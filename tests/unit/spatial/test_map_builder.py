"""The scripts/build_map.py flow with a fake projector and in-memory stores."""

from __future__ import annotations

import numpy as np
import pytest

from music_discovery.domain.errors import FeatureAlignmentError
from music_discovery.domain.protocols import Matrix
from music_discovery.spatial.map_builder import build_map, projection_config
from music_discovery.spatial.spatial_repository import projection_version_for
from music_discovery.spatial.umap_projector import (
    MapConfig,
    Projection,
    QualityConfig,
    UmapParams,
    effective_params,
    normalize_coordinates,
)
from tests.fakes import FrozenClock, InMemoryEmbeddingStore, InMemoryProjectionStore
from tests.fakes import hashed_unit_vector as vec

IDS = [f"trk_{i:02d}" for i in range(20)]
CATALOG = [*IDS, "trk_no_audio"]


class FakeProjector:
    """Takes the first two embedding dimensions as coordinates; records its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def fit(self, matrix: Matrix, params: UmapParams, *, normalize: bool) -> Projection:
        self.calls += 1
        effective, notes = effective_params(params, matrix.shape[0])
        coords = np.asarray(matrix[:, :2], dtype=np.float64)
        transform = None
        if normalize:
            coords, transform = normalize_coordinates(coords)
        return Projection(coords, params, effective, transform, {"fake": "1"}, notes)


@pytest.fixture
def embeddings() -> InMemoryEmbeddingStore:
    return InMemoryEmbeddingStore({t: vec(t, 8) for t in IDS}, embedding_version="ev-abc")


def test_flow_persists_coordinates_meta_and_quality(embeddings: InMemoryEmbeddingStore) -> None:
    projections, projector = InMemoryProjectionStore(), FakeProjector()
    result = build_map(
        embeddings=embeddings,
        catalog_track_ids=CATALOG,
        projector=projector,
        projections=projections,
        config=MapConfig(),
        clock=FrozenClock(),
        embedding_preprocessing={"sample_rate": 48000},
        labels={IDS[0]: "Title — Artist"},
    )

    meta = result.meta
    assert not result.reused
    assert meta.projection_version == projection_version_for(
        "ev-abc", projection_config(MapConfig())
    )
    assert meta.embedding_version == "ev-abc"
    assert meta.model_id == "fake-clap-v1"
    assert meta.embedding_preprocessing == {"sample_rate": 48000}
    assert meta.n_points == 20
    assert meta.excluded_tracks == 1
    assert meta.umap_requested["n_neighbors"] == 15
    assert meta.random_state == 42
    assert meta.coordinate_transform is not None
    assert any("illustrative" in note for note in meta.notes)

    artifact = projections.read(meta.projection_version)
    assert artifact.track_ids == sorted(IDS)
    assert len(artifact.coordinates) == 20
    assert max(abs(v) for point in artifact.coordinates for v in point) == pytest.approx(1.0)
    quality = projections.quality[meta.projection_version]
    assert quality["n_points"] == 20
    assert 0.0 <= float(quality["trustworthiness"]) <= 1.0  # type: ignore[arg-type]
    assert len(quality["probe_neighbors"]) == 3  # type: ignore[arg-type]


def test_identical_rebuild_is_reused_unless_forced(embeddings: InMemoryEmbeddingStore) -> None:
    projections, projector = InMemoryProjectionStore(), FakeProjector()
    first = build_map(
        embeddings=embeddings,
        catalog_track_ids=CATALOG,
        projector=projector,
        projections=projections,
        config=MapConfig(),
        clock=FrozenClock(),
    )
    again = build_map(
        embeddings=embeddings,
        catalog_track_ids=CATALOG,
        projector=projector,
        projections=projections,
        config=MapConfig(),
        clock=FrozenClock(),
    )
    assert again.reused
    assert again.meta == first.meta
    assert projector.calls == 1

    forced = build_map(
        embeddings=embeddings,
        catalog_track_ids=CATALOG,
        projector=projector,
        projections=projections,
        config=MapConfig(),
        clock=FrozenClock(),
        force=True,
    )
    assert not forced.reused
    assert projector.calls == 2
    assert projections.writes == 2


def test_parameters_change_the_projection_version(embeddings: InMemoryEmbeddingStore) -> None:
    base = projection_version_for("ev-abc", projection_config(MapConfig()))
    other = MapConfig(umap=UmapParams(min_dist=0.3))
    assert projection_version_for("ev-abc", projection_config(other)) != base
    assert projection_version_for("ev-xyz", projection_config(MapConfig())) != base
    # quality settings do not change what the map is
    tuned = MapConfig(quality=QualityConfig(k=5))
    assert projection_version_for("ev-abc", projection_config(tuned)) == base


def test_three_components_are_refused(embeddings: InMemoryEmbeddingStore) -> None:
    with pytest.raises(ValueError, match="UMAP_N_COMPONENTS=2"):
        build_map(
            embeddings=embeddings,
            catalog_track_ids=CATALOG,
            projector=FakeProjector(),
            projections=InMemoryProjectionStore(),
            config=MapConfig(umap=UmapParams(n_components=3)),
            clock=FrozenClock(),
        )


def test_embeddings_outside_the_catalog_stop_the_build(
    embeddings: InMemoryEmbeddingStore,
) -> None:
    projections = InMemoryProjectionStore()
    with pytest.raises(FeatureAlignmentError):
        build_map(
            embeddings=embeddings,
            catalog_track_ids=IDS[:10],
            projector=FakeProjector(),
            projections=projections,
            config=MapConfig(),
            clock=FrozenClock(),
        )
    assert projections.writes == 0
