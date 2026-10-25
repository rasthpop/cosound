"""`GET /api/tracks/{track_id}` and `GET /api/tracks/{track_id}/neighbors`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_track_service
from music_discovery.api.schemas import ErrorResponse, NeighborsResponse, TrackDetail
from music_discovery.application.track_service import TrackService
from music_discovery.spatial.neighbor_service import MAX_K

router = APIRouter(tags=["tracks"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


@router.get("/tracks/{track_id}", operation_id="getTrack", responses=NOT_FOUND)
def get_track(
    track_id: str, service: Annotated[TrackService, Depends(get_track_service)]
) -> TrackDetail:
    return mapping.track_detail(service.get(track_id))


@router.get(
    "/tracks/{track_id}/neighbors",
    operation_id="getTrackNeighbors",
    responses={**NOT_FOUND, 422: {"model": ErrorResponse}},
)
def get_neighbors(
    track_id: str,
    service: Annotated[TrackService, Depends(get_track_service)],
    k: Annotated[int, Query(ge=1, le=MAX_K, description="Number of neighbors.")] = 10,
) -> NeighborsResponse:
    return mapping.neighbors_response(service.neighbors(track_id, k))
