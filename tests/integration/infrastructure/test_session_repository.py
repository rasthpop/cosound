"""Session and feedback repository contract, run against the in-memory fakes and SQLite."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from music_discovery.domain import protocols as p
from music_discovery.domain.enums import FeedbackType
from music_discovery.domain.errors import StaleSessionVersion
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    FeedbackEvent,
    HardConstraint,
    SearchSpecification,
    WeightedPreference,
)
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlFeedbackRepository,
    SqlSessionRepository,
)
from tests import fakes

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
SPEC = SearchSpecification(
    original_query="Calm piano without vocals",
    mood_preferences=[WeightedPreference(value="calm", weight=0.7, source_span="calm")],
    instrument_preferences=[WeightedPreference(value="piano", weight=0.7, source_span=None)],
    vocal_preferences="excluded",
    hard_constraints=[
        HardConstraint(attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED),
        HardConstraint(
            attribute=ConstraintAttribute.DURATION,
            operator=ConstraintOperator.RANGE,
            range=(None, 180.0),
        ),
    ],
    semantic_prompts=["calm music featuring piano"],
)


@pytest.fixture(params=["memory", "sql"])
def repos(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[tuple[p.SessionRepository, p.FeedbackRepository]]:
    if request.param == "memory":
        yield fakes.InMemorySessionRepository(), fakes.InMemoryFeedbackRepository()
        return
    database = Database(f"sqlite:///{tmp_path / 'sessions.db'}")
    database.init_schema()
    yield SqlSessionRepository(database), SqlFeedbackRepository(database)
    database.dispose()


def turn(query_id: str, spec: SearchSpecification = SPEC, **kw: object) -> SearchTurnRecord:
    return SearchTurnRecord(
        query_id=query_id,
        query_text=spec.original_query,
        spec=spec,
        result_track_ids=["trk_a", "trk_b"],
        created_at=NOW,
        **kw,  # type: ignore[arg-type]
    )


def event(event_id: str, minutes: int = 0, **kw: object) -> FeedbackEvent:
    data: dict[str, object] = {
        "event_id": event_id,
        "search_session_id": "ses_1",
        "query_id": "qry_1",
        "track_id": "trk_a",
        "event_type": FeedbackType.MORE_LIKE_THIS,
        "timestamp": NOW + timedelta(minutes=minutes),
    }
    return FeedbackEvent.model_validate(data | kw)


def new_session() -> SearchSession:
    return SearchSession(session_id="ses_1", created_at=NOW)


def test_missing_session_is_none(repos: tuple[p.SessionRepository, p.FeedbackRepository]) -> None:
    sessions, _ = repos
    assert sessions.get("nope") is None


def test_session_round_trips_with_turns_and_feedback(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    sessions, _ = repos
    refined = SPEC.model_copy(update={"spec_version": 2, "excluded_track_ids": ["trk_b"]})
    session = (
        new_session()
        .with_turn(turn("qry_1"))
        .with_feedback(event("evt_1", track_id="trk_b", event_type=FeedbackType.NOT_RELEVANT))
        .with_turn(
            turn("qry_2", refined, triggered_by_event_id="evt_1", change_summary=["excluded trk_b"])
        )
    )
    sessions.save(session, expected_version=None)
    loaded = sessions.get("ses_1")
    assert loaded == session
    assert loaded is not None
    assert loaded.current_spec == refined
    assert loaded.spec_history == [SPEC, refined]
    assert loaded.turns[0].spec.hard_constraints[1].range == (None, 180.0)


def test_updates_advance_with_the_read_version(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    sessions, _ = repos
    first = new_session().with_turn(turn("qry_1"))
    sessions.save(first, expected_version=None)
    second = first.with_turn(turn("qry_2"))
    sessions.save(second, expected_version=first.version)
    assert sessions.get("ses_1") == second


def test_concurrent_update_with_stale_version_raises(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    sessions, _ = repos
    base = new_session().with_turn(turn("qry_1"))
    sessions.save(base, expected_version=None)
    read_a = sessions.get("ses_1")
    read_b = sessions.get("ses_1")
    assert read_a is not None
    assert read_b is not None
    sessions.save(read_a.with_turn(turn("qry_a")), expected_version=read_a.version)
    with pytest.raises(StaleSessionVersion) as error:
        sessions.save(read_b.with_turn(turn("qry_b")), expected_version=read_b.version)
    assert error.value.code == "stale_session_version"
    stored = sessions.get("ses_1")
    assert stored is not None
    assert [t.query_id for t in stored.turns] == ["qry_1", "qry_a"], "the loser wrote nothing"


def test_creating_an_existing_session_raises(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    sessions, _ = repos
    sessions.save(new_session(), expected_version=None)
    with pytest.raises(StaleSessionVersion):
        sessions.save(new_session(), expected_version=None)


def test_updating_a_missing_session_raises(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    sessions, _ = repos
    with pytest.raises(StaleSessionVersion):
        sessions.save(new_session(), expected_version=3)


def test_feedback_events_are_listed_per_session_in_time_order(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    _, feedback = repos
    later = event(
        "evt_2",
        minutes=5,
        event_type=FeedbackType.MORE_OF_ATTRIBUTE,
        track_id=None,
        attribute="electronic",
        value=0.2,
    )
    feedback.add(later)
    feedback.add(event("evt_1", minutes=1, free_text="nice"))
    feedback.add(event("evt_x", search_session_id="ses_other"))
    events = feedback.for_session("ses_1")
    assert [e.event_id for e in events] == ["evt_1", "evt_2"]
    assert events[1] == later
    assert events[1].track_id is None, "missing stays None"
    assert feedback.for_session("ses_none") == []


def test_adding_the_same_event_twice_keeps_one(
    repos: tuple[p.SessionRepository, p.FeedbackRepository],
) -> None:
    _, feedback = repos
    feedback.add(event("evt_1"))
    feedback.add(event("evt_1"))
    assert len(feedback.for_session("ses_1")) == 1


def test_sql_session_tables_survive_reopening(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'sessions.db'}"
    database = Database(url)
    database.init_schema()
    session = new_session().with_turn(turn("qry_1"))
    SqlSessionRepository(database).save(session, expected_version=None)
    database.dispose()
    reopened = Database(url)
    reopened.init_schema()
    assert SqlSessionRepository(reopened).get("ses_1") == session
    reopened.dispose()
