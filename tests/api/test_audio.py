from __future__ import annotations

from fastapi.testclient import TestClient

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import TrackAudio
from tests.support.world import AUDIO_BYTES


def test_valid_track_streams_its_clip(client: TestClient) -> None:
    response = client.get("/api/tracks/trk_sound/audio")
    assert response.status_code == 200
    assert response.content == AUDIO_BYTES
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["x-audio-license"] == "Attribution 4.0 International"


def test_range_request_returns_206(client: TestClient) -> None:
    response = client.get("/api/tracks/trk_sound/audio", headers={"Range": "bytes=10-19"})
    assert response.status_code == 206
    assert response.content == AUDIO_BYTES[10:20]
    assert response.headers["content-range"] == f"bytes 10-19/{len(AUDIO_BYTES)}"


def test_track_without_audio_is_a_404_envelope(client: TestClient) -> None:
    response = client.get("/api/tracks/trk_tape/audio")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "audio_missing"
    unknown = client.get("/api/tracks/trk_nope/audio")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "track_not_found"


def test_path_traversal_is_impossible(client: TestClient) -> None:
    world = client.app.state.world  # type: ignore[attr-defined]
    outside = world.data_dir.parent / "private.mp3"
    outside.write_bytes(b"private")
    world.audio.upsert(
        TrackAudio(track_id="trk_bus", source=DataSource.FMA, file_path="../private.mp3")
    )
    response = client.get("/api/tracks/trk_bus/audio")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "audio_missing"
    assert "private" not in response.text
    # the id itself never becomes a path
    sneaky = client.get("/api/tracks/..%2F..%2Fprivate.mp3/audio")
    assert sneaky.status_code == 404
    assert sneaky.content != b"private"


def test_preview_url_points_to_the_endpoint_only_when_audio_exists(client: TestClient) -> None:
    results = {
        r["track_id"]: r
        for r in client.post(
            "/api/search", json={"query": "calm flute melody", "limit": 10}
        ).json()["results"]
    }
    assert results["trk_sound"]["preview_url"] == "/api/tracks/trk_sound/audio"
    assert client.get(results["trk_sound"]["preview_url"]).status_code == 200
    assert results["trk_tape"]["preview_url"] is None
