"""One error envelope for every non-2xx response (api-contracts §3).

Status codes are chosen from the stable domain error `code`, never from messages. Unknown
errors become a generic 500; their details are logged server-side only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from music_discovery.api.schemas import ErrorBody, ErrorResponse
from music_discovery.domain.errors import MusicDiscoveryError

log = logging.getLogger(__name__)

STATUS_BY_CODE: dict[str, int] = {
    "validation_error": 422,
    "invalid_feedback_event": 422,
    "contradictory_constraints": 422,
    "invalid_constraint": 422,
    "track_not_found": 404,
    "session_not_found": 404,
    "not_found": 404,
    "audio_missing": 404,
    "track_not_in_results": 409,
    "query_not_in_session": 409,
    "stale_session_version": 409,
    "projection_unavailable": 503,
    "projection_mismatch": 503,
    "semantic_unavailable": 503,
}
HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}

ERROR_DESCRIPTIONS = {
    404: "Not found.",
    409: "Conflicts with the session state.",
    422: "Invalid request.",
    500: "Unexpected error.",
    503: "A required capability is unavailable.",
}
"""Explicit, so the OpenAPI document does not depend on the Python version's status phrases."""


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entries for error statuses, all using the envelope."""
    return {
        status: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[status]}
        for status in statuses
    }


def status_for(code: str) -> int:
    if code in STATUS_BY_CODE:
        return STATUS_BY_CODE[code]
    return 404 if code.endswith("_not_found") else 500


def envelope(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, MusicDiscoveryError)
    status = status_for(exc.code)
    if status == 500:
        log.error("unmapped domain error %s: %s %s", exc.code, exc.message, exc.details)
        return envelope(500, "internal_error", "Something went wrong.")
    return envelope(status, exc.code, exc.message, _json_safe(exc.details))


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"loc": ".".join(str(part) for part in e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    return envelope(422, "validation_error", "Request is invalid.", {"errors": errors})


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = HTTP_CODES.get(exc.status_code, "http_error")
    return envelope(exc.status_code, code, str(exc.detail))


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return envelope(500, "internal_error", "Something went wrong.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(MusicDiscoveryError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected)


def _json_safe(details: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in details.items():
        if value is None or isinstance(value, str | int | float | bool):
            safe[key] = value
        elif isinstance(value, list | tuple):
            safe[key] = [v if isinstance(v, str | int | float | bool) else str(v) for v in value]
        else:
            safe[key] = str(value)
    return safe
