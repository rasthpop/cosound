"""DTO mapping: nulls preserved, enums on the wire, no domain objects, valid examples."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel

from music_discovery.api import mapping
from music_discovery.api import schemas as s
from music_discovery.api.examples import build_examples
from music_discovery.application.feedback_service import FeedbackCommand
from music_discovery.domain.enums import FeedbackType
from tests.support.world import QUERY, World


def walk(model: BaseModel) -> Iterator[object]:
    """Every value nested in a DTO."""
    for value in model.__dict__.values():
        yield value
        items = value if isinstance(value, list | tuple) else [value]
        if isinstance(value, dict):
            items = list(value.values())
        for item in items:
            if isinstance(item, BaseModel):
                yield from walk(item)


def assert_api_only(model: BaseModel) -> None:
    assert isinstance(model, s.ApiModel)
    for value in walk(model):
        if isinstance(value, BaseModel):
            assert isinstance(value, s.ApiModel), f"{type(value).__name__} leaked into a DTO"
    # the wire form re-validates into the same DTO
    assert type(model).model_validate_json(model.model_dump_json()) == model


def test_search_response_maps_every_result_and_keeps_nulls() -> None:
    world = World()
    dto = mapping.search_response(world.search.search(QUERY, session_id=None, limit=8))
    assert_api_only(dto)
    wire = dto.model_dump(mode="json")
    assert wire["outcome"] == "ok"
    assert wire["capabilities"] == {
        "semantic": "available",
        "llm_interpreter": "disabled",
        "map": "available",
    }
    by_id = {r["track_id"]: r for r in wire["results"]}
    tape = by_id["trk_tape"]  # metadata-only, no audio, no map point, no source page
    assert tape["preview_url"] is None
    assert tape["spatial"] is None
    assert tape["source_url"] is None
    assert tape["audio_available"] is False
    assert tape["evidence_status"] == "metadata_only"
    assert tape["score_breakdown"]["semantic"] is None
    sound = by_id["trk_sound"]
    assert sound["preview_url"] == "/api/tracks/trk_sound/audio"
    assert sound["source_url"] == "https://freemusicarchive.org/t/1"
    assert sound["spatial"]["projection_version"] == "umap-test"
    assert sound["evidence_status"] == "audio_and_metadata"
    assert sound["artists"] == [{"artist_id": "art_trk_sound", "name": "Artist trk_sound"}]
    assert "discogs_url" not in sound  # ADR-0005
    assert wire["interpreted_query"]["original_query"] == QUERY
    assert all(0.0 <= r["score"] <= 1.0 for r in wire["results"])


def test_degraded_search_maps_capabilities_and_warnings() -> None:
    world = World(semantic=False, projection_available=False)
    wire = mapping.search_response(world.search.search(QUERY, session_id=None, limit=5)).model_dump(
        mode="json"
    )
    assert wire["capabilities"]["semantic"] == "unavailable"
    assert wire["capabilities"]["map"] == "unavailable"
    assert [w["code"] for w in wire["warnings"]] == ["semantic_unavailable", "map_unavailable"]
    assert all(r["spatial"] is None for r in wire["results"])


def test_track_detail_neighbors_feedback_session_and_map_mapping() -> None:
    world = World()
    detail = mapping.track_detail(world.track_service.get("trk_both"))
    assert_api_only(detail)
    assert detail.release == s.Release(release_id="rel_garden", title="Garden Sessions", year=2011)
    assert detail.year is None
    assert detail.audio is not None
    assert detail.audio.license

    no_audio = mapping.track_detail(world.track_service.get("trk_tape"))
    assert (no_audio.audio, no_audio.preview_url, no_audio.spatial, no_audio.release) == (
        None,
        None,
        None,
        None,
    )

    neighbors = mapping.neighbors_response(world.track_service.neighbors("trk_night", 2))
    assert_api_only(neighbors)
    assert neighbors.metric == "clap_cosine"
    assert neighbors.reason is None

    first = world.search.search(QUERY, session_id=None, limit=5)
    assert first.query_id is not None
    result = world.feedback.submit(
        FeedbackCommand(
            session_id=first.session.session_id,
            query_id=first.query_id,
            event_type=FeedbackType.NOT_RELEVANT,
            track_id=first.items[0].view.track.id,
            refresh=True,
        )
    )
    feedback = mapping.feedback_response(result)
    assert_api_only(feedback)
    assert feedback.model_dump(mode="json")["next_action"] == "REFINE_SEARCH"
    assert feedback.refreshed is not None

    session = mapping.session_response(result.session)
    assert_api_only(session)
    wire = session.model_dump(mode="json")
    assert [t["triggered_by_event_id"] is None for t in wire["turns"]] == [True, False]
    assert wire["feedback"][0]["event_type"] == "NOT_RELEVANT"

    page = mapping.map_points(world.map.list_points(limit=3))
    assert_api_only(page)
    assert page.next_cursor == page.points[-1].track_id
    meta = mapping.map_meta(world.map.meta())
    assert meta.status == "available"
    down = mapping.map_meta(World(projection_available=False).map.meta())
    assert (down.status, down.reason, down.bounds) == (
        "unavailable",
        "projection_unavailable",
        None,
    )
    with pytest.raises(ValueError, match="unavailable"):
        mapping.map_points(World(projection_available=False).map.list_points())

    health = mapping.health(world.capabilities.current())
    assert health.api_version == s.API_VERSION


EXAMPLES = build_examples()


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_example_validates_against_its_dto(name: str) -> None:
    example = EXAMPLES[name]
    assert_api_only(example)
    schema_examples = type(example).model_json_schema().get("examples", [])
    assert example.model_dump(mode="json") in schema_examples


def test_examples_cover_every_outcome_and_degraded_variant() -> None:
    searches = [e for e in EXAMPLES.values() if isinstance(e, s.SearchResponse)]
    assert {e.outcome for e in searches} == {"ok", "no_confident_match", "needs_clarification"}
    assert any(not e.results and e.outcome == "ok" for e in searches)  # empty plate
    codes = {w.code for e in searches for w in e.warnings}
    assert {"semantic_unavailable", "llm_fallback"} <= codes
    assert any(
        c.status == "unknown" for e in searches for r in e.results for c in r.constraint_status
    )
    neighbors: list[Any] = [e for e in EXAMPLES.values() if isinstance(e, s.NeighborsResponse)]
    assert {n.metric for n in neighbors} == {"clap_cosine", "catalog_relationship"}
    errors = {e.error.code for e in EXAMPLES.values() if isinstance(e, s.ErrorResponse)}
    assert {"validation_error", "track_not_found", "projection_unavailable"} <= errors


def test_examples_are_fictional_placeholders() -> None:
    for example in EXAMPLES.values():
        text = example.model_dump_json()
        assert "http://" not in text
        assert "https://" not in text
        for value in walk(example):
            if isinstance(value, str) and value.startswith(("trk_", "art_", "rel_")):
                assert "_example_" in value
