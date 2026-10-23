"""Orchestrator: one search turn = Agent A -> Agent B -> Agent C.explain (base §5, §8).

- `search(query, session, limit)`: interpret (follow-ups refine the session's spec), discover,
  explain, record the turn and save the session;
- `refine(session, event, limit)`: validate and apply one feedback event (Agent C), record it,
  and - when the spec changed - search again with the new spec;
- `refine_text(session, text, query_id, limit)`: free-text feedback normalized into events,
  applied in order, then one new search.

Every turn carries a "what changed" summary. The outcome is passed through unchanged: OK,
NO_CONFIDENT_MATCH (with reasons) or NEEDS_CLARIFICATION, with any `degraded` flags. Sessions
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
)
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.domain.enums import NextAction
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
        changes = spec_changes(previous, spec) if previous is not None else []
        turn = self._run(session, query, spec, limit, changes, triggered_by=None)
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
            decision = FeedbackDecision(False, spec, NextAction.NONE, reason=normalized.reason)
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
        rejected = [d.reason for d in decisions if not d.accepted and d.reason]
        summary = FeedbackDecision(
            accepted=any(d.accepted for d in decisions),
            spec=spec,
            next_action=_combined_action(decisions),
            change_notes=[n for d in decisions for n in d.change_notes],
            reason="; ".join(rejected) or None,
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
        changes: list[str],
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
            change_summary=changes,
        )
        return SearchTurn(
            session=session.with_turn(record),
            spec=spec,
            query_id=query_id,
            outcome=outcome,
            explanations=[e.explanation for e in explained],
            trace=result.trace,
            change_summary=changes,
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
    changes: list[str] = []
    for name in PREFERENCE_FIELDS:
        changes += _pref_changes(getattr(old, name), getattr(new, name), "")
    changes += _pref_changes(old.negative_preferences, new.negative_preferences, "less ")
    if old.vocal_preferences != new.vocal_preferences:
        changes.append(f"vocals {new.vocal_preferences}")
    old_hard = {c.model_dump_json() for c in old.hard_constraints}
    for c in new.hard_constraints:
        if c.model_dump_json() not in old_hard:
            subject = c.value if c.value is not None else str(c.attribute)
            changes.append(f"constraint: {subject} {c.operator}")
    if new.needs_clarification and not old.needs_clarification:
        changes.append("needs clarification")
    return changes


def _pref_changes(
    old: Sequence[WeightedPreference], new: Sequence[WeightedPreference], lead: str
) -> list[str]:
    before = {p.value: p.weight for p in old}
    after = {p.value: p.weight for p in new}
    changes = [f"added {lead}{v}" for v in after if v not in before]
    changes += [f"dropped {lead}{v}" for v in before if v not in after]
    changes += [
        f"{lead}{v} {before[v]:.2f} -> {after[v]:.2f}"
        for v in after
        if v in before and abs(after[v] - before[v]) > 1e-9
    ]
    return changes
