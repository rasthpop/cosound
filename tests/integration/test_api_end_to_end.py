"""End to end through the real composition root (`create_app(settings)`).

SQLite repositories, the NumPy cosine index over a persisted embedding version, BM25, the file
projection store and real audio files. Only the CLAP model is replaced by the hashed-vector
fake encoder (same model id as the stored embeddings), so no checkpoint is needed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from music_discovery.api import dependencies
from music_discovery.api.app import create_app
from music_discovery.infrastructure.settings import Settings
from tests.fakes import FakeEncoder
from tests.support.seed import MODEL, seed
from tests.support.world import AUDIO_BYTES, DIM, EMBEDDED, QUERY, REPO


@pytest.fixture
def client(
    make_settings: Callable[..., Settings], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    checkpoint = tmp_path / "clap-checkpoint"
    checkpoint.mkdir()
    settings = make_settings(
        project_root=REPO, clap_checkpoint=checkpoint, clap_model_version=MODEL
    )
    seed(settings, projection=True, audio=True)
    monkeypatch.setattr(
        dependencies, "ClapEncoder", lambda path, model_id: FakeEncoder(dim=DIM, model_id=model_id)
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_full_flow_against_the_real_stack(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["capabilities"] == {
        "semantic": "available",
        "llm_interpreter": "disabled",
        "map": "available",
    }

    plate: dict[str, Any] = client.post("/api/search", json={"query": QUERY, "limit": 6}).json()
    assert plate["outcome"] == "ok"
    ids = [r["track_id"] for r in plate["results"]]
    assert {"trk_sound", "trk_both"} <= set(ids)
    sound = next(r for r in plate["results"] if r["track_id"] == "trk_sound")
    assert sound["score_breakdown"]["semantic"] is not None
    assert sound["spatial"]["projection_version"] == "umap-seeded"
    assert sound["preview_url"] == "/api/tracks/trk_sound/audio"

    detail = client.get("/api/tracks/trk_both").json()
    assert detail["release"]["title"] == "Garden Sessions"
    neighbors = client.get("/api/tracks/trk_night/neighbors", params={"k": 2}).json()
    assert neighbors["metric"] == "clap_cosine"
    assert neighbors["neighbors"][0]["track_id"] == "trk_bus"

    clip = client.get(sound["preview_url"], headers={"Range": "bytes=0-2"})
    assert clip.status_code == 206
    assert clip.content == AUDIO_BYTES[:3]

    top = ids[0]
    refined = client.post(
        "/api/feedback",
        json={
            "session_id": plate["session_id"],
            "query_id": plate["query_id"],
            "event_type": "NOT_RELEVANT",
            "track_id": top,
            "refresh": True,
        },
    ).json()
    assert refined["accepted"] is True
    assert top not in [r["track_id"] for r in refined["refreshed"]["results"]]

    session = client.get(f"/api/sessions/{plate['session_id']}").json()
    assert len(session["turns"]) == 2  # persisted in SQLite
    assert session["feedback"][0]["track_id"] == top

    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/map/points", params=params).json()
        seen += [p["track_id"] for p in page["points"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == sorted(EMBEDDED)
    meta = client.get("/api/map/meta").json()
    assert (meta["status"], meta["n_points"]) == ("available", len(EMBEDDED))
