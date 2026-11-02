from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.schemas import FeedbackResponse, SessionResponse
from tests.support.world import QUERY


def search(client: TestClient, limit: int = 6) -> dict[str, Any]:
    body: dict[str, Any] = client.post("/api/search", json={"query": QUERY, "limit": limit}).json()
    return body


def feedback(client: TestClient, plate: dict[str, Any], **body: Any) -> Any:
    payload = {"session_id": plate["session_id"], "query_id": plate["query_id"], **body}
    return client.post("/api/feedback", json=payload)


def test_refresh_changes_results(client: TestClient) -> None:
    plate = search(client)
    top = plate["results"][0]["track_id"]
    response = feedback(client, plate, event_type="NOT_RELEVANT", track_id=top, refresh=True)
    assert response.status_code == 200
    body = FeedbackResponse.model_validate(response.json())
    assert body.accepted
    assert body.next_action == "REFINE_SEARCH"
    assert body.change_summary
    assert top in body.updated_search_state.interpreted_query.excluded_track_ids
    assert body.refreshed is not None
    assert top not in [r.track_id for r in body.refreshed.results]
    assert body.refreshed.query_id != plate["query_id"]


def test_attribute_feedback_without_refresh(client: TestClient) -> None:
    plate = search(client)
    body = feedback(
        client, plate, event_type="MORE_OF_ATTRIBUTE", attribute="electronic", value=True
    ).json()
    assert body["accepted"] is True
    assert body["refreshed"] is None
    assert body["updated_search_state"]["interpreted_query"]["original_query"] == QUERY


def test_select_track_from_the_map(client: TestClient) -> None:
    plate = search(client, limit=3)
    shown = {r["track_id"] for r in plate["results"]}
    outside = next(t for t in ("trk_night", "trk_bus", "trk_fill0") if t not in shown)
    body = feedback(client, plate, event_type="SELECT_TRACK", track_id=outside).json()
    assert body["accepted"] is True
    assert body["next_action"] == "SHOW_DETAILS"
    assert body["refreshed"] is None


def test_free_text_feedback(client: TestClient) -> None:
    plate = search(client)
    ok = feedback(client, plate, free_text="more electronic", refresh=True).json()
    assert ok["accepted"] is True
    assert ok["refreshed"] is not None
    rejected = feedback(client, search(client), free_text="the weather is lovely").json()
    assert rejected["accepted"] is False
    assert rejected["reason"]


def test_unknown_session(client: TestClient) -> None:
    response = client.post(
        "/api/feedback",
        json={"session_id": "ses_nope", "query_id": "qry_x", "event_type": "NOT_RELEVANT",
              "track_id": "trk_sound"},
    )  # fmt: skip
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_unknown_query_is_409(client: TestClient) -> None:
    plate = search(client)
    plate = {**plate, "query_id": "qry_nope"}
    response = feedback(client, plate, event_type="NOT_RELEVANT", track_id="trk_sound")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "query_not_in_session"


def test_unknown_track_is_404(client: TestClient) -> None:
    response = feedback(client, search(client), event_type="SELECT_TRACK", track_id="trk_nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "track_not_found"


def test_track_not_in_results_is_409(client: TestClient) -> None:
    plate = search(client, limit=3)
    shown = {r["track_id"] for r in plate["results"]}
    outside = next(t for t in ("trk_night", "trk_bus", "trk_fill0") if t not in shown)
    response = feedback(client, plate, event_type="NOT_RELEVANT", track_id=outside)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "track_not_in_results"


@pytest.mark.parametrize(
    "body",
    [
        {"event_type": "MAKE_IT_POP", "track_id": "trk_sound"},
        {"event_type": "MORE_OF_ATTRIBUTE"},
        {"event_type": "NOT_RELEVANT"},
        {},
        {"free_text": "x" * 501},
        {"event_type": "NOT_RELEVANT", "track_id": "trk_sound", "limit": 1000},
    ],
)
def test_malformed_feedback_is_422(client: TestClient, body: dict[str, Any]) -> None:
    response = feedback(client, search(client), **body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"validation_error", "invalid_feedback_event"}


def test_history_is_visible_in_the_session(client: TestClient) -> None:
    plate = search(client)
    top = plate["results"][0]["track_id"]
    feedback(client, plate, event_type="NOT_RELEVANT", track_id=top)
    response = client.get(f"/api/sessions/{plate['session_id']}")
    assert response.status_code == 200
    session = SessionResponse.model_validate(response.json())
    assert session.original_query == QUERY
    assert session.turns[0].query_id == plate["query_id"]
    assert len(session.turns) == 2
    assert session.turns[1].triggered_by_event_id == session.feedback[0].event_id
    assert session.turns[1].change_summary
    assert session.feedback[0].event_type == "NOT_RELEVANT"
    assert session.feedback[0].track_id == top


def test_unknown_session_lookup_is_404(client: TestClient) -> None:
    response = client.get("/api/sessions/ses_nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"
