"""`POST /api/feedback`: a typed event or free text → updated search state (+ refreshed plate)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from music_discovery.api import mapping
from music_discovery.api.dependencies import get_feedback_service
from music_discovery.api.schemas import ErrorResponse, FeedbackRequest, FeedbackResponse
from music_discovery.application.feedback_service import FeedbackCommand, FeedbackService

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    operation_id="submitFeedback",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def submit_feedback(
    request: FeedbackRequest,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> FeedbackResponse:
    result = service.submit(FeedbackCommand(**request.model_dump()))
    return mapping.feedback_response(result)
