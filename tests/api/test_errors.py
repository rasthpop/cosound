"""Error envelope, status mapping, request ids, and startup with optional parts missing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.app import REQUEST_ID_HEADER, create_app
from music_discovery.api.errors import STATUS_BY_CODE, status_for
from music_discovery.domain import errors as domain_errors
from music_discovery.domain.errors import MusicDiscoveryError
from music_discovery.infrastructure.settings import Settings
from tests.support.seed import MODEL, seed
from tests.support.world import REPO

ERROR_CLASSES = sorted(
    (
        cls
        for cls in vars(domain_errors).values()
        if isinstance(cls, type) and issubclass(cls, MusicDiscoveryError)
    ),
    key=lambda cls: cls.__name__,
)
EXPECTED = {
    "validation_error": 422,
    "invalid_feedback_event": 422,
    "contradictory_constraints": 422,
    "invalid_constraint": 422,
    "track_not_found": 404,
    "session_not_found": 404,
    "not_found": 404,
    "audio_missing": 404,
    "track_not_in_results": 409,
    "query_not_in_session": 409,
    "stale_session_version": 409,
    "projection_unavailable": 503,
    "projection_mismatch": 503,
}


def raising_client(client: TestClient) -> TestClient:
    app = client.app

    def boom(name: str) -> None:
        if name == "unexpected":
            raise RuntimeError("secret internal detail")
        cls = getattr(domain_errors, name)
        raise cls(f"{name} happened", details={"track_id": "trk_x", "items": [1, "a"]})

    def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    app.add_api_route("/api/_raise/{name}", boom, methods=["GET"])  # type: ignore[attr-defined]
    app.add_api_route("/api/_int", needs_int, methods=["GET"])  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize("cls", ERROR_CLASSES, ids=lambda c: c.__name__)
def test_every_domain_error_maps_to_a_status_and_envelope(
    client: TestClient, cls: type[MusicDiscoveryError]
) -> None:
    response = raising_client(client).get(f"/api/_raise/{cls.__name__}")
    expected = EXPECTED.get(cls.code, 404 if cls.code.endswith("_not_found") else 500)
    assert response.status_code == expected
    error = response.json()["error"]
    assert set(response.json()) == {"error"}
    if expected == 500:  # unmapped: generic, nothing internal leaks
        assert error == {
            "code": "internal_error",
            "message": "Something went wrong.",
            "details": {},
        }
    else:
        assert error["code"] == cls.code
        assert error["message"] == f"{cls.__name__} happened"
        assert error["details"] == {"track_id": "trk_x", "items": [1, "a"]}


def test_status_table_matches_the_contract() -> None:
    assert {k: v for k, v in STATUS_BY_CODE.items() if k in EXPECTED} == EXPECTED
    assert status_for("something_not_found") == 404
    assert status_for("brand_new_code") == 500


def test_request_validation_uses_the_envelope(client: TestClient) -> None:
    response = raising_client(client).get("/api/_int", params={"n": "seven"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["errors"][0]["loc"] == "query.n"


def test_unknown_route_and_unexpected_errors_use_the_envelope(client: TestClient) -> None:
    missing = client.get("/api/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    crash = raising_client(client).get("/api/_raise/unexpected")
    assert crash.status_code == 500
    assert "secret" not in crash.text
    assert crash.json()["error"]["code"] == "internal_error"


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    echoed = client.get("/api/health", headers={REQUEST_ID_HEADER: "abc-123"})
    assert echoed.headers[REQUEST_ID_HEADER] == "abc-123"
    generated = client.get("/api/health")
    assert len(generated.headers[REQUEST_ID_HEADER]) == 32


def test_cors_allows_the_configured_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_health_reports_capabilities(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["capabilities"] == {
        "semantic": "available",
        "llm_interpreter": "disabled",
        "map": "available",
    }


# --- Real composition root -------------------------------------------------------------


def real_app(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_app_starts_with_clap_checkpoint_missing(
    make_settings: Callable[..., Settings], tmp_path: Path
) -> None:
    settings = make_settings(
        project_root=REPO, clap_checkpoint=tmp_path / "no-such-checkpoint", clap_model_version=MODEL
    )
    seed(settings, projection=True)
    with real_app(settings) as client:
        health = client.get("/api/health").json()
        assert health["capabilities"]["semantic"] == "unavailable"
        assert health["semantic_reason"] == "clap_checkpoint_missing"
        assert health["capabilities"]["map"] == "available"


def test_app_starts_with_projection_missing(
    make_settings: Callable[..., Settings], tmp_path: Path
) -> None:
    settings = make_settings(
        project_root=REPO, clap_checkpoint=tmp_path / "missing", clap_model_version=MODEL
    )
    seed(settings, projection=False)
    with real_app(settings) as client:
        health = client.get("/api/health").json()
        assert health["capabilities"]["map"] == "unavailable"
        assert health["map_reason"] == "projection_unavailable"


def test_app_starts_on_an_empty_installation(make_settings: Callable[..., Settings]) -> None:
    with real_app(make_settings(project_root=REPO, clap_checkpoint=None)) as client:
        health = client.get("/api/health").json()
        assert health["capabilities"]["semantic"] == "unavailable"
        assert health["semantic_reason"] == "embeddings_unavailable"
        assert health["capabilities"]["map"] == "unavailable"
