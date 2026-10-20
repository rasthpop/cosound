"""CatalogImporter end to end against SQLite, a raw cache on disk and a fake Discogs source."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from music_discovery.domain.errors import DiscogsNotFound
from music_discovery.domain.models import Track
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlImportRunRepository,
    SqlLabelRepository,
    SqlReleaseRepository,
    SqlTrackRepository,
)
from music_discovery.ingestion.catalog_importer import CatalogImporter, CatalogWriters
from music_discovery.ingestion.discogs_models import DiscogsReleaseSummary, DiscogsSearchHit
from music_discovery.ingestion.normalizer import release_id_for
from music_discovery.ingestion.raw_cache import RawCache
from music_discovery.ingestion.selection import Selection
from tests.fakes import FrozenClock, SequentialIdGenerator

FIXTURES = Path(__file__).parents[2] / "fixtures" / "discogs"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def variant(base: dict[str, Any], release_id: int, title: str) -> dict[str, Any]:
    payload = copy.deepcopy(base)
    payload["id"] = release_id
    payload["title"] = title
    return payload


class FakeSource:
    def __init__(
        self, releases: dict[int, dict[str, Any]], artist_listing: list[DiscogsReleaseSummary]
    ) -> None:
        self.releases = releases
        self.artist_listing = artist_listing
        self.release_calls: list[int] = []
        self.listing_calls = 0

    def get_release_raw(self, release_id: int) -> dict[str, Any]:
        self.release_calls.append(release_id)
        if release_id not in self.releases:
            raise DiscogsNotFound(f"/releases/{release_id} not found")
        return copy.deepcopy(self.releases[release_id])

    def iter_artist_releases(
        self, artist_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]:
        self.listing_calls += 1
        return iter(self.artist_listing[:max_items])

    def iter_label_releases(
        self, label_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]:
        return iter([])

    def search(
        self,
        *,
        max_items: int,
        genre: str | None = None,
        style: str | None = None,
        type: str = "release",
    ) -> Iterator[DiscogsSearchHit]:
        return iter([])


class OfflineSource(FakeSource):
    def get_release_raw(self, release_id: int) -> dict[str, Any]:
        raise AssertionError("network source used in offline mode")


SELECTION = Selection.model_validate(
    {
        "selection_version": 1,
        "max_releases": 10,
        "seeds": [
            {"kind": "release", "id": 900001},
            {"kind": "artist", "id": 700001, "max_items": 5},
            {"kind": "release", "id": 900002},
        ],
    }
)


@pytest.fixture
def source() -> FakeSource:
    full = fixture("release_full.json")
    releases = {
        900001: full,
        900002: fixture("release_minimal.json"),
        900003: variant(full, 900003, "Second Album"),
    }
    listing = [
        DiscogsReleaseSummary(id=900003, title="Second Album", type="release"),
        DiscogsReleaseSummary(id=800009, title="Master", type="master", main_release=900001),
    ]
    return FakeSource(releases, listing)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(f"sqlite:///{tmp_path / 'catalog.db'}")
    database.init_schema()
    yield database
    database.dispose()


def writers(database: Database, tracks: SqlTrackRepository | None = None) -> CatalogWriters:
    return CatalogWriters(
        tracks=tracks or SqlTrackRepository(database),
        releases=SqlReleaseRepository(database),
        artists=SqlArtistRepository(database),
        labels=SqlLabelRepository(database),
        runs=SqlImportRunRepository(database),
        uow=database,
    )


def importer(
    source: FakeSource | None, cache: RawCache, database: Database, **kw: Any
) -> CatalogImporter:
    return CatalogImporter(
        source,
        cache,
        kw.pop("w", None) or writers(database),
        clock=FrozenClock(),
        ids=SequentialIdGenerator(),
    )


def all_track_ids(database: Database) -> list[str]:
    return [t.id for t in SqlTrackRepository(database).list_page(limit=1000)]


def test_import_resolves_seeds_and_writes_catalog(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    cache = RawCache(tmp_path / "raw")
    report = importer(source, cache, database).run(SELECTION)
    assert report.errors == []
    assert report.release_ids == [900001, 900003, 900002], (
        "deduped, master resolved to main release"
    )
    assert report.counts["releases_imported"] == 3
    assert report.counts["tracks_imported"] == 5 + 5 + 3
    assert SqlTrackRepository(database).count() == 13
    assert SqlReleaseRepository(database).get(release_id_for(900003)) is not None
    assert cache.has("releases", 900001)
    run = SqlImportRunRepository(database).get(report.run_id)
    assert run is not None
    assert run.selection_hash == SELECTION.selection_hash
    assert run.counts["releases_imported"] == 3


def test_rerun_is_idempotent_and_uses_cache(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    cache = RawCache(tmp_path / "raw")
    first = importer(source, cache, database).run(SELECTION)
    ids_after_first = all_track_ids(database)
    calls_after_first = len(source.release_calls)
    second = importer(source, cache, database).run(SELECTION)
    assert all_track_ids(database) == ids_after_first
    assert len(source.release_calls) == calls_after_first, "second run must not refetch"
    assert source.listing_calls == 1, "seed listing cached too"
    assert second.counts["from_cache"] == 3
    assert first.release_ids == second.release_ids


def test_artist_aliases_merge_across_releases(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    importer(source, RawCache(tmp_path / "raw"), database).run(SELECTION)
    lena = next(
        a
        for a in (
            SqlArtistRepository(database).get(t.artists[0].artist_id)
            for t in SqlTrackRepository(database).list_page(limit=50)
        )
        if a and a.name == "Lena Ostrova"
    )
    assert "Lena O." in lena.aliases


def test_from_cache_only_needs_no_network(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    cache = RawCache(tmp_path / "raw")
    importer(source, cache, database).run(SELECTION)
    other_db = Database(f"sqlite:///{tmp_path / 'fresh.db'}")
    other_db.init_schema()
    offline = OfflineSource({}, [])
    report = importer(offline, cache, other_db).run(SELECTION, from_cache_only=True)
    assert report.errors == []
    assert SqlTrackRepository(other_db).count() == 13
    other_db.dispose()


def test_from_cache_only_reports_missing_entries(database: Database, tmp_path: Path) -> None:
    report = importer(OfflineSource({}, []), RawCache(tmp_path / "empty"), database).run(
        SELECTION, from_cache_only=True
    )
    codes = sorted({e.code for e in report.errors})
    assert codes == ["not_cached"]
    assert SqlTrackRepository(database).count() == 0


def test_dry_run_writes_nothing(source: FakeSource, database: Database, tmp_path: Path) -> None:
    cache = RawCache(tmp_path / "raw")
    report = importer(source, cache, database).run(SELECTION, dry_run=True)
    assert report.dry_run
    assert source.release_calls == []
    assert SqlTrackRepository(database).count() == 0
    assert SqlImportRunRepository(database).get(report.run_id) is None
    assert not (tmp_path / "raw").exists()


def test_bad_release_is_reported_and_others_imported(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    source.releases[900003] = {"id": 900003}  # missing title -> invalid shape
    del source.releases[900002]  # -> DiscogsNotFound
    report = importer(source, RawCache(tmp_path / "raw"), database).run(SELECTION)
    assert {(e.key, e.code) for e in report.errors} == {
        ("release:900003", "discogs_response_invalid"),
        ("release:900002", "discogs_not_found"),
    }
    assert report.counts["releases_imported"] == 1
    assert SqlTrackRepository(database).count() == 5


class FailOnTitle(SqlTrackRepository):
    """Simulates a crash halfway through writing one release."""

    def upsert(self, track: Track) -> None:
        if track.title == "Dusk" and track.release_id == release_id_for(900003):
            raise RuntimeError("disk full")
        super().upsert(track)


def test_mid_release_failure_rolls_back_only_that_release(
    source: FakeSource, database: Database, tmp_path: Path
) -> None:
    w = writers(database, tracks=FailOnTitle(database))
    report = importer(source, RawCache(tmp_path / "raw"), database, w=w).run(SELECTION)
    assert [(e.key, e.code) for e in report.errors] == [("release:900003", "write_failed")]
    tracks = SqlTrackRepository(database).list_page(limit=100)
    assert {t.release_id for t in tracks} == {release_id_for(900001), release_id_for(900002)}
    assert SqlReleaseRepository(database).get(release_id_for(900003)) is None, (
        "release row rolled back too"
    )
    assert SqlTrackRepository(database).count() == 8


def test_max_releases_caps_the_plan(source: FakeSource, database: Database, tmp_path: Path) -> None:
    capped = SELECTION.model_copy(update={"max_releases": 2})
    report = importer(source, RawCache(tmp_path / "raw"), database).run(capped)
    assert report.release_ids == [900001, 900003]


def test_selection_validation_and_hash() -> None:
    with pytest.raises(ValueError, match="need an id"):
        Selection.model_validate(
            {"selection_version": 1, "max_releases": 1, "seeds": [{"kind": "artist"}]}
        )
    with pytest.raises(ValueError, match="need a value"):
        Selection.model_validate(
            {"selection_version": 1, "max_releases": 1, "seeds": [{"kind": "style"}]}
        )
    bumped = SELECTION.model_copy(update={"selection_version": 2})
    assert bumped.selection_hash != SELECTION.selection_hash
    repo_config = Selection.load(Path(__file__).parents[3] / "config" / "discogs_selection.yaml")
    assert repo_config.max_releases <= 500
