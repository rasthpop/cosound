"""Bounded, idempotent Discogs import (base.md §10.2).

1. Resolve the selection's seeds to release ids (bounded by `max_releases`).
2. Fetch each release into the raw cache, unless it is already cached.
3. Normalize from the cache and write each release in its own transaction.
4. Record an `ImportRun` with the selection hash, counts and errors.

A failure on one release rolls back only that release; the run continues.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from music_discovery.domain.enums import DataSource
from music_discovery.domain.errors import DataSourceError, MusicDiscoveryError
from music_discovery.domain.ids import IdPrefix
from music_discovery.domain.models import Artist, ImportFailure, ImportRun, Label
from music_discovery.domain.protocols import (
    ArtistRepository,
    Clock,
    IdGenerator,
    ImportRunRepository,
    LabelRepository,
    ReleaseRepository,
    TrackRepository,
    UnitOfWork,
)
from music_discovery.ingestion.discogs_models import (
    DiscogsRelease,
    DiscogsReleaseSummary,
    DiscogsSearchHit,
)
from music_discovery.ingestion.normalizer import normalize_release
from music_discovery.ingestion.raw_cache import RawCache
from music_discovery.ingestion.selection import Seed, Selection

RELEASES = "releases"
SEEDS = "seeds"


class ReleaseSource(Protocol):
    """What the importer needs from Discogs. `DiscogsClient` satisfies it."""

    def get_release_raw(self, release_id: int) -> dict[str, Any]: ...
    def iter_artist_releases(
        self, artist_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]: ...
    def iter_label_releases(
        self, label_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]: ...
    def search(
        self,
        *,
        max_items: int,
        genre: str | None = None,
        style: str | None = None,
        type: str = "release",
    ) -> Iterator[DiscogsSearchHit]: ...


@dataclass
class CatalogWriters:
    tracks: TrackRepository
    releases: ReleaseRepository
    artists: ArtistRepository
    labels: LabelRepository
    runs: ImportRunRepository
    uow: UnitOfWork


@dataclass
class ImportReport:
    run_id: str
    selection_hash: str
    dry_run: bool
    release_ids: list[int] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[ImportFailure] = field(default_factory=list)


def _summary_release_ids(summaries: Iterable[DiscogsReleaseSummary]) -> list[int]:
    ids: list[int] = []
    for s in summaries:
        if s.type == "master":
            if s.main_release:
                ids.append(s.main_release)
        else:
            ids.append(s.id)
    return ids


class CatalogImporter:
    def __init__(
        self,
        source: ReleaseSource | None,
        cache: RawCache,
        writers: CatalogWriters,
        *,
        clock: Clock,
        ids: IdGenerator,
        logger: logging.Logger | None = None,
    ) -> None:
        self._source = source
        self._cache = cache
        self._w = writers
        self._clock = clock
        self._ids = ids
        self._log = logger or logging.getLogger(__name__)

    def run(
        self, selection: Selection, *, from_cache_only: bool = False, dry_run: bool = False
    ) -> ImportReport:
        offline = from_cache_only or dry_run or self._source is None
        started = self._clock.now()
        report = ImportReport(
            run_id=self._ids.new(IdPrefix.IMPORT_RUN),
            selection_hash=selection.selection_hash,
            dry_run=dry_run,
        )
        counts = {
            "seeds_resolved": 0,
            "releases_planned": 0,
            "fetched": 0,
            "from_cache": 0,
            "releases_imported": 0,
            "tracks_imported": 0,
            "failed": 0,
        }

        report.release_ids = self._resolve(selection, offline=offline, report=report, counts=counts)
        counts["releases_planned"] = len(report.release_ids)

        if not dry_run:
            for release_id in report.release_ids:
                self._import_one(release_id, offline=offline, report=report, counts=counts)
            counts["failed"] = len(report.errors)
            self._w.runs.save(
                ImportRun(
                    id=report.run_id,
                    source=DataSource.DISCOGS,
                    selection_hash=report.selection_hash,
                    started_at=started,
                    finished_at=self._clock.now(),
                    counts=counts,
                    errors=report.errors,
                )
            )
        else:
            counts["from_cache"] = sum(self._cache.has(RELEASES, r) for r in report.release_ids)
        report.counts = counts
        return report

    # --- Seeds --------------------------------------------------------------------------

    def _resolve(
        self, selection: Selection, *, offline: bool, report: ImportReport, counts: dict[str, int]
    ) -> list[int]:
        planned: dict[int, None] = {}
        for seed in selection.seeds:
            if len(planned) >= selection.max_releases:
                break
            ids = self._seed_release_ids(seed, offline=offline, report=report)
            if ids is None:
                continue
            counts["seeds_resolved"] += 1
            for release_id in ids:
                if len(planned) >= selection.max_releases:
                    break
                planned.setdefault(release_id, None)
        return list(planned)

    def _seed_release_ids(
        self, seed: Seed, *, offline: bool, report: ImportReport
    ) -> list[int] | None:
        if seed.kind == "release":
            assert seed.id is not None
            return [seed.id]
        cached = self._cache.get(SEEDS, seed.key)
        if cached is not None:
            return [int(i) for i in cached]
        if offline:
            report.errors.append(
                ImportFailure(
                    key=f"seed:{seed.key}",
                    code="not_cached",
                    message="seed listing is not in the raw cache",
                )
            )
            return None
        assert self._source is not None
        try:
            ids = self._fetch_seed(seed)
        except MusicDiscoveryError as exc:
            report.errors.append(
                ImportFailure(key=f"seed:{seed.key}", code=exc.code, message=exc.message)
            )
            return None
        self._cache.put(SEEDS, seed.key, ids)
        return ids

    def _fetch_seed(self, seed: Seed) -> list[int]:
        assert self._source is not None
        if seed.kind == "artist":
            assert seed.id is not None
            return _summary_release_ids(
                self._source.iter_artist_releases(seed.id, max_items=seed.max_items)
            )
        if seed.kind == "label":
            assert seed.id is not None
            return _summary_release_ids(
                self._source.iter_label_releases(seed.id, max_items=seed.max_items)
            )
        hits = self._source.search(
            max_items=seed.max_items,
            style=seed.value if seed.kind == "style" else None,
            genre=seed.value if seed.kind == "genre" else None,
        )
        return [h.id for h in hits if h.type == "release"]

    # --- Releases ---------------------------------------------------------------------------

    def _payload(self, release_id: int, *, offline: bool, counts: dict[str, int]) -> Any | None:
        cached = self._cache.get(RELEASES, release_id)
        if cached is not None:
            counts["from_cache"] += 1
            return cached
        if offline:
            return None
        assert self._source is not None
        payload = self._source.get_release_raw(release_id)
        self._cache.put(RELEASES, release_id, payload)
        counts["fetched"] += 1
        return payload

    def _import_one(
        self, release_id: int, *, offline: bool, report: ImportReport, counts: dict[str, int]
    ) -> None:
        key = f"release:{release_id}"
        try:
            payload = self._payload(release_id, offline=offline, counts=counts)
        except DataSourceError as exc:
            report.errors.append(ImportFailure(key=key, code=exc.code, message=exc.message))
            return
        if payload is None:
            report.errors.append(
                ImportFailure(key=key, code="not_cached", message="release is not in the raw cache")
            )
            return
        try:
            normalized = normalize_release(
                DiscogsRelease.model_validate(payload), imported_at=self._clock.now()
            )
        except ValidationError as exc:
            report.errors.append(
                ImportFailure(
                    key=key,
                    code="discogs_response_invalid",
                    message=str(exc.errors(include_url=False)[:3]),
                )
            )
            return
        try:
            with self._w.uow.transaction():
                self._w.releases.upsert(normalized.release)
                for artist in normalized.artists:
                    self._w.artists.upsert(self._merge_artist(artist))
                for label in normalized.labels:
                    self._w.labels.upsert(self._merge_label(label))
                for track in normalized.tracks:
                    self._w.tracks.upsert(track)
        except Exception as exc:  # roll back this release only, keep importing the rest
            self._log.exception("release import failed", extra={"release_id": release_id})
            code = exc.code if isinstance(exc, MusicDiscoveryError) else "write_failed"
            report.errors.append(ImportFailure(key=key, code=code, message=str(exc)))
            return
        counts["releases_imported"] += 1
        counts["tracks_imported"] += len(normalized.tracks)

    def _merge_artist(self, artist: Artist) -> Artist:
        """Union aliases and external ids with what earlier releases already recorded."""
        existing = self._w.artists.get(artist.id)
        if existing is None:
            return artist
        aliases = list(dict.fromkeys([*existing.aliases, *artist.aliases]))
        ext = list(dict.fromkeys([*existing.external_ids, *artist.external_ids]))
        return existing.model_copy(update={"aliases": aliases, "external_ids": ext})

    def _merge_label(self, label: Label) -> Label:
        existing = self._w.labels.get(label.id)
        if existing is None:
            return label
        ext = list(dict.fromkeys([*existing.external_ids, *label.external_ids]))
        return existing.model_copy(update={"external_ids": ext})
