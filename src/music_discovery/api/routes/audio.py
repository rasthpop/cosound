"""`GET /api/tracks/{track_id}/audio`: stream the track's licensed local FMA clip (ADR-0005).

Only tracks with a validated `TrackAudio` record are served, from a path resolved inside
DATA_DIR by the track service (no user-supplied paths). Range requests return 206. The clip's
license travels in `X-Audio-License`.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from music_discovery.api.dependencies import get_track_service
from music_discovery.api.errors import error_responses
from music_discovery.application.track_service import TrackService

router = APIRouter(tags=["tracks"])

LICENSE_HEADER = "X-Audio-License"


@router.get(
    "/tracks/{track_id}/audio",
    operation_id="getTrackAudio",
    response_class=FileResponse,
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "The audio clip."},
        206: {"content": {"audio/mpeg": {}}, "description": "Requested byte range."},
        **error_responses(404),
    },
)
def get_track_audio(
    track_id: str, service: Annotated[TrackService, Depends(get_track_service)]
) -> FileResponse:
    audio = service.audio_file(track_id)
    license_text = audio.license if audio.license is not None else "unknown"
    return FileResponse(
        audio.path,
        media_type=audio.media_type,
        headers={LICENSE_HEADER: quote(license_text, safe=" .,:;()/-+'")},
        content_disposition_type="inline",
    )
