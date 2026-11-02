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


#: Track fields whose completeness the data-understanding report measures (CRISP-DM step 2).
PROFILED_FIELDS = (
    "artists",
    "year",
    "genres",
    "styles",
    "tags",
    "duration_seconds",
    "release_id",
    "source_url",
    "audio_path",
    "audio_embedding_id",
)


@dataclass
class CatalogProfile:
    """What the catalog contains and how complete it is. Missing values are counted, not filled."""

    tracks: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    present: dict[str, int] = field(default_factory=dict)
    """Tracks with a non-empty value, per field in PROFILED_FIELDS."""
    first_genre: dict[str, int] = field(default_factory=dict)
    """First genre tag per track (the map's colour), `"(none)"` for tracks without one."""
    genres_per_track: dict[int, int] = field(default_factory=dict)
    with_decodable_audio: int = 0
    with_embeddings: int = 0
    without_audio: list[str] = field(default_factory=list)
    """Track ids with no validated audio (not embedded, not on the map)."""
    audio_licenses: dict[str, int] = field(default_factory=dict)


def _present(track: Track, name: str) -> bool:
    value = getattr(track, name)
    return bool(value) if isinstance(value, list | str) else value is not None


def profile(tracks: TrackRepository, audio: TrackAudioRepository) -> CatalogProfile:
    """Field completeness, genre balance and audio/embedding coverage of the whole catalog."""
    sources: Counter[str] = Counter()
    present: Counter[str] = Counter()
    first_genre: Counter[str] = Counter()
    per_track: Counter[int] = Counter()
    ids: list[str] = []
    for track in iter_tracks(tracks):
        ids.append(track.id)
        sources[str(track.provenance.source)] += 1
        present.update(name for name in PROFILED_FIELDS if _present(track, name))
        first_genre[track.genres[0] if track.genres else "(none)"] += 1
        per_track[len(track.genres)] += 1
    records = audio.list_all()
    with_audio = {a.track_id for a in records}
    licenses = Counter(a.license or "(not recorded)" for a in records)
    return CatalogProfile(
        tracks=len(ids),
        by_source=dict(sorted(sources.items())),
        present={name: present[name] for name in PROFILED_FIELDS},
        first_genre=dict(first_genre.most_common()),
        genres_per_track=dict(sorted(per_track.items())),
        with_decodable_audio=len(records),
        with_embeddings=sum(a.has_embedding for a in records),
        without_audio=sorted(set(ids) - with_audio),
        audio_licenses=dict(licenses.most_common()),
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
