"""FastAPI application factory (composition root).

    uv run uvicorn music_discovery.api.app:create_app --factory      # make serve

`create_app(settings, services=...)` lets tests inject services built over fakes;
`build_app(settings)` has every route but no services (used by scripts/export_openapi.py).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from music_discovery.api.dependencies import Services, build_services
from music_discovery.api.errors import error_responses, install_error_handlers
from music_discovery.api.routes import audio, feedback, health, map, search, sessions, tracks
from music_discovery.api.schemas import API_VERSION
from music_discovery.infrastructure.settings import Settings, get_settings

access_log = logging.getLogger("music_discovery.api.access")

REQUEST_ID_HEADER = "X-Request-ID"
API_VERSION_HEADER = "X-API-Version"


def create_app(settings: Settings | None = None, *, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = build_app(settings)
    app.state.services = services if services is not None else build_services(settings)
    return app


def build_app(settings: Settings) -> FastAPI:
    """Routes, middleware and error handlers without services (enough for the OpenAPI export)."""
    app = FastAPI(
        title="Semantic Music Discovery API",
        version=API_VERSION,
        description=(
            "Natural-language music discovery over the FMA catalog. Scores order results and "
            "are not probabilities; missing values are null."
        ),
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Range", REQUEST_ID_HEADER],
        expose_headers=[
            REQUEST_ID_HEADER,
            API_VERSION_HEADER,
            "Content-Range",
            "Accept-Ranges",
            "X-Audio-License",
        ],
    )
    app.middleware("http")(_request_context)
    # every route answers errors with the envelope (FastAPI's default 422 body is replaced)
    errors = error_responses(422, 500)
    for module in (health, search, tracks, audio, feedback, sessions, map):
        app.include_router(module.router, prefix="/api", responses=errors)
    return app


async def _request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Request id (incoming or new) on the response, and one structured access-log line."""
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = (
        incoming if 0 < len(incoming) <= 64 and incoming.isprintable() else uuid.uuid4().hex
    )
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers[API_VERSION_HEADER] = API_VERSION
    access_log.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    )
    return response
