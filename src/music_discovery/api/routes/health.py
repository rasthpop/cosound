"""`GET /api/health`: liveness and which optional capabilities are working."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_capability_service
from music_discovery.api.schemas import HealthResponse
from music_discovery.application.capabilities import CapabilityService

router = APIRouter(tags=["health"])


@router.get("/health", operation_id="getHealth")
def get_health(
    capabilities: Annotated[CapabilityService, Depends(get_capability_service)],
) -> HealthResponse:
    return mapping.health(capabilities.current())
