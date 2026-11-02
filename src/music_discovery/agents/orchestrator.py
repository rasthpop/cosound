"""Orchestrator: one search turn = Agent A -> Agent B -> Agent C.explain (base §5, §8).

- `search(query, session, limit)`: interpret (follow-ups refine the session's spec), discover,
  explain, record the turn and save the session;
- `refine(session, event, limit)`: validate and apply one feedback event (Agent C), record it,
  and - when the spec changed - search again with the new spec;
- `refine_text(session, text, query_id, limit)`: free-text feedback normalized into events,
  applied in order, then one new search.

Every turn carries a "what changed" summary: notes for people (`change_summary`) and the
same changes as structured `SpecChange` entries (`changes`). The outcome is passed through
unchanged: OK, NO_CONFIDENT_MATCH (with reasons) or NEEDS_CLARIFICATION, with any `degraded`
flags. Sessions
are saved with the version they were read at, so a concurrent update raises
`StaleSessionVersion` instead of being lost. No agent here decides relevance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_b_discovery import DiscoveryAgent
from music_discovery.agents.agent_c_feedback import (
    ExplainedCandidate,
    FeedbackAgent,
    FeedbackDecision,
    rejected,
)
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.domain.enums import ChangeKind, NextAction
from music_discovery.domain.ids import IdPrefix
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.protocols import (
    Clock,
    FeedbackRepository,
    IdGenerator,
    SessionRepository,
)
from music_discovery.domain.schemas import (
    Explanation,
    FeedbackEvent,
    RetrievalTrace,
    SearchOutcome,
    SearchSpecification,
    SpecChange,
    WeightedPreference,
)

PREFERENCE_FIELDS = (
    "mood_preferences",
    "instrument_preferences",
    "genre_preferences",
    "tempo_preferences",
    "energy_preferences",
    "texture_preferences",
    "era_preferences",
)


@dataclass(frozen=True)
class SearchTurn:
    """One search (or the result of feedback that did not need a new search)."""

    session: SearchSession
    spec: SearchSpecification
    query_id: str | None
    """The new turn's id; None when no search ran (rejected feedback, SELECT_TRACK)."""
    outcome: SearchOutcome | None
    explanations: list[Explanation] = field(default_factory=list)
    trace: RetrievalTrace | None = None
    change_summary: list[str] = field(default_factory=list)
    changes: list[SpecChange] = field(default_factory=list)
    decision: FeedbackDecision | None = None
    llm_fallback_reason: str | None = None


class Orchestrator:
    def __init__(
        self,
        query: QueryAgent,
        discovery: DiscoveryAgent,
        feedback: FeedbackAgent,
        sessions: SessionRepository,
        feedback_events: FeedbackRepository,
        clock: Clock,
        ids: IdGenerator,
        feedback_text: FeedbackTextNormalizer | None = None,
    ) -> None:
        self._a = query
        self._b = discovery
        self._c = feedback
        self._sessions = sessions
        self._events = feedback_events
        self._clock = clock
        self._ids = ids
        self._text = feedback_text

    def search(self, query: str, session: SearchSession | None, limit: int) -> SearchTurn:
        read_version = None if session is None else session.version
        if session is None:
            session = SearchSession(
                session_id=self._ids.new(IdPrefix.SESSION), created_at=self._clock.now()
            )
        previous = session.current_spec
        interpretation = self._a.interpret_traced(query, session)
        spec = interpretation.spec
        diff = _spec_diff(previous, spec) if previous is not None else []
        notes = [n for n, _ in diff]
        changes = [c for _, c in diff if c is not None]
        turn = self._run(session, query, spec, limit, notes, changes, triggered_by=None)
        self._sessions.save(turn.session, expected_version=read_version)
        return replace(turn, llm_fallback_reason=interpretation.llm_fallback_reason)

    def refine(self, session: SearchSession, event: FeedbackEvent, limit: int) -> SearchTurn:
        return self._refine(session, [event], limit)

    def refine_text(
        self, session: SearchSession, text: str, query_id: str, limit: int
    ) -> SearchTurn:
        if self._text is None:
            raise RuntimeError("free-text feedback is not configured")
        normalized = self._text.normalize(
            text,
            session_id=session.session_id,
            query_id=query_id,
            event_id=self._ids.new(IdPrefix.EVENT),
            timestamp=self._clock.now(),
        )
        if not normalized.accepted:
            spec = session.current_spec
            if spec is None:
                raise ValueError("feedback needs a session with a search")
            decision = FeedbackDecision(
                False, spec, NextAction.NONE, reason=normalized.reason, changes=[rejected()]
            )
            return SearchTurn(session, spec, None, None, decision=decision)
        return self._refine(session, normalized.events, limit)

    def _refine(
        self, session: SearchSession, events: Sequence[FeedbackEvent], limit: int
    ) -> SearchTurn:
        read_version = session.version
        spec = session.current_spec
        decisions: list[FeedbackDecision] = []
        recorded = session
        for event in events:
            decision = self._c.apply_feedback(session, event, spec=spec)
            decisions.append(decision)
            recorded = recorded.with_feedback(event)
            if decision.accepted:
                spec = decision.spec  # later events in a batch build on earlier ones
        assert spec is not None  # apply_feedback raised if the session had no search
        refused = [d.reason for d in decisions if not d.accepted and d.reason]
        summary = FeedbackDecision(
            accepted=any(d.accepted for d in decisions),
            spec=spec,
            next_action=_combined_action(decisions),
            change_notes=[n for d in decisions for n in d.change_notes],
            reason="; ".join(refused) or None,
            changes=[c for d in decisions for c in d.changes],
        )
        if summary.next_action is not NextAction.REFINE_SEARCH:
            turn = SearchTurn(recorded, spec, None, None, decision=summary)
        else:
            text = recorded.turns[-1].query_text
            turn = self._run(
                recorded,
                text,
                spec,
                limit,
                summary.change_notes,
                summary.changes,
                triggered_by=events[-1].event_id,
            )
            turn = replace(turn, decision=summary)
        self._sessions.save(turn.session, expected_version=read_version)
        for event in events:
            self._events.add(event)
        return turn

    def _run(
        self,
        session: SearchSession,
        query_text: str,
        spec: SearchSpecification,
        limit: int,
        notes: list[str],
        changes: list[SpecChange],
        *,
        triggered_by: str | None,
    ) -> SearchTurn:
        result = self._b.discover(spec, limit)
        explained: list[ExplainedCandidate] = self._c.explain(result)
        outcome = result.outcome.model_copy(update={"candidates": [e.candidate for e in explained]})
        query_id = self._ids.new(IdPrefix.QUERY)
        record = SearchTurnRecord(
            query_id=query_id,
            query_text=query_text,
            spec=spec,
            result_track_ids=[c.track_id for c in outcome.candidates],
            created_at=self._clock.now(),
            triggered_by_event_id=triggered_by,
            change_summary=notes,
        )
        return SearchTurn(
            session=session.with_turn(record),
            spec=spec,
            query_id=query_id,
            outcome=outcome,
            explanations=[e.explanation for e in explained],
            trace=result.trace,
            change_summary=notes,
            changes=changes,
        )


