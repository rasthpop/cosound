"""`GET /api/tracks/{track_id}` and `GET /api/tracks/{track_id}/neighbors`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_track_service
from music_discovery.api.errors import error_responses
from music_discovery.api.schemas import NeighborsResponse, TrackDetail
from music_discovery.application.track_service import MAX_NEIGHBORS, TrackService

router = APIRouter(tags=["tracks"])


@router.get("/tracks/{track_id}", operation_id="getTrack", responses=error_responses(404))
def get_track(
    track_id: str, service: Annotated[TrackService, Depends(get_track_service)]
) -> TrackDetail:
    return mapping.track_detail(service.get(track_id))


@router.get(
    "/tracks/{track_id}/neighbors",
    operation_id="getTrackNeighbors",
    responses=error_responses(404, 422),
)
def get_neighbors(
    track_id: str,
    service: Annotated[TrackService, Depends(get_track_service)],
    k: Annotated[int, Query(ge=1, le=MAX_NEIGHBORS, description="Number of neighbors.")] = 10,
) -> NeighborsResponse:
    return mapping.neighbors_response(service.neighbors(track_id, k))
