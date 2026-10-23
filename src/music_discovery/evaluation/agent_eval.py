"""Component evaluations for Agent A (query understanding) and Agent C (feedback), base §6, §8.

Agent A, per query of the split, against `expected_attributes` / `expected_hard_constraints`:
- per-category precision / recall / F1 over attribute values (micro over queries), plus micro
  and macro F1 over all categories; vocals is scored as a single label (accuracy);
- hard-constraint accuracy: the predicted constraint set equals the expected one exactly;
- validity: every spec passed schema validation (always 1.0 on the deterministic path); with
  an LLM interpreter, the share of queries where the LLM reading was accepted is reported too.

Agent C, per case of `feedback_cases.jsonl` whose query is in the split: the initial spec comes
from Agent A, the initial plate from the hybrid retriever over the corpus, the events (or free
text) are applied through Agent C, and the plate is retrieved again. Checked:
- spec delta: every expected change is present (added / kept / raised / lowered preferences,
  negatives, track sets, vocals, accepted or rejected);
- preservation: original query and hard constraints unchanged (must be 100 %);
- ranking direction: the named track is gone / up / down in the new plate, when the case says;
- "what changed": accepted changes come with change notes.
Track references are `rank:N` in the initial plate, so cases do not depend on catalog ids.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.schemas import FeedbackEvent, SearchSpecification
from music_discovery.evaluation.datasets import EvalDataset, EvalQuery

CASES_FILE = "feedback_cases.jsonl"
CATEGORIES = ("mood", "instrument", "genre", "tempo", "energy", "texture", "era")
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
Retrieve = Callable[[SearchSpecification], list[str]]
"""Full ranked plate (internal track ids) for a spec over the evaluation corpus."""


# --- Agent A ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: Score) -> Score:
        return Score(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None:
            return None
        return 0.0 if p + r == 0 else 2 * p * r / (p + r)


@dataclass(frozen=True)
class AgentARow:
    query_id: str
    text: str
    interpreter: str
    valid: bool
    llm_fallback_reason: str | None
    scores: dict[str, Score]
    expected: dict[str, list[str]]
    predicted: dict[str, list[str]]
    vocals_expected: str
    vocals_predicted: str
    hard_expected: list[dict[str, Any]]
    hard_predicted: list[dict[str, Any]]

    @property
    def hard_correct(self) -> bool:
        key = lambda c: json.dumps(c, sort_keys=True)  # noqa: E731
        return sorted(map(key, self.hard_expected)) == sorted(map(key, self.hard_predicted))

    @property
    def vocals_correct(self) -> bool:
        return self.vocals_expected == self.vocals_predicted


def _hard(spec: SearchSpecification) -> list[dict[str, Any]]:
    return [c.model_dump(mode="json", exclude_none=True) for c in spec.hard_constraints]


def evaluate_agent_a(queries: Sequence[EvalQuery], agent: QueryAgent) -> list[AgentARow]:
    rows: list[AgentARow] = []
    for q in queries:
        result = agent.interpret_traced(q.text)
        spec = result.spec
        valid = SearchSpecification.model_validate(spec.model_dump(mode="json")) == spec
        expected_all = q.expected_attributes.model_dump()
        scores, expected, predicted = {}, {}, {}
        for category in CATEGORIES:
            want = {v.casefold() for v in expected_all.get(category, [])}
            got = {p.value.casefold() for p in spec.positive_preferences[category]}
            scores[category] = Score(len(want & got), len(got - want), len(want - got))
            expected[category], predicted[category] = sorted(want), sorted(got)
        rows.append(
            AgentARow(
                query_id=q.query_id,
                text=q.text,
                interpreter=spec.interpreter,
                valid=valid,
                llm_fallback_reason=result.llm_fallback_reason,
                scores=scores,
                expected=expected,
                predicted=predicted,
                vocals_expected=str(expected_all.get("vocals", "unspecified")),
                vocals_predicted=spec.vocal_preferences,
                hard_expected=[
                    c.model_dump(mode="json", exclude_none=True)
                    for c in q.expected_hard_constraints
                ],
                hard_predicted=_hard(spec),
            )
        )
    return rows


def agent_a_metrics(rows: Sequence[AgentARow], *, llm_enabled: bool) -> dict[str, Any]:
    per_category: dict[str, dict[str, float | int | None]] = {}
    total = Score()
    for category in CATEGORIES:
        s = sum((r.scores[category] for r in rows), Score())
        total += s
        per_category[category] = {
            "precision": s.precision,
            "recall": s.recall,
            "f1": s.f1,
            "support": s.tp + s.fn,
        }
    f1s = [m["f1"] for m in per_category.values() if m["f1"] is not None]
    n = len(rows)
    return {
        "n_queries": n,
        "per_category": per_category,
        "micro": {"precision": total.precision, "recall": total.recall, "f1": total.f1},
        "macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "vocals_accuracy": sum(r.vocals_correct for r in rows) / n if n else None,
        "hard_constraint_accuracy": sum(r.hard_correct for r in rows) / n if n else None,
        "validity_rate": sum(r.valid for r in rows) / n if n else None,
        "llm_acceptance_rate": (
            sum(r.interpreter == "llm" for r in rows) / n if n and llm_enabled else None
        ),
    }


def agent_a_csv_rows(rows: Sequence[AgentARow]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        disagreements = [
            f"{c}: expected {r.expected[c]} got {r.predicted[c]}"
            for c in CATEGORIES
            if r.expected[c] != r.predicted[c]
        ]
        if not r.vocals_correct:
            disagreements.append(f"vocals: expected {r.vocals_expected} got {r.vocals_predicted}")
        if not r.hard_correct:
            disagreements.append(f"hard: expected {r.hard_expected} got {r.hard_predicted}")
        out.append(
            {
                "query_id": r.query_id,
                "text": r.text,
                "interpreter": r.interpreter,
                "valid": r.valid,
                "llm_fallback_reason": r.llm_fallback_reason or "",
                "tp": sum(s.tp for s in r.scores.values()),
                "fp": sum(s.fp for s in r.scores.values()),
                "fn": sum(s.fn for s in r.scores.values()),
                "vocals_correct": r.vocals_correct,
                "hard_correct": r.hard_correct,
                "disagreements": " | ".join(disagreements),
            }
        )
    return out


# --- Agent C ----------------------------------------------------------------------------


class FeedbackCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    query_id: str
    text: str | None = None
    events: list[dict[str, Any]] = []
    expected: dict[str, Any]
    ranking: dict[str, str] | None = None
    notes: str = ""


def load_cases(directory: Path) -> list[FeedbackCase]:
    path = directory / CASES_FILE
    if not path.is_file():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [FeedbackCase.model_validate_json(line) for line in lines]


@dataclass(frozen=True)
class AgentCRow:
    case_id: str
    query_id: str
    accepted: bool
    delta_ok: bool
    preserved: bool
    ranking_ok: bool | None
    notes_ok: bool
    change_notes: list[str]
    failures: list[str] = field(default_factory=list)


def _resolve(ref: str, plate: Sequence[str]) -> str | None:
    kind, _, value = ref.partition(":")
    if kind == "rank" and value.isdigit() and 0 < int(value) <= len(plate):
        return plate[int(value) - 1]
    return None


def _values(spec: SearchSpecification, category: str) -> dict[str, float]:
    return {p.value: p.weight for p in spec.positive_preferences[category]}


def _check_delta(
    before: SearchSpecification,
    after: SearchSpecification,
    expected: Mapping[str, Any],
    plate: Sequence[str],
    accepted: bool,
) -> list[str]:
    failures: list[str] = []
    if expected.get("accepted", True) != accepted:
        failures.append(f"accepted={accepted}, expected {expected.get('accepted', True)}")
    for category, values in expected.get("preferences_added", {}).items():
        for v in values:
            if v in _values(before, category) or v not in _values(after, category):
                failures.append(f"{category} {v!r} not added")
    for category, values in expected.get("preferences_kept", {}).items():
        for v in values:
            kept = _values(after, category)
            if v not in kept or kept[v] != _values(before, category).get(v):
                failures.append(f"{category} {v!r} not kept unchanged")
    for key, sign in (("weights_raised", 1), ("weights_lowered", -1)):
        for category, values in expected.get(key, {}).items():
            for v in values:
                old, new = _values(before, category).get(v), _values(after, category).get(v)
                negated = v in {p.value for p in after.negative_preferences}
                moved = old is not None and (
                    (new is not None and (new - old) * sign > 0) or (sign < 0 and negated)
                )
                if not moved:
                    failures.append(f"{category} {v!r} weight not {key.split('_')[1]}")
    negatives = {p.value for p in after.negative_preferences}
    failures += [
        f"negative {v!r} missing" for v in expected.get("negatives_added", []) if v not in negatives
    ]
    for key, field_name in (
        ("excluded", "excluded_track_ids"),
        ("references", "reference_track_ids"),
        ("negative_references", "negative_reference_track_ids"),
    ):
        for ref in expected.get(key, []):
            track = _resolve(ref, plate)
            if track is None or track not in getattr(after, field_name):
                failures.append(f"{ref} not in {field_name}")
    if "vocals" in expected and after.vocal_preferences != expected["vocals"]:
        failures.append(f"vocals {after.vocal_preferences}, expected {expected['vocals']}")
    return failures


def _direction(
    before: Sequence[str], after: Sequence[str], track: str
) -> Literal["gone", "up", "down", "same"]:
    if track not in after:
        return "gone"
    old, new = before.index(track), after.index(track)
    return "up" if new < old else "down" if new > old else "same"


def _direction_ok(wanted: str, direction: str | None, was_first: bool) -> bool:
    """ "down" accepts "gone"; "up" accepts staying first (it cannot rise further)."""
    if direction == wanted:
        return True
    return (wanted == "down" and direction == "gone") or (
        wanted == "up" and direction == "same" and was_first
    )


def evaluate_agent_c(
    cases: Sequence[FeedbackCase],
    dataset: EvalDataset,
    *,
    query_agent: QueryAgent,
    feedback_agent: FeedbackAgent,
    retrieve: Retrieve,
    normalizer: FeedbackTextNormalizer,
) -> list[AgentCRow]:
    rows: list[AgentCRow] = []
    for case in cases:
        query = dataset.query(case.query_id)
        spec0 = query_agent.interpret(query.text)
        plate0 = retrieve(spec0)
        turn = SearchTurnRecord(
            query_id="qry_eval",
            query_text=query.text,
            spec=spec0,
            result_track_ids=plate0,
            created_at=EPOCH,
        )
        session = SearchSession(session_id="ses_eval", created_at=EPOCH).with_turn(turn)
        events = _events(case, plate0, normalizer)
        spec, accepted, notes = spec0, False, []
        for event in events:
            decision = feedback_agent.apply_feedback(session, event, spec=spec)
            accepted |= decision.accepted
            notes += decision.change_notes
            spec = decision.spec
        plate1 = retrieve(spec) if spec != spec0 else plate0
        delta_failures = _check_delta(spec0, spec, case.expected, plate0, accepted)
        failures = list(delta_failures)
        preserved = (
            spec.original_query == spec0.original_query
            and spec.hard_constraints == spec0.hard_constraints
        )
        if not preserved:
            failures.append("original query or hard constraints changed")
        ranking_ok = None
        if case.ranking is not None:
            track = _resolve(case.ranking["track"], plate0)
            direction = None if track is None else _direction(plate0, plate1, track)
            wanted = case.ranking["direction"]
            ranking_ok = _direction_ok(wanted, direction, track == plate0[0])
            if not ranking_ok:
                failures.append(f"{case.ranking['track']} went {direction}, expected {wanted}")
        changed = spec != spec0
        notes_ok = bool(notes) == changed
        if not notes_ok:
            failures.append("change notes missing" if changed else "notes without a change")
        rows.append(
            AgentCRow(
                case_id=case.case_id,
                query_id=case.query_id,
                accepted=accepted,
                delta_ok=not delta_failures,
                preserved=preserved,
                ranking_ok=ranking_ok,
                notes_ok=notes_ok,
                change_notes=notes,
                failures=failures,
            )
        )
    return rows


def _events(
    case: FeedbackCase, plate: Sequence[str], normalizer: FeedbackTextNormalizer
) -> list[FeedbackEvent]:
    base = {"search_session_id": "ses_eval", "query_id": "qry_eval", "timestamp": EPOCH}
    if case.text:
        result = normalizer.normalize(
            case.text,
            session_id="ses_eval",
            query_id="qry_eval",
            event_id="evt_eval",
            timestamp=EPOCH,
        )
        return result.events
    events = []
    for i, raw in enumerate(case.events, start=1):
        data = {k: v for k, v in raw.items() if k != "track"} | base | {"event_id": f"evt_{i}"}
        if "track" in raw:
            data["track_id"] = _resolve(raw["track"], plate)
        events.append(FeedbackEvent.model_validate(data))
    return events


def agent_c_metrics(rows: Sequence[AgentCRow]) -> dict[str, Any]:
    n = len(rows)
    ranked = [r.ranking_ok for r in rows if r.ranking_ok is not None]
    return {
        "n_cases": n,
        "spec_delta_accuracy": sum(r.delta_ok for r in rows) / n if n else None,
        "constraint_preservation": sum(r.preserved for r in rows) / n if n else None,
        "ranking_direction_accuracy": sum(ranked) / len(ranked) if ranked else None,
        "n_ranking_cases": len(ranked),
        "change_notes_ok": sum(r.notes_ok for r in rows) / n if n else None,
        "failed_cases": [r.case_id for r in rows if r.failures],
    }


def agent_c_csv_rows(rows: Sequence[AgentCRow]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": r.case_id,
            "query_id": r.query_id,
            "accepted": r.accepted,
            "delta_ok": r.delta_ok,
            "preserved": r.preserved,
            "ranking_ok": "" if r.ranking_ok is None else r.ranking_ok,
            "notes_ok": r.notes_ok,
            "change_notes": " | ".join(r.change_notes),
            "failures": " | ".join(r.failures),
        }
        for r in rows
    ]


def components_markdown(
    agent_a: Mapping[str, Any] | None, agent_c: Mapping[str, Any] | None
) -> list[str]:
    def fmt(value: object) -> str:
        return "—" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)

    lines: list[str] = []
    if agent_a is not None:
        lines += [
            f"### Agent A (n = {agent_a['n_queries']} queries)",
            "",
            "| Category | Precision | Recall | F1 | Support |",
            "|---|---|---|---|---|",
        ]
        for category, m in agent_a["per_category"].items():
            lines.append(
                f"| {category} | {fmt(m['precision'])} | {fmt(m['recall'])} | "
                f"{fmt(m['f1'])} | {m['support']} |"
            )
        micro = agent_a["micro"]
        lines += [
            "",
            f"- Micro P/R/F1: {fmt(micro['precision'])} / {fmt(micro['recall'])} / "
            f"{fmt(micro['f1'])}; macro F1 {fmt(agent_a['macro_f1'])}.",
            f"- Vocals accuracy {fmt(agent_a['vocals_accuracy'])}; hard-constraint accuracy "
            f"{fmt(agent_a['hard_constraint_accuracy'])}; structured-output validity "
            f"{fmt(agent_a['validity_rate'])}; "
            f"LLM acceptance {fmt(agent_a['llm_acceptance_rate'])}.",
            "- Per-query disagreements: `agent_a.csv`.",
            "- The lexicon was written against these query labels (P06.T01), so a high score here",
            "  shows the parser and labels agree; it does not measure how it generalizes.",
            "",
        ]
    if agent_c is not None:
        lines += [
            f"### Agent C (n = {agent_c['n_cases']} feedback cases)",
            "",
            f"- Spec-delta accuracy {fmt(agent_c['spec_delta_accuracy'])}; constraint "
            f"preservation {fmt(agent_c['constraint_preservation'])} (must be 1.000); ranking "
            f"direction {fmt(agent_c['ranking_direction_accuracy'])} "
            f"(n = {agent_c['n_ranking_cases']}); change notes {fmt(agent_c['change_notes_ok'])}.",
            f"- Failed cases: {', '.join(agent_c['failed_cases']) or 'none'} "
            "(details: `agent_c.csv`).",
            "",
        ]
    return lines