def _combined_action(decisions: Sequence[FeedbackDecision]) -> NextAction:
    actions = [d.next_action for d in decisions if d.accepted]
    if NextAction.REFINE_SEARCH in actions:
        return NextAction.REFINE_SEARCH
    if NextAction.SHOW_DETAILS in actions:
        return NextAction.SHOW_DETAILS
    return NextAction.NONE


def spec_changes(old: SearchSpecification, new: SearchSpecification) -> list[str]:
    """Human-readable differences between two specs, for "what changed"."""
    return [note for note, _ in _spec_diff(old, new)]


def spec_change_entries(old: SearchSpecification, new: SearchSpecification) -> list[SpecChange]:
    """The same differences as structured entries."""
    return [change for _, change in _spec_diff(old, new) if change is not None]


_VOCAL_KINDS = {
    "preferred": ChangeKind.PREFERENCE_RAISED,
    "avoided": ChangeKind.PREFERENCE_LOWERED,
    "unspecified": ChangeKind.PREFERENCE_REMOVED,
}
"""`required`/`excluded` vocals come with a hard constraint, reported as `constraint_added`."""


Diff = list[tuple[str, SpecChange | None]]


def _spec_diff(old: SearchSpecification, new: SearchSpecification) -> Diff:
    """(note, entry) pairs; a note without an entry is covered by another entry."""
    diff: Diff = []
    for name in PREFERENCE_FIELDS:
        category = name.removesuffix("_preferences")
        diff += _pref_diff(getattr(old, name), getattr(new, name), category)
    diff += _pref_diff(old.negative_preferences, new.negative_preferences, None)
    if old.vocal_preferences != new.vocal_preferences:
        note = f"vocals {new.vocal_preferences}"
        kind = _VOCAL_KINDS.get(new.vocal_preferences)
        change = None if kind is None else SpecChange(kind=kind, attribute="vocals", value="vocals")
        diff.append((note, change))
    old_hard = {c.model_dump_json() for c in old.hard_constraints}
    for c in new.hard_constraints:
        if c.model_dump_json() not in old_hard:
            subject = c.value if c.value is not None else str(c.attribute)
            change = SpecChange(
                kind=ChangeKind.CONSTRAINT_ADDED,
                attribute=str(c.attribute),
                operator=str(c.operator),
                value=c.value,
            )
            diff.append((f"constraint: {subject} {c.operator}", change))
    if new.needs_clarification and not old.needs_clarification:
        change = SpecChange(kind=ChangeKind.NEEDS_CLARIFICATION, value=new.clarification_question)
        diff.append(("needs clarification", change))
    return diff


def _pref_diff(
    old: Sequence[WeightedPreference],
    new: Sequence[WeightedPreference],
    category: str | None,
) -> Diff:
    """`category=None` diffs the negative preferences."""
    lead = "" if category is not None else "less "
    before = {p.value: p.weight for p in old}
    after = {p.value: p.weight for p in new}

    def entry(kind: ChangeKind, negative_kind: ChangeKind, value: str) -> SpecChange:
        if category is None:
            return SpecChange(kind=negative_kind, value=value)
        return SpecChange(kind=kind, attribute=category, value=value)

    added, removed = ChangeKind.PREFERENCE_ADDED, ChangeKind.PREFERENCE_REMOVED
    neg_added, neg_removed = ChangeKind.NEGATIVE_ADDED, ChangeKind.NEGATIVE_REMOVED
    diff: Diff = [
        (f"added {lead}{v}", entry(added, neg_added, v)) for v in after if v not in before
    ]
    diff += [
        (f"dropped {lead}{v}", entry(removed, neg_removed, v)) for v in before if v not in after
    ]
    for v in after:
        if v in before and abs(after[v] - before[v]) > 1e-9:
            up = after[v] > before[v]
            kind = ChangeKind.PREFERENCE_RAISED if up else ChangeKind.PREFERENCE_LOWERED
            note = f"{lead}{v} {before[v]:.2f} -> {after[v]:.2f}"
            diff.append((note, entry(kind, neg_added if up else neg_removed, v)))
    return diff
