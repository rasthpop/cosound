"""Map points and map metadata for the interface (base.md §13.4).

Serves persisted, validated coordinates only: UMAP never runs here, and embeddings never
leave the backend. When the projection is missing or does not match the running system, the
service reports `status="unavailable"` with the error code instead of raising, so the map
endpoints can degrade while search keeps working.

Every point belongs to the audio projection, so `has_audio` is true for all of them; tracks
without an embedding are not on the map (they are counted in `MapMeta.excluded_tracks`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from music_discovery.domain.errors import SpatialArtifactError
from music_discovery.domain.models import Track
from music_discovery.domain.protocols import TrackRepository
from music_discovery.domain.schemas import ProjectionMeta
from music_discovery.spatial.spatial_repository import ProjectionSpatialRepository

log = logging.getLogger(__name__)

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000

MapStatus = Literal["available", "unavailable"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MapFilters(_Model):
    genre: str | None = None
    style: str | None = None
    artist_id: str | None = None
    has_audio: bool | None = None


class MapPoint(_Model):
    track_id: str
    x: float
    y: float
    title: str
    artist: str | None
    genre: str | None
    """First source genre tag; `None` when the source has none."""
    style: str | None
    source_url: str | None
    has_audio: bool


class MapPage(_Model):
    status: MapStatus
    reason: str | None = None
    """Error code when unavailable (`projection_unavailable`, `projection_mismatch`, …)."""
    projection_version: str | None = None
    points: list[MapPoint] = Field(default_factory=list)
    next_cursor: str | None = None


class MapBounds(_Model):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class MapMeta(_Model):
    status: MapStatus
    reason: str | None = None
    projection_version: str | None = None
    embedding_version: str | None = None
    model_id: str | None = None
    created_at: datetime | None = None
    bounds: MapBounds | None = None
    n_points: int = 0
    excluded_tracks: int | None = None
    """Catalog tracks without an audio embedding, absent from the map. None if unknown."""
    coordinate_transform: dict[str, JsonValue] | None = None


def _artist_display(track: Track) -> str | None:
    if not track.artists:
        return None
    parts: list[str] = []
    for i, ref in enumerate(track.artists):
        parts.append(ref.name)
        if i < len(track.artists) - 1:
            parts.append(f" {ref.join} " if ref.join else ", ")
    return "".join(parts)


def _matches(track: Track, filters: MapFilters) -> bool:
    if filters.has_audio is False:
        return False  # every map point has audio (see module docstring)
    if filters.genre and filters.genre.casefold() not in {g.casefold() for g in track.genres}:
        return False
    if filters.style and filters.style.casefold() not in {s.casefold() for s in track.styles}:
        return False
    return not (filters.artist_id and filters.artist_id not in {a.artist_id for a in track.artists})


class MapService:
    def __init__(
        self,
        tracks: TrackRepository,
        spatial: ProjectionSpatialRepository | None,
        *,
        unavailable_reason: str | None = None,
    ) -> None:
        if spatial is None and unavailable_reason is None:
            unavailable_reason = "projection_unavailable"
        self._tracks = tracks
        self._spatial = spatial
        self._reason = None if spatial is not None else unavailable_reason
        self._points: list[tuple[MapPoint, Track]] | None = None

    @classmethod
    def from_loader(
        cls, tracks: TrackRepository, load: Callable[[], ProjectionSpatialRepository]
    ) -> MapService:
        """Load the projection; a missing or mismatched artifact makes the map unavailable."""
        try:
            return cls(tracks, load())
        except SpatialArtifactError as exc:
            log.warning("map unavailable (%s): %s", exc.code, exc.message)
            return cls(tracks, None, unavailable_reason=exc.code)

    @property
    def available(self) -> bool:
        return self._spatial is not None

    def list_points(
        self,
        filters: MapFilters | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> MapPage:
        """Points ordered by track id; `cursor` is the last track id of the previous page."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if self._spatial is None:
            return MapPage(status="unavailable", reason=self._reason)
        limit = min(limit, MAX_LIMIT)
        filters = filters or MapFilters()
        page: list[MapPoint] = []
        has_more = False
        for point, track in self._all_points():
            if cursor is not None and point.track_id <= cursor:
                continue
            if not _matches(track, filters):
                continue
            if len(page) == limit:
                has_more = True
                break
            page.append(point)
        return MapPage(
            status="available",
            projection_version=self._spatial.projection_version,
            points=page,
            next_cursor=page[-1].track_id if has_more else None,
        )

    def meta(self) -> MapMeta:
        if self._spatial is None:
            return MapMeta(status="unavailable", reason=self._reason)
        meta: ProjectionMeta = self._spatial.meta
        coords = list(self._spatial.all_coordinates().values())
        bounds = None
        if coords:
            xs, ys = [c[0] for c in coords], [c[1] for c in coords]
            bounds = MapBounds(min_x=min(xs), max_x=max(xs), min_y=min(ys), max_y=max(ys))
        return MapMeta(
            status="available",
            projection_version=meta.projection_version,
            embedding_version=meta.embedding_version,
            model_id=meta.model_id,
            created_at=meta.created_at,
            bounds=bounds,
            n_points=len(coords),
            excluded_tracks=meta.excluded_tracks,
            coordinate_transform=meta.coordinate_transform,
        )

    def _all_points(self) -> list[tuple[MapPoint, Track]]:
        """Built once: the catalog and the projection do not change while the app runs."""
        if self._points is None:
            assert self._spatial is not None
            coordinates = self._spatial.all_coordinates()
            ids = sorted(coordinates)
            points = []
            for track in self._tracks.get_many(ids):
                x, y = coordinates[track.id]
                point = MapPoint(
                    track_id=track.id,
                    x=x,
                    y=y,
                    title=track.title,
                    artist=_artist_display(track),
                    genre=track.genres[0] if track.genres else None,
                    style=track.styles[0] if track.styles else None,
                    source_url=track.source_url,
                    has_audio=True,
                )
                points.append((point, track))
            if len(points) != len(ids):
                log.warning("%d projected tracks missing from the catalog", len(ids) - len(points))
            self._points = sorted(points, key=lambda p: p[0].track_id)
        return self._points
