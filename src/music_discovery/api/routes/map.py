"""`GET /api/map/points` (paginated coordinates) and `GET /api/map/meta`.

Points need the projection: without it they are a 503 envelope. Meta always answers and says
whether the map is available, so the UI can show the state without an error.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_map_service
from music_discovery.api.errors import error_responses
from music_discovery.api.schemas import MapMetaResponse, MapPointsResponse
from music_discovery.application.map_service import DEFAULT_LIMIT, MAX_LIMIT, MapFilters, MapService
from music_discovery.domain.errors import ProjectionMissing

router = APIRouter(tags=["map"])


@router.get(
    "/map/points",
    operation_id="getMapPoints",
    responses=error_responses(422, 503),
)
def get_map_points(
    service: Annotated[MapService, Depends(get_map_service)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(description="`next_cursor` of the previous page.")] = None,
    genre: str | None = None,
    style: str | None = None,
    artist_id: str | None = None,
    has_audio: bool | None = None,
) -> MapPointsResponse:
    filters = MapFilters(genre=genre, style=style, artist_id=artist_id, has_audio=has_audio)
    page = service.list_points(filters, limit=limit, cursor=cursor)
    if page.status == "unavailable":
        raise ProjectionMissing("The track map is not available.", details={"reason": page.reason})
    return mapping.map_points(page)


@router.get("/map/meta", operation_id="getMapMeta")
def get_map_meta(service: Annotated[MapService, Depends(get_map_service)]) -> MapMetaResponse:
    return mapping.map_meta(service.meta())
