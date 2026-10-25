"""Validated, read-only access to one persisted projection (base.md §11.3).

The loader checks the artifact against the running system before anything is served: same
embedding version, one row per embedded track, every id in the catalog, finite coordinates.
Any disagreement is a `ProjectionMismatch` (the map is unavailable; search is unaffected).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Collection, Mapping
from typing import Any

from music_discovery.domain.errors import ProjectionMismatch
from music_discovery.domain.protocols import ProjectionStore
from music_discovery.domain.schemas import ProjectionArtifact, ProjectionMeta


def projection_version_for(embedding_version: str, config: Mapping[str, Any]) -> str:
    """Short, stable hash of the embeddings and every parameter that shapes the map."""
    canonical = json.dumps(
        {"embedding_version": embedding_version, "config": config}, sort_keys=True
    )
    return "umap-" + hashlib.sha256(canonical.encode()).hexdigest()[:12]


class ProjectionSpatialRepository:
    """Implements `domain.protocols.SpatialRepository` over a validated artifact."""

    def __init__(self, artifact: ProjectionArtifact) -> None:
        self._meta = artifact.meta
        self._coordinates = dict(zip(artifact.track_ids, artifact.coordinates, strict=True))

    @property
    def projection_version(self) -> str:
        return self._meta.projection_version

    @property
    def meta(self) -> ProjectionMeta:
        return self._meta

    def coordinates(self, track_id: str) -> tuple[float, float] | None:
        return self._coordinates.get(track_id)

    def all_coordinates(self) -> Mapping[str, tuple[float, float]]:
        return dict(self._coordinates)


def load_projection(
    store: ProjectionStore,
    projection_version: str,
    *,
    embedding_version: str,
    embedded_track_ids: Collection[str],
    catalog_track_ids: Collection[str],
) -> ProjectionSpatialRepository:
    """Read and validate a projection. Raises `ProjectionMissing` or `ProjectionMismatch`."""
    artifact = store.read(projection_version)
    validate_projection(
        artifact,
        embedding_version=embedding_version,
        embedded_track_ids=embedded_track_ids,
        catalog_track_ids=catalog_track_ids,
    )
    return ProjectionSpatialRepository(artifact)


def validate_projection(
    artifact: ProjectionArtifact,
    *,
    embedding_version: str,
    embedded_track_ids: Collection[str],
    catalog_track_ids: Collection[str],
) -> None:
    meta = artifact.meta
    details: dict[str, Any] = {"projection_version": meta.projection_version}
    if meta.embedding_version != embedding_version:
        raise ProjectionMismatch(
            f"projection was built from {meta.embedding_version}, "
            f"active embeddings are {embedding_version}; rebuild with scripts/build_map.py",
            details={**details, "stored": meta.embedding_version, "active": embedding_version},
        )
    ids = artifact.track_ids
    if len(ids) != meta.n_points or len(artifact.coordinates) != len(ids):
        raise ProjectionMismatch(
            f"meta says {meta.n_points} points, artifact has {len(ids)} ids and "
            f"{len(artifact.coordinates)} coordinates",
            details=details,
        )
    if len(set(ids)) != len(ids):
        raise ProjectionMismatch("duplicate track ids in the projection", details=details)
    projected = set(ids)
    missing = sorted(set(embedded_track_ids) - projected)
    extra = sorted(projected - set(embedded_track_ids))
    if missing or extra:
        raise ProjectionMismatch(
            f"projection ids differ from the embedding store: {len(missing)} missing, "
            f"{len(extra)} extra",
            details={**details, "missing": missing[:20], "extra": extra[:20]},
        )
    unknown = sorted(projected - set(catalog_track_ids))
    if unknown:
        raise ProjectionMismatch(
            f"{len(unknown)} projected track ids are not in the catalog",
            details={**details, "track_ids": unknown[:20]},
        )
    if not all(math.isfinite(v) for point in artifact.coordinates for v in point):
        raise ProjectionMismatch("non-finite coordinates in the projection", details=details)
