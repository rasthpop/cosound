from __future__ import annotations

import pytest

from music_discovery.application.feedback_service import FeedbackCommand
from music_discovery.application.search_service import SearchResult
from music_discovery.domain.enums import FeedbackType, NextAction
from music_discovery.domain.errors import (
    InvalidFeedbackEvent,
    InvalidRequest,
    QueryNotInSession,
    SessionNotFound,
    TrackNotFound,
    TrackNotInResults,
)
from tests.support.world import QUERY, World


def searched(world: World) -> SearchResult:
    return world.search.search(QUERY, session_id=None, limit=6)


def command(result: SearchResult, **kw: object) -> FeedbackCommand:
    assert result.query_id is not None
    values: dict[str, object] = {
        "session_id": result.session.session_id,
        "query_id": result.query_id,
    }
    values.update(kw)
    return FeedbackCommand(**values)  # type: ignore[arg-type]


def test_not_relevant_refines_and_refresh_returns_the_new_plate() -> None:
    world = World()
    first = searched(world)
    top = first.items[0].view.track.id

    result = world.feedback.submit(
        command(first, event_type=FeedbackType.NOT_RELEVANT, track_id=top, refresh=True)
    )

    assert result.accepted
    assert result.next_action is NextAction.REFINE_SEARCH
    assert result.change_summary
    assert top in result.spec.excluded_track_ids
    assert result.refreshed is not None
    assert top not in [i.view.track.id for i in result.refreshed.items]
    assert len(result.session.turns) == 2
    assert world.events.for_session(first.session.session_id)


def test_without_refresh_no_plate_is_returned_but_the_turn_is_recorded() -> None:
    world = World()
    first = searched(world)
    result = world.feedback.submit(
        command(first, event_type=FeedbackType.MORE_OF_ATTRIBUTE, attribute="electronic")
    )
    assert result.accepted
    assert result.refreshed is None
    assert len(result.session.turns) == 2
    assert result.spec.original_query == QUERY


def test_select_track_from_the_map_needs_no_search() -> None:
    world = World()
    first = searched(world)
    shown = {i.view.track.id for i in first.items}
    outside = next(t for t in ("trk_night", "trk_bus", "trk_fill0") if t not in shown)
    result = world.feedback.submit(
        command(first, event_type=FeedbackType.SELECT_TRACK, track_id=outside, refresh=True)
    )
    assert result.accepted
    assert result.next_action is NextAction.SHOW_DETAILS
    assert result.refreshed is None
    assert len(result.session.turns) == 1


def test_free_text_feedback_is_normalized_or_rejected() -> None:
    world = World()
    first = searched(world)
    accepted = world.feedback.submit(command(first, free_text="more electronic", refresh=True))
    assert accepted.accepted
    assert accepted.refreshed is not None

    rejected = world.feedback.submit(
        command(searched(world), free_text="the weather is lovely today")
    )
    assert not rejected.accepted
    assert rejected.reason
    assert rejected.next_action is NextAction.NONE


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"session_id": "ses_missing"}, SessionNotFound),
        (
            {
                "query_id": "qry_missing",
                "event_type": FeedbackType.NOT_RELEVANT,
                "track_id": "trk_fill0",
            },
            QueryNotInSession,
        ),
        ({"query_id": "qry_missing", "free_text": "more electronic"}, QueryNotInSession),
        ({"event_type": FeedbackType.SELECT_TRACK, "track_id": "trk_unknown"}, TrackNotFound),
        ({"event_type": FeedbackType.MORE_OF_ATTRIBUTE}, InvalidFeedbackEvent),
        ({"event_type": FeedbackType.NOT_RELEVANT}, InvalidFeedbackEvent),
        ({}, InvalidFeedbackEvent),
        (
            {"event_type": FeedbackType.NOT_RELEVANT, "track_id": "trk_fill0", "limit": 0},
            InvalidRequest,
        ),
    ],
)
def test_invalid_feedback_references(overrides: dict[str, object], error: type[Exception]) -> None:
    world = World()
    first = searched(world)
    with pytest.raises(error):
        world.feedback.submit(command(first, **overrides))


def test_track_not_in_results_is_refused() -> None:
    world = World()
    first = searched(world)
    shown = {i.view.track.id for i in first.items}
    outside = next(t.id for t in world.tracks.list_page(limit=50) if t.id not in shown)
    with pytest.raises(TrackNotInResults):
        world.feedback.submit(
            command(first, event_type=FeedbackType.NOT_RELEVANT, track_id=outside)
        )
