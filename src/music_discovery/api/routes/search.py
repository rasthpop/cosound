"""`POST /api/search`: a query (or follow-up in a session) → a plate of ranked tracks."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_search_service
from music_discovery.api.schemas import ErrorResponse, SearchRequest, SearchResponse
from music_discovery.application.search_service import SearchService

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    operation_id="search",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def search(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    result = service.search(request.query, session_id=request.session_id, limit=request.limit)
    return mapping.search_response(result)
