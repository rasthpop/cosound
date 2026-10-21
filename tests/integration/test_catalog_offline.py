"""Milestone 1: a local catalog can be built and queried without a live Discogs request.

The `block_network` fixture (tests/conftest.py) refuses every socket connection here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from music_discovery.domain.enums import DataSource, MatchStatus
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlImportRunRepository,
    SqlLabelRepository,
    SqlMatchRepository,
    SqlRelationshipRepository,
    SqlReleaseRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.ingestion.catalog_importer import CatalogImporter, CatalogWriters
from music_discovery.ingestion.catalog_report import iter_tracks, lookup, summarize
from music_discovery.ingestion.fma_loader import FmaImporter, FmaWriters, load_genres, load_tracks
from music_discovery.ingestion.matcher import SourceMatcher
from music_discovery.ingestion.raw_cache import RawCache
from music_discovery.ingestion.relationships import derive_relationships
from music_discovery.ingestion.selection import Selection
from tests.fakes import FakeAudioProbe, FrozenClock, SequentialIdGenerator

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(f"sqlite:///{tmp_path / 'catalog.db'}")
    database.init_schema()
    yield database
    database.dispose()


def test_catalog_builds_and_answers_queries_offline(database: Database, data_dir: Path) -> None:
    # Discogs: releases come only from the raw cache.
    cache = RawCache(data_dir / "raw" / "discogs")
    for name in ("release_full.json", "release_minimal.json"):
        payload = json.loads((FIXTURES / "discogs" / name).read_text())
        cache.put("releases", payload["id"], payload)
    selection = Selection.model_validate(
        {
            "selection_version": 1,
            "max_releases": 5,
            "seeds": [{"kind": "release", "id": 900001}, {"kind": "release", "id": 900002}],
        }
    )
    tracks = SqlTrackRepository(database)
    discogs_report = CatalogImporter(
        None,
        cache,
        CatalogWriters(
            tracks,
            SqlReleaseRepository(database),
            SqlArtistRepository(database),
            SqlLabelRepository(database),
            SqlImportRunRepository(database),
            database,
        ),
        clock=FrozenClock(),
        ids=SequentialIdGenerator(),
    ).run(selection, from_cache_only=True)
    assert discogs_report.errors == []

    # FMA: metadata fixtures; one track has decodable audio according to the probe.
    audio_dir = data_dir / "raw" / "fma" / "fma_small"
    (audio_dir / "000").mkdir(parents=True)
    (audio_dir / "000" / "000002.mp3").write_bytes(b"stand-in")
    FmaImporter(
        FmaWriters(
            tracks,
            SqlReleaseRepository(database),
            SqlArtistRepository(database),
            SqlTrackAudioRepository(database),
            SqlImportRunRepository(database),
            database,
        ),
        FakeAudioProbe(failures={"000005.mp3": "audio_missing", "000140.mp3": "audio_missing"}),
        data_dir=data_dir,
        clock=FrozenClock(),
        ids=SequentialIdGenerator(),
    ).run(load_tracks(FIXTURES / "fma"), audio_dir=audio_dir, genres=load_genres(FIXTURES / "fma"))

    # Relationships and cross-source matching, all local.
    all_tracks = list(iter_tracks(tracks))
    SqlRelationshipRepository(database).replace_all(derive_relationships(all_tracks))
    releases = SqlReleaseRepository(database)
    titles = {
        t.release_id: r.title
        for t in all_tracks
        if t.release_id and (r := releases.get(t.release_id))
    }
    matcher = SourceMatcher(
        [t for t in all_tracks if t.provenance.source is DataSource.DISCOGS], release_titles=titles
    )
    matches = SqlMatchRepository(database)
    for track in (t for t in all_tracks if t.provenance.source is DataSource.FMA):
        if (decision := matcher.match(track, decided_at=FrozenClock().now())) is not None:
            matches.upsert(decision)

    summary = summarize(tracks, SqlTrackAudioRepository(database), matches)
    assert summary.tracks == 8 + 3, "8 Discogs tracks from two releases + 3 FMA tracks"
    assert summary.by_source == {"discogs": 8, "fma": 3}
    assert summary.with_decodable_audio == 1
    assert summary.with_embeddings == 0
    assert summary.matches == {s.value: 0 for s in MatchStatus}, "synthetic sources share no titles"

    assert [t.title for t in lookup(tracks, "flute")] == ["Low Tide Flute"]
    assert {t.title for t in lookup(tracks, "lena ostrova")} >= {"Low Tide Flute", "Reed Signal"}
    flute = lookup(tracks, "flute")[0]
    assert SqlRelationshipRepository(database).for_track(flute.id), (
        "relationships available offline"
    )
