"""Seed a real (SQLite + files) installation in temp dirs: catalog, audio, embeddings, map."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from music_discovery.audio.embedding_store import EmbeddingMeta, write_embeddings
from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import TrackAudio
from music_discovery.domain.schemas import ProjectionMeta
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlRelationshipRepository,
    SqlReleaseRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import Settings
from music_discovery.infrastructure.spatial_store import FileProjectionStore
from tests.support.world import AUDIO_BYTES, CATALOG, VECTORS, World

MODEL = "fake-clap-v1"


def seed(settings: Settings, *, projection: bool, audio: bool = False) -> None:
    """The test-world catalog in SQLite, its embeddings, and optionally a map and clips."""
    database = Database(settings.database_url)
    database.init_schema()
    tracks = SqlTrackRepository(database)
    for track in CATALOG:
        tracks.upsert(track)
    world = World()
    for release in [world.releases.get("rel_garden")]:
        assert release is not None
        SqlReleaseRepository(database).upsert(release)
    relationships = SqlRelationshipRepository(database)
    for source in ("trk_night", "trk_bus"):
        for rel in world.relationships.for_track(source):
            relationships.upsert(rel)
    ids = sorted(t.id for t in CATALOG if t.audio_embedding_id is not None)
    if audio:
        clips = SqlTrackAudioRepository(database)
        for track_id in ids:
            path = settings.data_dir / "raw" / "fma" / f"{track_id}.mp3"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(AUDIO_BYTES)
            clips.upsert(
                TrackAudio(
                    track_id=track_id,
                    source=DataSource.FMA,
                    file_path=f"raw/fma/{track_id}.mp3",
                    license="Attribution 4.0 International",
                )
            )
    dim = len(next(iter(VECTORS.values())))
    meta = EmbeddingMeta(
        embedding_version="ev-test",
        model_id=MODEL,
        preprocessing={},
        package_versions={},
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        n=len(ids),
        dim=dim,
        failures=0,
    )
    write_embeddings(settings.embeddings_dir, meta, ids, np.stack([VECTORS[i] for i in ids]))
    if projection:
        store = FileProjectionStore(settings.umap_dir)
        coords = [(float(i), float(-i)) for i in range(len(ids))]
        store.write(
            ProjectionMeta(
                projection_version="umap-seeded",
                embedding_version="ev-test",
                model_id=MODEL,
                umap_requested={},
                umap_effective={},
                random_state=42,
                package_versions={},
                created_at=datetime(2026, 10, 2, tzinfo=UTC),
                n_points=len(ids),
                excluded_tracks=1,
                coordinates_sha256=store.coordinates_sha256(ids, coords),
            ),
            ids,
            coords,
            {},
        )
