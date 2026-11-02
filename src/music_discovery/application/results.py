"""Read models shared by the application services: a track with what is known around it.

`TrackView` joins catalog facts with the optional pieces a client needs (validated audio,
map coordinates). Anything unknown stays `None`; nothing is filled in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from music_discovery.domain.models import Track, TrackAudio
from music_discovery.domain.protocols import (
    SpatialRepository,
    TrackAudioRepository,
    TrackRepository,
)


@dataclass(frozen=True)
class TrackView:
    track: Track
    audio: TrackAudio | None
    """A validated local clip (decodes, license recorded); None when there is none."""
    coordinates: tuple[float, float] | None
    projection_version: str | None
    """Set together with `coordinates`."""


class TrackViewBuilder:
    def __init__(
        self,
        tracks: TrackRepository,
        audio: TrackAudioRepository,
        spatial: SpatialRepository | None,
    ) -> None:
        self._tracks = tracks
        self._audio = audio
        self._spatial = spatial

    def view(self, track: Track) -> TrackView:
        coordinates = None if self._spatial is None else self._spatial.coordinates(track.id)
        return TrackView(
            track=track,
            audio=self._audio.get(track.id),
            coordinates=coordinates,
            projection_version=(
                self._spatial.projection_version
                if self._spatial is not None and coordinates is not None
                else None
            ),
        )

    def get(self, track_id: str) -> TrackView | None:
        track = self._tracks.get(track_id)
        return None if track is None else self.view(track)

    def many(self, track_ids: Sequence[str]) -> dict[str, TrackView]:
        """Views for the known ids; unknown ids are absent."""
        return {t.id: self.view(t) for t in self._tracks.get_many(track_ids)}
