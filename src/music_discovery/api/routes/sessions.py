"""`GET /api/sessions/{session_id}`: session state and history ("what changed")."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_search_service
from music_discovery.api.schemas import ErrorResponse, SessionResponse
from music_discovery.application.search_service import SearchService

router = APIRouter(tags=["sessions"])


@router.get(
    "/sessions/{session_id}", operation_id="getSession", responses={404: {"model": ErrorResponse}}
)
def get_session(
    session_id: str, service: Annotated[SearchService, Depends(get_search_service)]
) -> SessionResponse:
    return mapping.session_response(service.session(session_id))
