"""Offline map build: features → UMAP → quality → persisted projection (base.md §11.2).

All collaborators are injected, so `scripts/build_map.py` only composes them and tests can run
the whole flow with a fake projector and an in-memory store.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import JsonValue

from music_discovery.domain.errors import ProjectionMissing
from music_discovery.domain.protocols import Clock, EmbeddingStore, ProjectionStore
from music_discovery.domain.schemas import ProjectionMeta
from music_discovery.spatial.feature_builder import build_features
from music_discovery.spatial.quality import projection_quality
from music_discovery.spatial.spatial_repository import projection_version_for
from music_discovery.spatial.umap_projector import MapConfig, Projector

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildResult:
    meta: ProjectionMeta
    quality: dict[str, Any] | None
    """None when an identical projection already existed and was reused."""

    @property
    def reused(self) -> bool:
        return self.quality is None


def projection_config(config: MapConfig) -> dict[str, Any]:
    """The parameters that define a projection version (quality settings do not)."""
    return {"umap": config.umap.model_dump(mode="json"), "normalize": config.normalize}


def build_map(
    *,
    embeddings: EmbeddingStore,
    catalog_track_ids: Collection[str],
    projector: Projector,
    projections: ProjectionStore,
    config: MapConfig,
    clock: Clock,
    embedding_preprocessing: Mapping[str, JsonValue] | None = None,
    labels: Mapping[str, str] | None = None,
    force: bool = False,
) -> BuildResult:
    if config.umap.n_components != 2:
        raise ValueError("the map artifact stores 2D coordinates; set UMAP_N_COMPONENTS=2")
    features = build_features(embeddings, catalog_track_ids)
    version = projection_version_for(features.embedding_version, projection_config(config))
    if not force:
        try:
            existing = projections.read(version)
        except ProjectionMissing:
            pass
        else:
            log.info("projection %s already exists; use --force to rebuild", version)
            return BuildResult(meta=existing.meta, quality=None)

    projection = projector.fit(features.matrix, config.umap, normalize=config.normalize)
    coords = projection.coordinates
    quality = projection_quality(
        features.track_ids,
        features.matrix,
        coords,
        k=config.quality.k,
        probes=config.quality.probe_tracks,
        probe_neighbors=config.quality.probe_neighbors,
        seed=config.umap.random_state,
        labels=labels,
    )
    points = [(float(x), float(y)) for x, y in coords]
    meta = ProjectionMeta(
        projection_version=version,
        embedding_version=features.embedding_version,
        model_id=features.model_id,
        embedding_preprocessing=dict(embedding_preprocessing or {}) or None,
        umap_requested=projection.requested.model_dump(mode="json"),
        umap_effective=projection.effective.model_dump(mode="json"),
        random_state=projection.effective.random_state,
        package_versions=projection.package_versions,
        created_at=clock.now(),
        n_points=features.n,
        excluded_tracks=features.excluded_count,
        coordinate_transform=projection.coordinate_transform,
        coordinates_sha256=projections.coordinates_sha256(features.track_ids, points),
        notes=[*projection.notes, *quality["notes"]],
    )
    projections.write(meta, features.track_ids, points, quality)
    log.info("wrote projection %s (%d points)", version, features.n)
    return BuildResult(meta=meta, quality=quality)
