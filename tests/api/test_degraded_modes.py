"""Robustness: every base.md §17 "API tests" bullet has at least one test.

| §17 bullet                   | where                                                        |
|------------------------------|--------------------------------------------------------------|
| request and response schemas | test_search.py, test_tracks.py, test_fixtures_valid.py       |
| invalid input handling       | test_search.py::test_invalid_input…, test_feedback.py (422)  |
| empty results                | test_search.py::test_empty_results…                          |
| missing audio                | test_search.py::test_metadata_only…, test_audio.py           |
| agent failures               | this file (LLM invalid / hallucinating / down, CLAP failure) |
| invalid track ids            | test_tracks.py::test_invalid_track_id_is_404                 |
| feedback validation          | test_feedback.py, this file (stale / duplicate)              |
| map pagination               | test_map.py::test_pagination_walk…                           |
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from music_discovery.domain.errors import StaleSessionVersion
from tests.api.conftest import ClientFactory
from tests.support.drafts import flute_draft
from tests.support.world import QUERY


def search(client: TestClient, **body: Any) -> Any:
    return client.post("/api/search", json={"query": QUERY, **body})


@pytest.mark.parametrize("llm_error", ["invalid_output", "rate_limited", "timeout", "circuit_open"])
def test_llm_failure_falls_back_with_200(make_client: ClientFactory, llm_error: str) -> None:
    response = search(make_client(llm_responses=[llm_error]))
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "ok"
    assert body["results"]
    assert body["interpreted_query"]["interpreter"] == "deterministic"
    assert body["capabilities"]["llm_interpreter"] == "fallback"
    assert [w["code"] for w in body["warnings"]] == ["llm_fallback"]


def test_hallucinated_llm_references_are_not_trusted(make_client: ClientFactory) -> None:
    invented = flute_draft().model_copy(update={"reference_track_ids": ["trk_invented"]})
    body = search(make_client(llm_responses=[invented])).json()
    assert body["outcome"] == "ok"
    assert "trk_invented" not in body["interpreted_query"]["reference_track_ids"]


def test_llm_success_is_reported_as_used(make_client: ClientFactory) -> None:
    body = search(make_client(llm_responses=[flute_draft()])).json()
    assert body["interpreted_query"]["interpreter"] == "llm"
    assert body["capabilities"]["llm_interpreter"] == "used"
    assert body["warnings"] == []


def test_clap_load_failure_gives_metadata_only_results_with_warning(
    make_client: ClientFactory,
) -> None:
    response = search(make_client(encoder_fails=True))
    assert response.status_code == 200
    body = response.json()
    assert body["results"]
    assert all(r["score_breakdown"]["semantic"] is None for r in body["results"])
    assert body["capabilities"]["semantic"] == "unavailable"
    assert [w["code"] for w in body["warnings"]] == ["semantic_unavailable"]


def test_duplicate_feedback_is_idempotent(client: TestClient) -> None:
    plate = search(client, limit=6).json()
    top = plate["results"][0]["track_id"]
    event = {
        "session_id": plate["session_id"],
        "query_id": plate["query_id"],
        "event_type": "NOT_RELEVANT",
        "track_id": top,
    }
    first = client.post("/api/feedback", json=event).json()
    again = client.post("/api/feedback", json=event).json()
    assert first["next_action"] == "REFINE_SEARCH"
    assert again["accepted"] is True
    assert again["next_action"] == "NONE"  # nothing changed, so no new search
    assert again["change_summary"] == []
    excluded = again["updated_search_state"]["interpreted_query"]["excluded_track_ids"]
    assert excluded.count(top) == 1


def test_stale_session_update_is_a_409(make_client: ClientFactory) -> None:
    client = make_client()
    plate = search(client).json()
    world = client.app.state.world  # type: ignore[attr-defined]

    def concurrent_save(*args: object, **kwargs: object) -> None:
        raise StaleSessionVersion("session changed since it was read")

    world.sessions.save = concurrent_save
    response = client.post(
        "/api/feedback",
        json={
            "session_id": plate["session_id"],
            "query_id": plate["query_id"],
            "event_type": "NOT_RELEVANT",
            "track_id": plate["results"][0]["track_id"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_session_version"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/search", {"query": QUERY, "limit": 10_000}),
        ("get", "/api/map/points?limit=100000", None),
        ("get", "/api/tracks/trk_night/neighbors?k=1000", None),
    ],
)
def test_large_limits_are_rejected(
    client: TestClient, method: str, path: str, payload: dict[str, Any] | None
) -> None:
    response = client.request(method.upper(), path, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_search_keeps_working_with_everything_optional_down(make_client: ClientFactory) -> None:
    client = make_client(semantic=False, projection_available=False, llm_responses=["timeout"])
    body = search(client).json()
    assert body["outcome"] == "ok"
    assert body["results"]
    assert {w["code"] for w in body["warnings"]} == {
        "semantic_unavailable",
        "llm_fallback",
        "map_unavailable",
    }
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
