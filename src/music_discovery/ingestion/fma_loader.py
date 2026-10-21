"""FMA metadata loading and catalog import (base.md §2, §9.1).

`tracks.csv` has a two-row header (MultiIndex columns); list-like columns are stringified
Python lists. The FMA track id is kept as an external id and is never compared with Discogs ids.
"""

from __future__ import annotations

import ast
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict

from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.domain.ids import ExternalId, IdPrefix, stable_id
from music_discovery.domain.models import (
    Artist,
    ArtistReference,
    ImportFailure,
    ImportRun,
    Provenance,
    Release,
    Track,
    TrackAudio,
)
from music_discovery.domain.protocols import (
    ArtistRepository,
    AudioProbe,
    Clock,
    IdGenerator,
    ImportRunRepository,
    ReleaseRepository,
    TrackAudioRepository,
    TrackRepository,
    UnitOfWork,
)

log = logging.getLogger(__name__)

SUBSETS = ("small", "medium", "large")
"""FMA subsets are nested: small ⊂ medium ⊂ large."""

ECHONEST_FEATURES = (
    "acousticness",
    "danceability",
    "energy",
    "instrumentalness",
    "liveness",
    "speechiness",
    "tempo",
    "valence",
)


def fma_audio_path(audio_dir: Path, track_id: int) -> Path:
    tid = f"{track_id:06d}"
    return audio_dir / tid[:3] / f"{tid}.mp3"


def fma_ext(kind: ExternalIdKind, value: int) -> ExternalId:
    return ExternalId(source=DataSource.FMA, kind=kind, value=str(value))


def fma_track_id(track_id: int) -> str:
    return stable_id(IdPrefix.TRACK, fma_ext(ExternalIdKind.TRACK, track_id))


class FmaTrackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    fma_track_id: int
    title: str | None
    artist_id: int | None
    artist_name: str | None
    album_id: int | None
    album_title: str | None
    year: int | None
    genre_top: str | None
    genre_ids: list[int]
    genre_all_ids: list[int]
    tags: list[str]
    duration_seconds: float | None
    license: str | None
    subset: str | None
    split: str | None


def _literal_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    parsed = ast.literal_eval(value)
    return list(parsed) if isinstance(parsed, (list, tuple)) else []


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _int(value: Any) -> int | None:
    value = _clean(value)
    return int(value) if value is not None else None


