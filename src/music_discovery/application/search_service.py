"""Search use case: query → orchestrator turn → result with track facts (base.md §13.1).

Returns domain objects plus the catalog/audio/map facts the API needs; no HTTP concepts.
Relevance comes from the orchestrator (hybrid engine); this layer only assembles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from music_discovery.agents.agent_b_discovery import MAX_LIMIT
from music_discovery.agents.orchestrator import Orchestrator, SearchTurn
from music_discovery.application.capabilities import (
    Capabilities,
    CapabilityService,
    SearchWarning,
    turn_warnings,
)
from music_discovery.application.results import TrackView, TrackViewBuilder
from music_discovery.domain.errors import InvalidRequest, SessionNotFound
from music_discovery.domain.models import SearchSession
from music_discovery.domain.protocols import SessionRepository
from music_discovery.domain.schemas import (
    Explanation,
    RankedCandidate,
    SearchOutcome,
    SearchSpecification,
)

log = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 500


@dataclass(frozen=True)
class ResultItem:
    candidate: RankedCandidate
    explanation: Explanation | None
    view: TrackView


@dataclass(frozen=True)
class SearchResult:
    session: SearchSession
    query_id: str | None
    spec: SearchSpecification
    outcome: SearchOutcome
    items: list[ResultItem]
    capabilities: Capabilities
    warnings: list[SearchWarning] = field(default_factory=list)
    change_summary: list[str] = field(default_factory=list)


class SearchService:
    def __init__(
        self,
        orchestrator: Orchestrator,
        sessions: SessionRepository,
        views: TrackViewBuilder,
        capabilities: CapabilityService,
    ) -> None:
        self._orchestrator = orchestrator
        self._sessions = sessions
        self._views = views
        self._capabilities = capabilities

    def search(self, query: str, *, session_id: str | None, limit: int) -> SearchResult:
        """A new search, or a follow-up query when `session_id` names an existing session."""
        text = query.strip()
        if not text:
            raise InvalidRequest("query must not be empty", details={"field": "query"})
        if len(text) > MAX_QUERY_LENGTH:
            raise InvalidRequest(
                f"query is longer than {MAX_QUERY_LENGTH} characters", details={"field": "query"}
            )
        check_limit(limit)
        session = None if session_id is None else self.session(session_id)
        return self.assemble(self._orchestrator.search(text, session, limit))

    def session(self, session_id: str) -> SearchSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(
                f"session {session_id} does not exist", details={"session_id": session_id}
            )
        return session

    def assemble(self, turn: SearchTurn) -> SearchResult:
        """Join a turn's candidates with catalog facts, capabilities and warnings."""
        if turn.outcome is None:
            raise ValueError("the turn ran no search")
        outcome = turn.outcome
        views = self._views.many([c.track_id for c in outcome.candidates])
        explanations = {e.track_id: e for e in turn.explanations}
        items = []
        for candidate in outcome.candidates:
            view = views.get(candidate.track_id)
            if view is None:  # the index and the catalog disagree; never invent the track
                log.warning("ranked track %s is not in the catalog", candidate.track_id)
                continue
            items.append(ResultItem(candidate, explanations.get(candidate.track_id), view))
        degraded = [*outcome.degraded, *(turn.trace.degraded if turn.trace else [])]
        capabilities = self._capabilities.for_turn(
            degraded=degraded, interpreter=turn.spec.interpreter
        )
        fallback = turn.llm_fallback_reason if self._capabilities.llm_configured else None
        return SearchResult(
            session=turn.session,
            query_id=turn.query_id,
            spec=turn.spec,
            outcome=outcome,
            items=items,
            capabilities=capabilities,
            warnings=turn_warnings(degraded, capabilities, llm_fallback_reason=fallback),
            change_summary=list(turn.change_summary),
        )


def check_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidRequest(
            f"limit must be between 1 and {MAX_LIMIT}", details={"field": "limit", "max": MAX_LIMIT}
        )
