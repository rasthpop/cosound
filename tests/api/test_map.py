from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.schemas import MapMetaResponse, MapPointsResponse
from tests.api.conftest import ClientFactory
from tests.support.world import EMBEDDED, QUERY


def page(client: TestClient, **params: Any) -> Any:
    return client.get("/api/map/points", params=params)


def test_pagination_walk_returns_every_point_once(client: TestClient) -> None:
    seen: list[str] = []
    cursor = None
    for _ in range(20):
        params: dict[str, Any] = {"limit": 4}
        if cursor:
            params["cursor"] = cursor
        response = page(client, **params)
        assert response.status_code == 200
        body = MapPointsResponse.model_validate(response.json())
        assert body.projection_version == "umap-test"
        assert len(body.points) <= 4
        seen += [p.track_id for p in body.points]
        cursor = body.next_cursor
        if cursor is None:
            break
    assert seen == sorted(EMBEDDED)
    assert len(seen) == len(set(seen))


def test_points_carry_no_embeddings(client: TestClient) -> None:
    point = page(client, limit=1).json()["points"][0]
    assert set(point) == {
        "track_id", "x", "y", "title", "artist", "genre", "style", "source_url", "has_audio",
    }  # fmt: skip


def test_filters(client: TestClient) -> None:
    def ids(**params: Any) -> list[str]:
        return [p["track_id"] for p in page(client, **params).json()["points"]]

    assert ids(genre="Electronic") == ["trk_bus", "trk_night"]
    assert ids(genre="electronic", artist_id="art_nocturne") == ["trk_bus", "trk_night"]
    assert ids(artist_id="art_trk_sound") == ["trk_sound"]
    assert ids(style="Ambient") == []
    assert ids(has_audio="false") == []
    assert len(ids(has_audio="true")) == len(EMBEDDED)


@pytest.mark.parametrize("limit", [0, 5001, "all"])
def test_limit_is_capped(client: TestClient, limit: object) -> None:
    response = page(client, limit=limit)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_meta(client: TestClient) -> None:
    body = MapMetaResponse.model_validate(client.get("/api/map/meta").json())
    assert body.status == "available"
    assert body.projection_version == "umap-test"
    assert body.n_points == len(EMBEDDED)
    assert body.excluded_tracks == 1
    assert body.bounds is not None


def test_meta_genres_cover_every_point(client: TestClient) -> None:
    genres = client.get("/api/map/meta").json()["genres"]
    assert genres == [
        {"genre": "Rock", "count": 6},
        {"genre": "Electronic", "count": 2},
        {"genre": "Folk", "count": 2},
        {"genre": "Punk", "count": 1},
    ]
    assert sum(g["count"] for g in genres) == len(EMBEDDED)


def test_meta_genres_count_points_without_genre_as_null(make_client: ClientFactory) -> None:
    client = make_client()
    world = client.app.state.world  # type: ignore[attr-defined]
    for tid in ("trk_fill0", "trk_fill1"):
        track = world.tracks.get(tid)
        world.tracks.upsert(track.model_copy(update={"genres": []}))
    body = MapMetaResponse.model_validate(client.get("/api/map/meta").json())
    assert [(g.genre, g.count) for g in body.genres] == [
        ("Rock", 4),
        ("Electronic", 2),
        ("Folk", 2),
        (None, 2),
        ("Punk", 1),
    ]
    assert sum(g.count for g in body.genres) == body.n_points


def test_projection_unavailable_is_503_while_search_works(make_client: ClientFactory) -> None:
    client = make_client(projection_available=False)
    points = page(client)
    assert points.status_code == 503
    assert points.json()["error"] == {
        "code": "projection_unavailable",
        "message": "The track map is not available.",
        "details": {"reason": "projection_unavailable"},
    }
    meta = client.get("/api/map/meta")
    assert meta.status_code == 200
    assert meta.json()["status"] == "unavailable"
    assert meta.json()["genres"] == []
    search = client.post("/api/search", json={"query": QUERY})
    assert search.status_code == 200
    assert search.json()["capabilities"]["map"] == "unavailable"
