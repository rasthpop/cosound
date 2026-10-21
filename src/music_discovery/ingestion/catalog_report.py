"""Read-only summary of the local catalog. Uses only local repositories, never the network."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from music_discovery.domain.enums import MatchStatus
from music_discovery.domain.models import Track
from music_discovery.domain.protocols import MatchRepository, TrackAudioRepository, TrackRepository
from music_discovery.ingestion.names import matching_key


def iter_tracks(tracks: TrackRepository, page_size: int = 1000) -> Iterator[Track]:
    after: str | None = None
    while page := tracks.list_page(limit=page_size, after=after):
        yield from page
        after = page[-1].id


@dataclass
class CatalogSummary:
    tracks: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    with_decodable_audio: int = 0
    with_embeddings: int = 0
    matches: dict[str, int] = field(default_factory=dict)
    top_genres: list[tuple[str, int]] = field(default_factory=list)


def summarize(
    tracks: TrackRepository, audio: TrackAudioRepository, matches: MatchRepository, *, top: int = 10
) -> CatalogSummary:
    sources: Counter[str] = Counter()
    genres: Counter[str] = Counter()
    count = 0
    for track in iter_tracks(tracks):
        count += 1
        sources[str(track.provenance.source)] += 1
        genres.update(track.genres[:1])
    audio_records = audio.list_all()
    return CatalogSummary(
        tracks=count,
        by_source=dict(sorted(sources.items())),
        with_decodable_audio=len(audio_records),
        with_embeddings=sum(a.has_embedding for a in audio_records),
        matches={str(s): len(matches.list_by_status(s)) for s in MatchStatus},
        top_genres=genres.most_common(top),
    )


def lookup(tracks: TrackRepository, text: str, *, limit: int = 20) -> list[Track]:
    """Tracks whose title or an artist name contains `text` (normalized), ordered by id."""
    needle = matching_key(text)
    if not needle:
        return []
    found: list[Track] = []
    for track in iter_tracks(tracks):
        haystack = [matching_key(track.title), *(matching_key(a.name) for a in track.artists)]
        if any(needle in h for h in haystack):
            found.append(track)
            if len(found) >= limit:
                break
    return found
