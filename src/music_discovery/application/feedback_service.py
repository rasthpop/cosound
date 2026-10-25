"""Feedback use case (base.md §8, §13.3): validate, apply through Agent C, optionally re-search.

Validation order: the session exists → the event is well-formed → Agent C checks that the
query belongs to the session and the track was in its results (SELECT_TRACK may name any
catalog track, e.g. a point picked on the map). Typed events and free text are both accepted;
free text is normalized into events (lexicon, optional LLM) or rejected with a reason.

Accepted feedback that changes the spec always runs the next search, so the session history
stays complete; `refresh` only decides whether that plate is returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from music_discovery.agents.orchestrator import Orchestrator, SearchTurn
from music_discovery.application.search_service import SearchResult, SearchService, check_limit
from music_discovery.domain.enums import FeedbackType, NextAction
from music_discovery.domain.errors import InvalidFeedbackEvent, QueryNotInSession
from music_discovery.domain.ids import IdPrefix
from music_discovery.domain.models import SearchSession
from music_discovery.domain.protocols import Clock, IdGenerator
from music_discovery.domain.schemas import FeedbackEvent, SearchSpecification


@dataclass(frozen=True)
class FeedbackCommand:
    session_id: str
    query_id: str
    event_type: FeedbackType | None = None
    track_id: str | None = None
    attribute: str | None = None
    value: bool | float | str | None = None
    free_text: str | None = None
    refresh: bool = False
    limit: int = 10


@dataclass(frozen=True)
class FeedbackResult:
    accepted: bool
    reason: str | None
    next_action: NextAction
    session: SearchSession
    spec: SearchSpecification
    change_summary: list[str] = field(default_factory=list)
    refreshed: SearchResult | None = None


class FeedbackService:
    def __init__(
        self,
        orchestrator: Orchestrator,
        search: SearchService,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._orchestrator = orchestrator
        self._search = search
        self._ids = ids
        self._clock = clock

    def submit(self, command: FeedbackCommand) -> FeedbackResult:
        check_limit(command.limit)
        session = self._search.session(command.session_id)
        free_text = (command.free_text or "").strip() or None
        if command.event_type is None:
            if free_text is None:
                raise InvalidFeedbackEvent(
                    "feedback needs an event_type or free_text", details={"field": "event_type"}
                )
            if session.turn(command.query_id) is None:
                # typed events get this check from Agent C; free text is checked here first
                raise QueryNotInSession(
                    f"query {command.query_id} is not in session {session.session_id}",
                    details={"query_id": command.query_id},
                )
            turn = self._orchestrator.refine_text(
                session, free_text, command.query_id, command.limit
            )
        else:
            event = self._event(command, command.event_type, free_text)
            turn = self._orchestrator.refine(session, event, command.limit)
        return self._result(turn, refresh=command.refresh)

    def _event(
        self, command: FeedbackCommand, event_type: FeedbackType, free_text: str | None
    ) -> FeedbackEvent:
        try:
            return FeedbackEvent(
                event_id=self._ids.new(IdPrefix.EVENT),
                search_session_id=command.session_id,
                query_id=command.query_id,
                track_id=command.track_id,
                event_type=event_type,
                attribute=command.attribute,
                value=command.value,
                free_text=free_text,
                timestamp=self._clock.now(),
            )
        except ValidationError as exc:
            problems = [e["msg"] for e in exc.errors()]
            raise InvalidFeedbackEvent("; ".join(problems), details={"errors": problems}) from exc

    def _result(self, turn: SearchTurn, *, refresh: bool) -> FeedbackResult:
        decision = turn.decision
        if decision is None:
            raise ValueError("a feedback turn always carries a decision")
        refreshed = self._search.assemble(turn) if refresh and turn.outcome is not None else None
        return FeedbackResult(
            accepted=decision.accepted,
            reason=decision.reason,
            next_action=decision.next_action,
            session=turn.session,
            spec=turn.spec,
            change_summary=list(decision.change_notes),
            refreshed=refreshed,
        )
