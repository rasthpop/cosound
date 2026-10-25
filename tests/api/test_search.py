from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.schemas import SearchResponse
from tests.api.conftest import ClientFactory
from tests.support.world import QUERY


def post(client: TestClient, **body: object) -> dict:  # type: ignore[type-arg]
    response = client.post("/api/search", json={"query": QUERY, **body})
    return {"status": response.status_code, **response.json()}


def test_search_returns_a_valid_plate(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": QUERY, "limit": 6})
    assert response.status_code == 200
    body = SearchResponse.model_validate(response.json())
    assert body.outcome == "ok"
    assert body.query_id is not None
    assert 1 <= len(body.results) <= 6
    assert [r.rank for r in body.results] == list(range(1, len(body.results) + 1))
    assert body.capabilities.semantic == "available"
    assert body.warnings == []
    first = body.results[0]
    assert first.description is None or first.description.strip()
    assert body.interpreted_query.original_query == QUERY


def test_follow_up_in_the_same_session(client: TestClient) -> None:
    first = post(client)
    second = post(client, query="more electronic", session_id=first["session_id"])
    assert second["status"] == 200
    assert second["session_id"] == first["session_id"]
    assert second["query_id"] != first["query_id"]
    assert second["change_summary"]


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "x" * 501},
        {"query": QUERY, "limit": 0},
        {"query": QUERY, "limit": 101},
        {"query": QUERY, "limit": "many"},
        {"limit": 5},
        {"query": QUERY, "unexpected": True},
    ],
)
def test_invalid_input_is_a_422_envelope(client: TestClient, body: dict) -> None:  # type: ignore[type-arg]
    response = client.post("/api/search", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_blank_query_is_rejected(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"field": "query"}


def test_unknown_session_is_404(client: TestClient) -> None:
    body = post(client, session_id="ses_nope")
    assert body["status"] == 404
    assert body["error"]["code"] == "session_not_found"


def test_metadata_only_results_keep_nulls(client: TestClient) -> None:
    results = {r["track_id"]: r for r in post(client, limit=10)["results"]}
    tape = results["trk_tape"]
    assert tape["audio_available"] is False
    assert tape["evidence_status"] == "metadata_only"
    assert tape["preview_url"] is None
    assert tape["spatial"] is None
    assert tape["score_breakdown"]["semantic"] is None


def test_semantic_unavailable_still_answers_with_a_warning(make_client: ClientFactory) -> None:
    body = post(make_client(semantic=False))
    assert body["status"] == 200
    assert body["outcome"] == "ok"
    assert body["results"]
    assert body["capabilities"]["semantic"] == "unavailable"
    assert [w["code"] for w in body["warnings"]] == ["semantic_unavailable"]
    assert all(r["score_breakdown"]["semantic"] is None for r in body["results"])


def test_needs_clarification(client: TestClient) -> None:
    body = post(client, query="no vocals with female vocals")
    assert body["status"] == 200
    assert body["outcome"] == "needs_clarification"
    assert body["clarification_question"]
    assert body["results"] == []


def test_no_confident_match(client: TestClient) -> None:
    body = post(client, query="only jazz")
    assert body["status"] == 200
    assert body["outcome"] == "no_confident_match"
    assert body["results"] == []
    assert body["no_match_reasons"]


def test_empty_results_are_a_valid_response(make_client: ClientFactory) -> None:
    # metadata-only search for words no track has: an OK outcome with an empty plate
    body = post(make_client(semantic=False), query="zzqx blorf")
    assert body["status"] == 200
    SearchResponse.model_validate({k: v for k, v in body.items() if k != "status"})
    assert body["outcome"] == "ok"
    assert body["results"] == []
