"""Aligned, validated feature matrix for the audio projection (base.md §11.1, §11.2).

The MVP projects CLAP audio embeddings only. Catalog tracks without an embedding are excluded
(and counted), never placed with made-up features. Metadata-augmented features would be a
separate, separately-labeled experiment.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass

import numpy as np

from music_discovery.domain.errors import FeatureAlignmentError, InvalidEmbedding
from music_discovery.domain.protocols import EmbeddingStore, Matrix
from music_discovery.domain.vectors import is_unit_norm

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureMatrix:
    """Row `i` of `matrix` is the embedding of `track_ids[i]`."""

    embedding_version: str
    model_id: str
    track_ids: tuple[str, ...]
    matrix: Matrix
    excluded_track_ids: tuple[str, ...]
    """Catalog tracks left out because they have no audio embedding."""

    @property
    def n(self) -> int:
        return len(self.track_ids)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded_track_ids)


def build_features(store: EmbeddingStore, catalog_track_ids: Collection[str]) -> FeatureMatrix:
    """Load the store's matrix, check it row by row against its ids and the catalog."""
    ids, raw = store.matrix()
    matrix = np.asarray(raw, dtype=np.float32)

    if matrix.ndim != 2 or matrix.shape[0] != len(ids):
        raise InvalidEmbedding(f"expected ({len(ids)}, d) embedding rows, got {matrix.shape}")
    if len(ids) == 0:
        raise InvalidEmbedding(f"embedding version {store.embedding_version} is empty")
    if len(set(ids)) != len(ids):
        raise FeatureAlignmentError("duplicate track ids in the embedding matrix")
    if ids != store.track_ids():
        raise FeatureAlignmentError("matrix row order differs from the store's track ids")
    if not np.all(np.isfinite(matrix)):
        bad = [ids[i] for i in np.flatnonzero(~np.isfinite(matrix).all(axis=1))[:5]]
        raise InvalidEmbedding("non-finite embedding rows", details={"track_ids": bad})
    if not is_unit_norm(matrix):
        raise InvalidEmbedding("embeddings must be L2-normalized")
    for row, track_id in enumerate(ids):
        stored = store.get(track_id)
        if stored is None or not np.array_equal(stored, matrix[row]):
            raise FeatureAlignmentError(
                f"row {row} is not the embedding of {track_id}", details={"track_id": track_id}
            )

    catalog = set(catalog_track_ids)
    unknown = sorted(set(ids) - catalog)
    if unknown:
        raise FeatureAlignmentError(
            f"{len(unknown)} embedded track ids are not in the catalog",
            details={"track_ids": unknown[:20]},
        )
    excluded = tuple(sorted(catalog - set(ids)))
    log.info(
        "feature matrix %s: %d tracks, %d catalog tracks excluded (no audio embedding)",
        store.embedding_version,
        len(ids),
        len(excluded),
    )
    return FeatureMatrix(
        embedding_version=store.embedding_version,
        model_id=store.model_id,
        track_ids=tuple(ids),
        matrix=matrix,
        excluded_track_ids=excluded,
    )
