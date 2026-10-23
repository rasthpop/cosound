"""Agent C — feedback and explanations (base §8).

`apply_feedback` validates an event against the session and turns it into a spec update with
the deterministic rule table (`feedback_rules`); it never touches the catalog or embeddings and
never persists anything (the orchestrator records the turn). Validation:

- the event belongs to this session, and its `query_id` is one of the session's turns;
- a track event names a track that query returned - except SELECT_TRACK, which may name any
  catalog track (selecting a point on the map is not feedback on a result).

`explain` builds evidence for each returned candidate and delegates the wording to the
description service; Agent C writes no prose itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from music_discovery.agents.feedback_rules import RuleContext, apply_rule, next_action
from music_discovery.agents.lexicon_loader import Lexicon
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder, SemanticSignal
from music_discovery.domain.enums import FeedbackType, NextAction
from music_discovery.domain.errors import (
    QueryNotInSession,
    SessionNotFound,
    TrackNotFound,
    TrackNotInResults,
)
from music_discovery.domain.models import SearchSession
from music_discovery.domain.protocols import TrackRepository
from music_discovery.domain.schemas import (
    TRACK_EVENTS,
    Explanation,
    FeedbackEvent,
    RankedCandidate,
    SearchSpecification,
)
from music_discovery.retrieval.hybrid_retriever import HybridResult


@dataclass(frozen=True)
class FeedbackDecision:
    accepted: bool
    spec: SearchSpecification
    """The spec to search with next (unchanged when rejected or a no-op)."""
    next_action: NextAction
    change_notes: list[str] = field(default_factory=list)
    reason: str | None = None
    """Why the event was not applied, when `accepted` is False."""


@dataclass(frozen=True)
class ExplainedCandidate:
    candidate: RankedCandidate
    """The candidate with its `evidence` attached."""
    explanation: Explanation


class FeedbackAgent:
    def __init__(
        self,
        lexicon: Lexicon,
        tracks: TrackRepository,
        evidence: EvidenceBuilder,
        descriptions: DescriptionService,
    ) -> None:
        self._ctx = RuleContext(lexicon=lexicon)
        self._tracks = tracks
        self._evidence = evidence
        self._descriptions = descriptions

    def apply_feedback(
        self,
        session: SearchSession,
        event: FeedbackEvent,
        *,
        spec: SearchSpecification | None = None,
    ) -> FeedbackDecision:
        """`spec` overrides the session's current spec (several events applied in one batch)."""
        current = self._validate(session, event)
        spec = spec or current
        result = apply_rule(spec, event, self._ctx)
        if result.rejected is not None:
            return FeedbackDecision(False, spec, NextAction.NONE, reason=result.rejected)
        if result.note is None:
            action = next_action(event)
            if action is NextAction.REFINE_SEARCH:
                action = NextAction.NONE  # nothing changed: no new search needed
            return FeedbackDecision(True, spec, action)
        return FeedbackDecision(True, result.spec, next_action(event), [result.note])

    def _validate(self, session: SearchSession, event: FeedbackEvent) -> SearchSpecification:
        if event.search_session_id != session.session_id:
            raise SessionNotFound(
                f"event {event.event_id} belongs to another session",
                details={"session_id": event.search_session_id},
            )
        turn = session.turn(event.query_id)
        current = session.current_spec
        if turn is None or current is None:
            raise QueryNotInSession(
                f"query {event.query_id} is not in session {session.session_id}",
                details={"query_id": event.query_id},
            )
        track = event.track_id
        if event.event_type in TRACK_EVENTS and track not in turn.result_track_ids:
            if event.event_type is not FeedbackType.SELECT_TRACK:
                raise TrackNotInResults(
                    f"track {track} was not returned for query {event.query_id}",
                    details={"track_id": track, "query_id": event.query_id},
                )
            if track is None or self._tracks.get(track) is None:
                raise TrackNotFound(
                    f"track {track} is not in the catalog", details={"track_id": track}
                )
        return current

    def explain(self, result: HybridResult) -> list[ExplainedCandidate]:
        degraded = [*result.outcome.degraded, *result.trace.degraded]
        model_id = result.trace.model_id
        explained: list[ExplainedCandidate] = []
        for candidate in result.outcome.candidates:
            track = self._tracks.get(candidate.track_id)
            hit = result.semantic_hits.get(candidate.track_id)
            signal = None
            if hit is not None and model_id is not None:
                signal = SemanticSignal(
                    prompt=hit.best_query.text,
                    raw_cosine=hit.raw_cosine,
                    rank=hit.rank,
                    model_id=model_id,
                    kind=hit.best_query.kind,
                )
            evidence = self._evidence.build(
                candidate,
                track,
                matched_fields=result.matched_fields.get(candidate.track_id, []),
                semantic=signal,
                degraded=degraded,
            )
            explained.append(
                ExplainedCandidate(
                    candidate=candidate.model_copy(update={"evidence": evidence}),
                    explanation=self._descriptions.describe(evidence, track),
                )
            )
        return explained
