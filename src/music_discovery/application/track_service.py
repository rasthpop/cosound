"""Track details, original-space neighbors and the licensed audio clip (base.md §13.2, §13.5).

Audio is served only from a validated `TrackAudio` record whose `file_path` resolves inside
DATA_DIR; nothing user-supplied ever becomes a path.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from music_discovery.application.results import TrackView, TrackViewBuilder
from music_discovery.domain.enums import RelationshipType
from music_discovery.domain.errors import AudioMissing, InvalidRequest, TrackNotFound
from music_discovery.domain.models import Release, TrackRelationship
from music_discovery.domain.protocols import (
    RelationshipRepository,
    ReleaseRepository,
    TrackAudioRepository,
)
from music_discovery.spatial.neighbor_service import (
    MAX_K,
    Neighbor,
    NeighborMetric,
    NeighborService,
    NoNeighborReason,
)

MAX_RELATED_PER_TYPE = 20
"""Track details list at most this many related tracks per relationship type (with counts)."""

AUDIO_MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
}


@dataclass(frozen=True)
class RelatedTrack:
    relationship: TrackRelationship
    view: TrackView


@dataclass(frozen=True)
class TrackDetail:
    view: TrackView
    release: Release | None
    related: list[RelatedTrack] = field(default_factory=list)
    relationship_counts: dict[RelationshipType, int] = field(default_factory=dict)
    """All relationships per type; `related` is capped at MAX_RELATED_PER_TYPE each."""


@dataclass(frozen=True)
class NeighborItem:
    neighbor: Neighbor
    view: TrackView


@dataclass(frozen=True)
class NeighborsResult:
    track_id: str
    metric: NeighborMetric
    model_id: str | None
    reason: NoNeighborReason | None
    items: list[NeighborItem]


@dataclass(frozen=True)
class AudioFile:
    track_id: str
    path: Path
    media_type: str
    license: str | None


class TrackService:
    def __init__(
        self,
        views: TrackViewBuilder,
        releases: ReleaseRepository,
        relationships: RelationshipRepository,
        audio: TrackAudioRepository,
        neighbors: NeighborService,
        data_dir: Path,
    ) -> None:
        self._views = views
        self._releases = releases
        self._relationships = relationships
        self._audio = audio
        self._neighbors = neighbors
        self._data_dir = data_dir.resolve()

    def get(self, track_id: str) -> TrackDetail:
        view = self._view(track_id)
        track = view.track
        release = self._releases.get(track.release_id) if track.release_id else None
        relationships = self._relationships.for_track(track_id)
        counts = Counter(r.relationship_type for r in relationships)
        shown: list[TrackRelationship] = []
        per_type: Counter[RelationshipType] = Counter()
        for rel in relationships:
            if per_type[rel.relationship_type] < MAX_RELATED_PER_TYPE:
                per_type[rel.relationship_type] += 1
                shown.append(rel)
        views = self._views.many([r.target_track_id for r in shown])
        related = [
            RelatedTrack(rel, views[rel.target_track_id])
            for rel in shown
            if rel.target_track_id in views
        ]
        return TrackDetail(view, release, related, dict(counts))

    def neighbors(self, track_id: str, k: int) -> NeighborsResult:
        if not 1 <= k <= MAX_K:
            raise InvalidRequest(
                f"k must be between 1 and {MAX_K}", details={"field": "k", "max": MAX_K}
            )
        self._view(track_id)
        result = self._neighbors.neighbors(track_id, k)
        views = self._views.many([n.track_id for n in result.neighbors])
        return NeighborsResult(
            track_id=track_id,
            metric=result.metric,
            model_id=result.model_id,
            reason=result.reason,
            items=[
                NeighborItem(n, views[n.track_id]) for n in result.neighbors if n.track_id in views
            ],
        )

    def audio_file(self, track_id: str) -> AudioFile:
        """The local clip to stream. Raises `TrackNotFound` or `AudioMissing`."""
        self._view(track_id)
        audio = self._audio.get(track_id)
        if audio is None:
            raise AudioMissing(
                f"track {track_id} has no validated audio", details={"track_id": track_id}
            )
        path = (self._data_dir / audio.file_path).resolve()
        if not path.is_relative_to(self._data_dir):
            raise AudioMissing(
                f"audio path for {track_id} is outside DATA_DIR", details={"track_id": track_id}
            )
        media_type = AUDIO_MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None or not path.is_file():
            raise AudioMissing(
                f"audio file for {track_id} is not available", details={"track_id": track_id}
            )
        return AudioFile(track_id, path, media_type, audio.license)

    def _view(self, track_id: str) -> TrackView:
        view = self._views.get(track_id)
        if view is None:
            raise TrackNotFound(f"track {track_id} does not exist", details={"track_id": track_id})
        return view
