from __future__ import annotations

from datetime import UTC, datetime

import pytest

from music_discovery.application.map_service import MAX_LIMIT, MapFilters, MapService
from music_discovery.domain.enums import DataSource
from music_discovery.domain.errors import ProjectionMismatch, ProjectionMissing
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.domain.schemas import ProjectionArtifact, ProjectionMeta
from music_discovery.spatial.spatial_repository import ProjectionSpatialRepository
from tests.fakes import InMemoryTrackRepository

GENRES = ["Rock", "Electronic", "Folk"]


def track(i: int) -> Track:
    return Track(
        id=f"trk_{i:03d}",
        title=f"Song {i}",
        artists=[ArtistReference(artist_id=f"art_{i % 4}", name=f"Artist {i % 4}")],
        genres=[GENRES[i % 3]],
        styles=["Ambient"] if i % 5 == 0 else [],
        source_url=f"https://freemusicarchive.org/track/{i}" if i % 2 else None,
        provenance=Provenance(source=DataSource.FMA),
    )


N = 30
TRACKS = [track(i) for i in range(N)]
PROJECTED = TRACKS[:25]  # the last 5 have no audio embedding


def spatial() -> ProjectionSpatialRepository:
    ids = [t.id for t in PROJECTED]
    coords = [(i / 10 - 1.0, 1.0 - i / 20) for i in range(len(ids))]
    meta = ProjectionMeta(
        projection_version="umap-test",
        embedding_version="ev-1",
        model_id="fake-clap-v1",
        umap_requested={},
        umap_effective={},
        random_state=42,
        package_versions={},
        created_at=datetime(2026, 10, 25, tzinfo=UTC),
        n_points=len(ids),
        excluded_tracks=5,
        coordinates_sha256="x" * 64,
    )
    return ProjectionSpatialRepository(
        ProjectionArtifact(meta=meta, track_ids=ids, coordinates=coords)
    )


@pytest.fixture
def service() -> MapService:
    repo = InMemoryTrackRepository()
    for t in TRACKS:
        repo.upsert(t)
    return MapService(repo, spatial())


def test_pagination_is_stable_and_complete(service: MapService) -> None:
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        page = service.list_points(limit=7, cursor=cursor)
        pages += 1
        assert page.status == "available"
        assert page.projection_version == "umap-test"
        assert len(page.points) <= 7
        seen.extend(p.track_id for p in page.points)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert pages == 4
    assert seen == sorted(t.id for t in PROJECTED)
    assert service.list_points(limit=7, cursor="trk_006").points[0].track_id == "trk_007"
    assert service.list_points(limit=25).next_cursor is None


def test_points_carry_display_fields_and_keep_nulls(service: MapService) -> None:
    points = {p.track_id: p for p in service.list_points().points}
    first, odd = points["trk_000"], points["trk_001"]
    assert (first.x, first.y) == (-1.0, 1.0)
    assert first.title == "Song 0"
    assert first.artist == "Artist 0"
    assert first.genre == "Rock"
    assert first.style == "Ambient"
    assert first.source_url is None  # not fabricated
    assert odd.style is None
    assert odd.source_url == "https://freemusicarchive.org/track/1"
    assert all(p.has_audio for p in points.values())


def test_no_embeddings_in_output(service: MapService) -> None:
    dumped = service.list_points().model_dump()
    assert set(dumped["points"][0]) == {
        "track_id", "x", "y", "title", "artist", "genre", "style", "source_url", "has_audio",
    }  # fmt: skip


def test_filters(service: MapService) -> None:
    def ids(**kw: object) -> list[str]:
        return [p.track_id for p in service.list_points(MapFilters.model_validate(kw)).points]

    assert ids(genre="electronic") == [t.id for t in PROJECTED if t.genres == ["Electronic"]]
    assert ids(style="Ambient") == ["trk_000", "trk_005", "trk_010", "trk_015", "trk_020"]
    assert ids(artist_id="art_3") == [t.id for t in PROJECTED if t.artists[0].artist_id == "art_3"]
    assert ids(genre="Rock", style="Ambient") == ["trk_000", "trk_015"]
    assert len(ids(has_audio=True)) == 25
    assert ids(has_audio=False) == []
    assert ids(genre="Jazz") == []


def test_filtered_pagination_covers_every_match(service: MapService) -> None:
    filters = MapFilters(genre="Folk")
    first = service.list_points(filters, limit=3)
    second = service.list_points(filters, limit=3, cursor=first.next_cursor)
    third = service.list_points(filters, limit=3, cursor=second.next_cursor)
    got = [p.track_id for page in (first, second, third) for p in page.points]
    assert got == [t.id for t in PROJECTED if t.genres == ["Folk"]]
    assert third.next_cursor is None


def test_limit_is_bounded(service: MapService) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        service.list_points(limit=0)
    assert len(service.list_points(limit=MAX_LIMIT * 10).points) == 25


def test_meta_reports_bounds_counts_and_version(service: MapService) -> None:
    meta = service.meta()
    assert meta.status == "available"
    assert meta.projection_version == "umap-test"
    assert meta.embedding_version == "ev-1"
    assert meta.n_points == 25
    assert meta.excluded_tracks == 5
    assert meta.bounds is not None
    assert (meta.bounds.min_x, meta.bounds.max_x) == (-1.0, pytest.approx(1.4))
    assert (meta.bounds.min_y, meta.bounds.max_y) == (pytest.approx(-0.2), 1.0)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ProjectionMissing("no projection"), "projection_unavailable"),
        (ProjectionMismatch("stale"), "projection_mismatch"),
    ],
)
def test_unavailable_projection_is_a_status_not_an_exception(error: Exception, code: str) -> None:
    def load() -> ProjectionSpatialRepository:
        raise error

    service = MapService.from_loader(InMemoryTrackRepository(), load)
    assert not service.available
    page = service.list_points()
    assert (page.status, page.reason, page.points, page.next_cursor) == (
        "unavailable",
        code,
        [],
        None,
    )
    meta = service.meta()
    assert (meta.status, meta.reason, meta.bounds, meta.projection_version) == (
        "unavailable",
        code,
        None,
        None,
    )


def test_loader_success_makes_map_available() -> None:
    service = MapService.from_loader(InMemoryTrackRepository(), spatial)
    assert service.available
    assert MapService(InMemoryTrackRepository(), None).meta().reason == "projection_unavailable"