def _year(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        year = pd.Timestamp(value).year
    except (ValueError, TypeError):
        return None
    return year if 1800 <= year <= 2100 else None


def load_tracks(metadata_dir: Path, *, subset: str | None = "small") -> list[FmaTrackRecord]:
    """Tracks from `tracks.csv`, optionally restricted to a subset (and the smaller ones in it)."""
    tracks = pd.read_csv(metadata_dir / "tracks.csv", index_col=0, header=[0, 1])
    if subset is not None:
        if subset not in SUBSETS:
            raise ValueError(f"unknown FMA subset {subset!r}")
        allowed = SUBSETS[: SUBSETS.index(subset) + 1]
        tracks = tracks[tracks[("set", "subset")].isin(allowed)]

    def col(top: str, name: str) -> pd.Series:
        key = (top, name)
        return (
            tracks[key]
            if key in tracks.columns
            else pd.Series([None] * len(tracks), index=tracks.index)
        )

    records = []
    index: list[Any] = tracks.index.tolist()
    columns = {
        "title": col("track", "title"),
        "artist_id": col("artist", "id"),
        "artist_name": col("artist", "name"),
        "album_id": col("album", "id"),
        "album_title": col("album", "title"),
        "released": col("album", "date_released"),
        "genre_top": col("track", "genre_top"),
        "genres": col("track", "genres"),
        "genres_all": col("track", "genres_all"),
        "tags": col("track", "tags"),
        "duration": col("track", "duration"),
        "license": col("track", "license"),
        "subset": col("set", "subset"),
        "split": col("set", "split"),
    }
    values = {name: series.tolist() for name, series in columns.items()}
    for position, tid in enumerate(index):
        row = {name: column[position] for name, column in values.items()}
        duration = _clean(row["duration"])
        records.append(
            FmaTrackRecord(
                fma_track_id=int(tid),
                title=_clean(row["title"]),
                artist_id=_int(row["artist_id"]),
                artist_name=_clean(row["artist_name"]),
                album_id=_int(row["album_id"]),
                album_title=_clean(row["album_title"]),
                year=_year(row["released"]),
                genre_top=_clean(row["genre_top"]),
                genre_ids=[int(g) for g in _literal_list(row["genres"])],
                genre_all_ids=[int(g) for g in _literal_list(row["genres_all"])],
                tags=[str(t) for t in _literal_list(row["tags"])],
                duration_seconds=float(duration) if duration is not None else None,
                license=_clean(row["license"]),
                subset=_clean(row["subset"]),
                split=_clean(row["split"]),
            )
        )
    return records


def load_track_urls(metadata_dir: Path) -> dict[int, str]:
    """FMA track page URLs from `raw_tracks.csv` (absent file or value -> no entry)."""
    path = metadata_dir / "raw_tracks.csv"
    if not path.is_file():
        return {}
    frame = pd.read_csv(path, usecols=["track_id", "track_url"])
    ids: list[Any] = frame["track_id"].tolist()
    urls: list[Any] = frame["track_url"].tolist()
    return {
        int(tid): str(url)
        for tid, url in zip(ids, urls, strict=True)
        if isinstance(url, str) and url.startswith(("http://", "https://"))
    }


def load_genres(metadata_dir: Path) -> dict[int, str]:
    genres = pd.read_csv(metadata_dir / "genres.csv")
    ids: list[Any] = genres["genre_id"].tolist()
    titles: list[Any] = genres["title"].tolist()
    return {int(i): str(t) for i, t in zip(ids, titles, strict=True)}


def load_echonest(
    metadata_dir: Path, track_ids: Iterable[int] | None = None
) -> dict[int, dict[str, float]]:
    """Echonest audio features where available (a subset of tracks). Estimates, not ground truth."""
    path = metadata_dir / "echonest.csv"
    if not path.is_file():
        return {}
    frame = pd.read_csv(path, index_col=0, header=[0, 1, 2])
    wanted = None if track_ids is None else set(track_ids)
    index: list[Any] = frame.index.tolist()
    features = {
        name: frame[("echonest", "audio_features", name)].tolist()
        for name in ECHONEST_FEATURES
        if ("echonest", "audio_features", name) in frame.columns
    }
    out: dict[int, dict[str, float]] = {}
    for position, raw_id in enumerate(index):
        tid = int(raw_id)
        if wanted is not None and tid not in wanted:
            continue
        values = {
            name: float(column[position])
            for name, column in features.items()
            if _clean(column[position]) is not None
        }
        if values:
            out[tid] = values
    return out


@dataclass
class FmaWriters:
    tracks: TrackRepository
    releases: ReleaseRepository
    artists: ArtistRepository
    audio: TrackAudioRepository
    runs: ImportRunRepository
    uow: UnitOfWork


@dataclass
class FmaImportReport:
    run_id: str
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[ImportFailure] = field(default_factory=list)


class FmaImporter:
    def __init__(
        self,
        writers: FmaWriters,
        probe: AudioProbe,
        *,
        data_dir: Path,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._w = writers
        self._probe = probe
        self._data_dir = data_dir
        self._clock = clock
        self._ids = ids

    def run(
        self,
        records: Sequence[FmaTrackRecord],
        *,
        audio_dir: Path,
        genres: dict[int, str],
        source_urls: Mapping[int, str] | None = None,
    ) -> FmaImportReport:
        started = self._clock.now()
        report = FmaImportReport(run_id=self._ids.new(IdPrefix.IMPORT_RUN))
        counts = {
            "tracks": 0,
            "audio_valid": 0,
            "audio_missing": 0,
            "audio_invalid": 0,
            "skipped": 0,
        }
        for record in records:
            if not record.title:
                counts["skipped"] += 1
                report.failures.append(
                    ImportFailure(
                        key=f"fma:{record.fma_track_id}", code="missing_title", message=""
                    )
                )
                continue
            audio, failure = self._audio(record, audio_dir)
            if audio is not None:
                counts["audio_valid"] += 1
            elif failure is not None and failure.code == "audio_missing":
                counts["audio_missing"] += 1
            elif failure is not None:
                counts["audio_invalid"] += 1
                report.failures.append(failure)
            url = (source_urls or {}).get(record.fma_track_id)
            track, artist, release = self._entities(record, audio, genres, started, url)
            with self._w.uow.transaction():
                if artist is not None:
                    self._w.artists.upsert(artist)
                if release is not None:
                    self._w.releases.upsert(release)
                self._w.tracks.upsert(track)
                if audio is not None:
                    self._w.audio.upsert(audio)
            counts["tracks"] += 1
        report.counts = counts
        self._w.runs.save(
            ImportRun(
                id=report.run_id,
                source=DataSource.FMA,
                started_at=started,
                finished_at=self._clock.now(),
                counts=counts,
                errors=report.failures,
            )
        )
        return report

    def _audio(
        self, record: FmaTrackRecord, audio_dir: Path
    ) -> tuple[TrackAudio | None, ImportFailure | None]:
        path = fma_audio_path(audio_dir, record.fma_track_id)
        result = self._probe.probe(path)
        key = f"fma:{record.fma_track_id}"
        if not result.ok:
            return None, ImportFailure(
                key=key, code=result.error_code or "audio_error", message=str(path)
            )
        try:
            relative = path.resolve().relative_to(self._data_dir.resolve())
        except ValueError:
            return None, ImportFailure(key=key, code="audio_outside_data_dir", message=str(path))
        return (
            TrackAudio(
                track_id=fma_track_id(record.fma_track_id),
                source=DataSource.FMA,
                file_path=relative.as_posix(),
                duration_seconds=result.duration_seconds,
                sample_rate=result.sample_rate,
                license=record.license,
            ),
            None,
        )

    def _entities(
        self,
        record: FmaTrackRecord,
        audio: TrackAudio | None,
        genres: dict[int, str],
        imported_at: datetime,
        source_url: str | None,
    ) -> tuple[Track, Artist | None, Release | None]:
        provenance = Provenance(
            source=DataSource.FMA, imported_at=imported_at, method="fma_metadata"
        )
        artist = None
        refs: list[ArtistReference] = []
        if record.artist_id is not None and record.artist_name:
            artist_ext = fma_ext(ExternalIdKind.ARTIST, record.artist_id)
            artist = Artist(
                id=stable_id(IdPrefix.ARTIST, artist_ext),
                name=record.artist_name.strip(),
                external_ids=[artist_ext],
                provenance=provenance,
            )
            refs = [ArtistReference(artist_id=artist.id, name=artist.name)]
        release = None
        if record.album_id is not None and record.album_title:
            album_ext = fma_ext(ExternalIdKind.RELEASE, record.album_id)
            release = Release(
                id=stable_id(IdPrefix.RELEASE, album_ext),
                title=record.album_title.strip(),
                year=record.year,
                artists=refs,
                external_ids=[album_ext],
                provenance=provenance,
            )
        names = [record.genre_top] if record.genre_top else []
        names += [genres[g] for g in record.genre_ids if g in genres]
        track = Track(
            id=fma_track_id(record.fma_track_id),
            title=(record.title or "").strip(),
            artists=refs,
            release_id=release.id if release else None,
            year=record.year,
            genres=list(dict.fromkeys(names)),
            tags=list(dict.fromkeys(t.strip() for t in record.tags if t.strip())),
            duration_seconds=record.duration_seconds,
            source_url=source_url,
            audio_source=DataSource.FMA if audio else None,
            audio_path=audio.file_path if audio else None,
            external_ids=[fma_ext(ExternalIdKind.TRACK, record.fma_track_id)],
            provenance=provenance,
        )
        return track, artist, release
