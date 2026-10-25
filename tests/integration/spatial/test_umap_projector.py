"""Real UMAP runs (slow): determinism and the 20-track evaluation corpus size."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from music_discovery.domain.vectors import l2_normalize
from music_discovery.infrastructure.spatial_store import FileProjectionStore
from music_discovery.spatial.map_builder import build_map
from music_discovery.spatial.umap_projector import MapConfig, UmapParams, UmapProjector
from tests.fakes import FrozenClock, InMemoryEmbeddingStore

pytestmark = pytest.mark.slow


def clustered(n: int, dim: int = 32, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centers = rng.standard_normal((4, dim)) * 3
    return l2_normalize(centers[np.arange(n) % 4] + rng.standard_normal((n, dim)))


def test_same_seed_gives_identical_coordinates() -> None:
    x = clustered(200)
    params = UmapParams(n_neighbors=15, random_state=42)
    first = UmapProjector().fit(x, params, normalize=True)
    second = UmapProjector().fit(x, params, normalize=True)
    np.testing.assert_allclose(first.coordinates, second.coordinates, atol=1e-6)
    assert first.coordinates.shape == (200, 2)
    assert first.effective == params


def test_twenty_point_corpus_records_clamped_params(tmp_path: Path) -> None:
    ids = [f"trk_{i:02d}" for i in range(20)]
    store = InMemoryEmbeddingStore(dict(zip(ids, clustered(20), strict=True)))
    projections = FileProjectionStore(tmp_path / "umap")
    config = MapConfig(umap=UmapParams(n_neighbors=30))

    result = build_map(
        embeddings=store,
        catalog_track_ids=ids,
        projector=UmapProjector(),
        projections=projections,
        config=config,
        clock=FrozenClock(),
    )

    meta = projections.read(result.meta.projection_version).meta
    assert meta.umap_requested["n_neighbors"] == 30
    assert meta.umap_effective["n_neighbors"] == 19
    assert any("clamped from 30 to 19" in note for note in meta.notes)
    assert any("illustrative" in note for note in meta.notes)
    assert meta.package_versions["umap-learn"]
    assert (tmp_path / "umap" / meta.projection_version / "quality.json").is_file()
