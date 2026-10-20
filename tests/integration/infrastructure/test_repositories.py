"""One contract suite, run against the in-memory fakes and the SQLite repositories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from music_discovery.domain import protocols as p
from music_discovery.domain.enums import DataSource, ExternalIdKind, MatchStatus, RelationshipType
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import (
    Artist,
    ArtistReference,
    CrossSourceMatch,
    Label,
    LabelReference,
    Provenance,
    Release,
    Track,
    TrackAudio,
    TracklistEntry,
    TrackRelationship,
)
from music_discovery.infrastructure.database import SCHEMA_VERSION, Database, SchemaVersionError
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlLabelRepository,
    SqlMatchRepository,
    SqlRelationshipRepository,
    SqlReleaseRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from tests import fakes

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
FMA = Provenance(source=DataSource.FMA, imported_at=NOW)
DISCOGS = Provenance(source=DataSource.DISCOGS, imported_at=NOW, method="api")


def ext(source: DataSource, kind: ExternalIdKind, value: str) -> ExternalId:
    return ExternalId(source=source, kind=kind, value=value)


@dataclass
class Repos:
    tracks: p.TrackRepository
    releases: p.ReleaseRepository
    artists: p.ArtistRepository
    labels: p.LabelRepository
    audio: p.TrackAudioRepository
    relationships: p.RelationshipRepository
    matches: p.MatchRepository
    uow: p.UnitOfWork


def memory_repos() -> Repos:
    stores = (
        fakes.InMemoryTrackRepository(),
        fakes.InMemoryReleaseRepository(),
        fakes.InMemoryArtistRepository(),
        fakes.InMemoryLabelRepository(),
        fakes.InMemoryTrackAudioRepository(),
        fakes.InMemoryRelationshipRepository(),
        fakes.InMemoryMatchRepository(),
    )
    return Repos(*stores, uow=fakes.InMemoryUnitOfWork(*stores))


def sql_repos(database: Database) -> Repos:
    return Repos(
        tracks=SqlTrackRepository(database),
        releases=SqlReleaseRepository(database),
        artists=SqlArtistRepository(database),
        labels=SqlLabelRepository(database),
        audio=SqlTrackAudioRepository(database),
        relationships=SqlRelationshipRepository(database),
        matches=SqlMatchRepository(database),
        uow=database,
    )


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(f"sqlite:///{tmp_path / 'catalog.db'}")
    database.init_schema()
    yield database
    database.dispose()


@pytest.fixture(params=["memory", "sqlite"])
def repos(request: pytest.FixtureRequest, database: Database) -> Repos:
    return memory_repos() if request.param == "memory" else sql_repos(database)


def full_track(track_id: str = "trk_1", **overrides: object) -> Track:
    values: dict[str, object] = {
        "id": track_id,
        "title": "Flute Song",
        "artists": [
            ArtistReference(artist_id="art_1", name="First", join="&"),
            ArtistReference(artist_id="art_2", name="Second", role="Flute"),
        ],
        "release_id": "rel_1",
        "master_release_id": "mst_1",
        "year": 1999,
        "genres": ["Electronic", "Folk"],
        "styles": ["Ambient"],
        "labels": [LabelReference(label_id="lbl_1", name="Label", catalog_number="CAT 1")],
        "duration_seconds": 272.5,
        "discogs_url": "https://www.discogs.com/release/1",
        "audio_source": DataSource.FMA,
        "audio_path": "raw/fma/fma_small/000/000002.mp3",
        "metadata_confidence": 0.75,
        "audio_embedding_id": "emb_1",
        "spatial_x": -2.4,
        "spatial_y": 1.8,
        "external_ids": [ext(DataSource.FMA, ExternalIdKind.TRACK, track_id.removeprefix("trk_"))],
        "provenance": FMA,
    }
    values.update(overrides)
    return Track.model_validate(values)


def minimal_track(track_id: str) -> Track:
    return Track(id=track_id, title=f"Track {track_id}", provenance=FMA)


# --- Tracks ---------------------------------------------------------------------


def test_track_roundtrip_preserves_every_field(repos: Repos) -> None:
    track = full_track()
    repos.tracks.upsert(track)
    assert repos.tracks.get("trk_1") == track


def test_minimal_track_keeps_nulls(repos: Repos) -> None:
    repos.tracks.upsert(minimal_track("trk_9"))
    stored = repos.tracks.get("trk_9")
    assert stored is not None
    assert stored.duration_seconds is None
    assert stored.preview_url is None
    assert stored.audio_embedding_id is None
    assert stored.external_ids == []


def test_upsert_is_idempotent_and_updates(repos: Repos) -> None:
    track = full_track()
    repos.tracks.upsert(track)
    repos.tracks.upsert(track)
    assert repos.tracks.count() == 1
    changed = track.model_copy(
        update={
            "title": "Renamed",
            "year": None,
            "external_ids": [ext(DataSource.FMA, ExternalIdKind.TRACK, "200")],
        }
    )
    repos.tracks.upsert(changed)
    assert repos.tracks.count() == 1
    assert repos.tracks.get("trk_1") == changed
    assert repos.tracks.find_by_external_id(ext(DataSource.FMA, ExternalIdKind.TRACK, "1")) is None


def test_missing_ids(repos: Repos) -> None:
    assert repos.tracks.get("trk_missing") is None
    assert repos.tracks.find_by_external_id(ext(DataSource.FMA, ExternalIdKind.TRACK, "x")) is None
    assert repos.tracks.get_many([]) == []
    assert repos.tracks.count() == 0


def test_get_many_keeps_requested_order(repos: Repos) -> None:
    for i in ("trk_a", "trk_b", "trk_c"):
        repos.tracks.upsert(minimal_track(i))
    found = repos.tracks.get_many(["trk_c", "trk_missing", "trk_a"])
    assert [t.id for t in found] == ["trk_c", "trk_a"]


def test_find_track_by_external_id(repos: Repos) -> None:
    repos.tracks.upsert(full_track("trk_2"))
    found = repos.tracks.find_by_external_id(ext(DataSource.FMA, ExternalIdKind.TRACK, "2"))
    assert found is not None
    assert found.id == "trk_2"
    other_source = ext(DataSource.DISCOGS, ExternalIdKind.TRACK, "2")
    assert repos.tracks.find_by_external_id(other_source) is None


def test_list_page_walks_every_track_once(repos: Repos) -> None:
    ids = [f"trk_{i:02d}" for i in range(7)]
    for i in reversed(ids):
        repos.tracks.upsert(minimal_track(i))
    seen: list[str] = []
    after: str | None = None
    while page := repos.tracks.list_page(limit=3, after=after):
        seen.extend(t.id for t in page)
        after = page[-1].id
    assert seen == ids


# --- Releases, artists, labels -------------------------------------------------------


def test_release_roundtrip_with_tracklist(repos: Repos) -> None:
    release = Release(
        id="rel_1",
        title="Album",
        year=1999,
        genres=["Jazz"],
        styles=["Cool Jazz"],
        artists=[ArtistReference(artist_id="art_1", name="First")],
        labels=[LabelReference(label_id="lbl_1", name="Label")],
        track_listing=[
            TracklistEntry(position="A1", title="One", duration_seconds=180.0, track_id="trk_1"),
            TracklistEntry(position="A2", title="Two"),
        ],
        master_release_id="mst_1",
        discogs_url="https://www.discogs.com/release/1",
        external_ids=[
            ext(DataSource.DISCOGS, ExternalIdKind.RELEASE, "1"),
            ext(DataSource.DISCOGS, ExternalIdKind.MASTER, "10"),
        ],
        provenance=DISCOGS,
    )
    repos.releases.upsert(release)
    assert repos.releases.get("rel_1") == release
    master = ext(DataSource.DISCOGS, ExternalIdKind.MASTER, "10")
    assert repos.releases.find_by_external_id(master) == release


def test_artist_and_label_roundtrip(repos: Repos) -> None:
    artist = Artist(
        id="art_1",
        name="Name (2)",
        aliases=["Alias"],
        external_ids=[ext(DataSource.DISCOGS, ExternalIdKind.ARTIST, "5")],
        provenance=DISCOGS,
    )
    label = Label(
        id="lbl_1",
        name="Label",
        external_ids=[ext(DataSource.DISCOGS, ExternalIdKind.LABEL, "7")],
        provenance=DISCOGS,
    )
    repos.artists.upsert(artist)
    repos.labels.upsert(label)
    assert repos.artists.get("art_1") == artist
    assert repos.labels.get("lbl_1") == label
    assert repos.artists.find_by_external_id(artist.external_ids[0]) == artist
    assert repos.labels.find_by_external_id(label.external_ids[0]) == label
    # external ids are scoped per entity type
    assert repos.tracks.find_by_external_id(artist.external_ids[0]) is None


# --- Audio, relationships, matches -----------------------------------------------------


def test_track_audio(repos: Repos) -> None:
    plain = TrackAudio(track_id="trk_b", source=DataSource.FMA, file_path="raw/b.mp3")
    embedded = TrackAudio(
        track_id="trk_a",
        source=DataSource.FMA,
        file_path="raw/a.mp3",
        duration_seconds=30.0,
        sample_rate=44100,
        license="CC BY 4.0",
        embedding_model="clap",
        embedding_version="ev1",
        embedding_path="embeddings/ev1",
    )
    repos.audio.upsert(plain)
    repos.audio.upsert(embedded)
    repos.audio.upsert(embedded)
    assert repos.audio.get("trk_a") == embedded
    assert repos.audio.get("trk_missing") is None
    assert repos.audio.list_all() == [embedded, plain]


def test_relationships_filter_and_order(repos: Repos) -> None:
    def rel(target: str, kind: RelationshipType, weight: float | None = None) -> TrackRelationship:
        return TrackRelationship(
            source_track_id="trk_1",
            target_track_id=target,
            relationship_type=kind,
            evidence_source=DataSource.DISCOGS,
            weight=weight,
        )

    repos.relationships.upsert(rel("trk_3", RelationshipType.SAME_LABEL))
    repos.relationships.upsert(rel("trk_2", RelationshipType.SAME_ARTIST))
    repos.relationships.upsert(rel("trk_2", RelationshipType.SAME_LABEL, 0.4))
    repos.relationships.upsert(rel("trk_2", RelationshipType.SAME_LABEL, 0.5))
    all_rels = repos.relationships.for_track("trk_1")
    assert [(r.relationship_type, r.target_track_id) for r in all_rels] == [
        (RelationshipType.SAME_ARTIST, "trk_2"),
        (RelationshipType.SAME_LABEL, "trk_2"),
        (RelationshipType.SAME_LABEL, "trk_3"),
    ]
    assert all_rels[1].weight == 0.5
    labels_only = repos.relationships.for_track("trk_1", {RelationshipType.SAME_LABEL})
    assert len(labels_only) == 2
    assert repos.relationships.for_track("trk_2") == []


def test_matches_by_track_and_status(repos: Repos) -> None:
    target = ext(DataSource.DISCOGS, ExternalIdKind.RELEASE, "9")
    other = ext(DataSource.DISCOGS, ExternalIdKind.RELEASE, "10")
    unresolved = CrossSourceMatch(
        track_id="trk_1",
        target=target,
        target_position="A1",
        status=MatchStatus.UNRESOLVED,
        method="title_artist_duration",
        signals={"title": True, "duration_delta_s": 4.2},
        candidates=[target, other],
        decided_at=NOW,
    )
    repos.matches.upsert(unresolved)
    assert repos.matches.for_track("trk_1") == [unresolved]
    assert repos.matches.list_by_status(MatchStatus.UNRESOLVED) == [unresolved]
    accepted = unresolved.model_copy(update={"status": MatchStatus.ACCEPTED, "confidence": 0.95})
    repos.matches.upsert(accepted)
    assert repos.matches.for_track("trk_1") == [accepted]
    assert repos.matches.list_by_status(MatchStatus.UNRESOLVED) == []
    assert repos.matches.list_by_status(MatchStatus.ACCEPTED)[0].decided_at == NOW


# --- Units of work -------------------------------------------------------------------


class BoomError(RuntimeError):
    pass


def test_failed_transaction_leaves_no_partial_writes(repos: Repos) -> None:
    repos.tracks.upsert(minimal_track("trk_keep"))

    def write_then_fail() -> None:
        with repos.uow.transaction():
            repos.tracks.upsert(full_track("trk_new"))
            repos.audio.upsert(
                TrackAudio(track_id="trk_new", source=DataSource.FMA, file_path="raw/n.mp3")
            )
            raise BoomError

    with pytest.raises(BoomError):
        write_then_fail()
    assert repos.tracks.get("trk_new") is None
    assert repos.audio.get("trk_new") is None
    assert repos.tracks.get("trk_keep") is not None


def test_successful_transaction_commits_together(repos: Repos) -> None:
    with repos.uow.transaction():
        repos.tracks.upsert(minimal_track("trk_1"))
        repos.tracks.upsert(minimal_track("trk_2"))
        assert repos.tracks.count() == 2
    assert repos.tracks.count() == 2


# --- SQLite specifics ------------------------------------------------------------------


def test_data_survives_reopening(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'reopen.db'}"
    first = Database(url)
    first.init_schema()
    SqlTrackRepository(first).upsert(full_track())
    first.dispose()
    second = Database(url)
    second.init_schema()
    assert SqlTrackRepository(second).get("trk_1") == full_track()
    assert second.schema_version() == SCHEMA_VERSION
    second.dispose()


def test_schema_version_mismatch_is_refused(database: Database) -> None:
    from music_discovery.infrastructure.database import schema_version

    with database.engine.begin() as conn:
        conn.execute(schema_version.update().values(version=SCHEMA_VERSION + 1))
    with pytest.raises(SchemaVersionError):
        database.init_schema()


def test_in_memory_database_shares_one_connection() -> None:
    database = Database("sqlite:///:memory:")
    database.init_schema()
    SqlTrackRepository(database).upsert(minimal_track("trk_1"))
    assert SqlTrackRepository(database).count() == 1
    database.dispose()


def test_sql_repositories_satisfy_protocols(database: Database) -> None:
    repos = sql_repos(database)
    checks = [
        (p.TrackRepository, repos.tracks),
        (p.ReleaseRepository, repos.releases),
        (p.ArtistRepository, repos.artists),
        (p.LabelRepository, repos.labels),
        (p.TrackAudioRepository, repos.audio),
        (p.RelationshipRepository, repos.relationships),
        (p.MatchRepository, repos.matches),
        (p.UnitOfWork, repos.uow),
    ]
    for protocol, instance in checks:
        assert isinstance(instance, protocol), protocol.__name__
