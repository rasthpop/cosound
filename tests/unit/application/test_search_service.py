from __future__ import annotations

import pytest

from music_discovery.domain.enums import CapabilityStatus, InterpreterStatus, SearchOutcomeKind
from music_discovery.domain.errors import InvalidRequest, SessionNotFound
from tests.support.drafts import flute_draft
from tests.support.world import QUERY, World


def test_search_joins_candidates_with_track_facts() -> None:
    world = World()
    result = world.search.search(QUERY, session_id=None, limit=6)

    assert result.outcome.kind is SearchOutcomeKind.OK
    assert result.query_id is not None
    assert [i.candidate.rank for i in result.items] == list(range(1, len(result.items) + 1))
    by_id = {i.view.track.id: i for i in result.items}
    assert {"trk_sound", "trk_both"} <= set(by_id)
    sound = by_id["trk_sound"]
    assert sound.explanation is not None
    assert sound.view.audio is not None
    assert sound.view.coordinates is not None
    assert sound.view.projection_version == "umap-test"
    tape = by_id.get("trk_tape")
    if tape is not None:  # no embedding: no audio record, not on the map
        assert tape.view.audio is None
        assert tape.view.coordinates is None
        assert tape.view.projection_version is None
    assert result.capabilities.semantic is CapabilityStatus.AVAILABLE
    assert result.capabilities.llm_interpreter is InterpreterStatus.DISABLED
    assert result.warnings == []
    assert world.sessions.get(result.session.session_id) == result.session


def test_follow_up_query_continues_the_session() -> None:
    world = World()
    first = world.search.search(QUERY, session_id=None, limit=5)
    second = world.search.search("more electronic", session_id=first.session.session_id, limit=5)
    assert second.session.session_id == first.session.session_id
    assert len(second.session.turns) == 2
    assert second.spec.original_query.startswith(first.spec.original_query)
    assert second.change_summary  # "what changed" is reported


def test_unknown_session_is_not_found() -> None:
    with pytest.raises(SessionNotFound):
        World().search.search(QUERY, session_id="ses_missing", limit=5)


@pytest.mark.parametrize(("query", "limit"), [("   ", 5), (QUERY, 0), (QUERY, 101), ("x" * 501, 5)])
def test_invalid_requests_raise_validation_errors(query: str, limit: int) -> None:
    with pytest.raises(InvalidRequest) as info:
        World().search.search(query, session_id=None, limit=limit)
    assert info.value.code == "validation_error"


def test_semantic_unavailable_degrades_to_metadata_with_warning() -> None:
    result = World(semantic=False).search.search(QUERY, session_id=None, limit=5)
    assert result.outcome.kind is SearchOutcomeKind.OK
    assert result.items
    assert all(i.candidate.score.semantic is None for i in result.items)
    assert result.capabilities.semantic is CapabilityStatus.UNAVAILABLE
    assert result.capabilities.semantic_reason == "clap_checkpoint_missing"
    assert [w.code for w in result.warnings] == ["semantic_unavailable"]


def test_map_unavailable_keeps_search_working() -> None:
    result = World(projection_available=False).search.search(QUERY, session_id=None, limit=5)
    assert result.items
    assert all(i.view.coordinates is None for i in result.items)
    assert result.capabilities.map is CapabilityStatus.UNAVAILABLE
    assert result.capabilities.map_reason == "projection_unavailable"
    assert "map_unavailable" in [w.code for w in result.warnings]


def test_llm_used_and_llm_fallback_are_reported() -> None:
    used = World(llm_responses=[flute_draft()]).search.search(QUERY, session_id=None, limit=5)
    assert used.capabilities.llm_interpreter is InterpreterStatus.USED
    assert used.spec.interpreter == "llm"
    assert used.warnings == []

    failed = World(llm_responses=["invalid_output"]).search.search(QUERY, session_id=None, limit=5)
    assert failed.outcome.kind is SearchOutcomeKind.OK  # deterministic parser took over
    assert failed.spec.interpreter == "deterministic"
    assert failed.capabilities.llm_interpreter is InterpreterStatus.FALLBACK
    assert [w.code for w in failed.warnings] == ["llm_fallback"]


def test_needs_clarification_has_no_items() -> None:
    result = World().search.search("no vocals with female vocals", session_id=None, limit=5)
    assert result.outcome.kind is SearchOutcomeKind.NEEDS_CLARIFICATION
    assert result.outcome.clarification_question
    assert result.items == []
