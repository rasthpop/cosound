"""Fit the UMAP track map for the active embedding version (offline; base.md §11).

    uv run python scripts/build_map.py            # reuse an identical projection if present
    uv run python scripts/build_map.py --force    # refit and overwrite it

Reads config/umap.yaml (+ UMAP_RANDOM_STATE, UMAP_N_COMPONENTS), writes
artifacts/umap/<projection_version>/ and prints the version; set ACTIVE_PROJECTION_VERSION to
it to pin the map the API serves (otherwise the newest projection is used).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import SqlTrackRepository
from music_discovery.infrastructure.settings import get_settings
from music_discovery.infrastructure.spatial_store import FileProjectionStore
from music_discovery.ingestion.catalog_report import iter_tracks
from music_discovery.spatial.map_builder import build_map
from music_discovery.spatial.umap_projector import MapConfig, UmapProjector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="refit even if the version exists")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    config = MapConfig.load(
        settings.project_root / "config" / "umap.yaml",
        random_state=settings.umap_random_state,
        n_components=settings.umap_n_components,
    )
    directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
    store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    tracks = list(iter_tracks(SqlTrackRepository(Database(settings.database_url))))
    labels = {t.id: f"{t.title} — {', '.join(a.name for a in t.artists) or '?'}" for t in tracks}

    result = build_map(
        embeddings=store,
        catalog_track_ids=[t.id for t in tracks],
        projector=UmapProjector(),
        projections=FileProjectionStore(settings.umap_dir),
        config=config,
        clock=SystemClock(),
        embedding_preprocessing=store.meta.preprocessing,
        labels=labels,
        force=args.force,
    )
    meta = result.meta
    summary = {
        "projection_version": meta.projection_version,
        "embedding_version": meta.embedding_version,
        "reused": result.reused,
        "n_points": meta.n_points,
        "excluded_tracks": meta.excluded_tracks,
        "umap_effective": meta.umap_effective,
        "notes": meta.notes,
    }
    if result.quality is not None:
        summary |= {k: result.quality[k] for k in ("k", "trustworthiness", "knn_overlap")}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
