from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.schemas import NeighborsResponse, TrackDetail
from tests.api.conftest import ClientFactory


def test_track_detail(client: TestClient) -> None:
    response = client.get("/api/tracks/trk_both")
    assert response.status_code == 200
    body = TrackDetail.model_validate(response.json())
    assert body.title == "Flute Garden"
    assert body.release is not None
    assert body.release.title == "Garden Sessions"
    assert body.preview_url == "/api/tracks/trk_both/audio"
    assert body.audio is not None
    assert body.spatial is not None


def test_track_without_audio_has_nulls(client: TestClient) -> None:
    body = client.get("/api/tracks/trk_tape").json()
    assert body["audio"] is None
    assert body["preview_url"] is None
    assert body["spatial"] is None
    assert body["release"] is None
    assert body["evidence_status"] == "metadata_only"


def test_related_tracks_are_catalog_context(client: TestClient) -> None:
    body = client.get("/api/tracks/trk_night").json()
    assert body["related_tracks"] == [
        {
            "track_id": "trk_bus",
            "title": "Night Bus",
            "artists": [{"artist_id": "art_nocturne", "name": "Artist nocturne"}],
            "relationship_type": "same_artist",
        }
    ]
    assert body["relationship_counts"] == {"same_artist": 1}


@pytest.mark.parametrize("path", ["/api/tracks/trk_nope", "/api/tracks/trk_nope/neighbors"])
def test_invalid_track_id_is_404(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "track_not_found"
    assert response.json()["error"]["details"] == {"track_id": "trk_nope"}


def test_neighbors_use_original_space(client: TestClient) -> None:
    response = client.get("/api/tracks/trk_night/neighbors", params={"k": 3})
    assert response.status_code == 200
    body = NeighborsResponse.model_validate(response.json())
    assert body.metric == "clap_cosine"
    assert body.reason is None
    assert len(body.neighbors) == 3
    assert body.neighbors[0].track_id == "trk_bus"
    assert all(n.track_id != "trk_night" for n in body.neighbors)


def test_neighbors_of_a_track_without_audio(client: TestClient) -> None:
    body = client.get("/api/tracks/trk_tape/neighbors").json()
    assert body["metric"] == "catalog_relationship"
    assert body["reason"] == "no_audio_embedding"
    assert body["neighbors"] == []


def test_neighbors_when_semantic_is_down(make_client: ClientFactory) -> None:
    body = make_client(semantic=False).get("/api/tracks/trk_night/neighbors").json()
    assert body["reason"] == "semantic_unavailable"
    assert [n["track_id"] for n in body["neighbors"]] == ["trk_bus"]
    assert body["neighbors"][0]["score"] is None  # unknown weight is not 0


@pytest.mark.parametrize("k", [0, 51, "lots"])
def test_neighbor_k_bounds(client: TestClient, k: object) -> None:
    response = client.get("/api/tracks/trk_night/neighbors", params={"k": k})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
