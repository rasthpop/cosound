from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import numpy as np
import pytest

from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.models import TrackRelationship
from music_discovery.domain.protocols import SpatialRepository
from music_discovery.domain.vectors import l2_normalize
from music_discovery.spatial import neighbor_service
from music_discovery.spatial.neighbor_service import MAX_K, NeighborService
from tests.fakes import BruteForceVectorIndex, InMemoryRelationshipRepository


def at(degrees: float) -> np.ndarray:
    rad = np.deg2rad(degrees)
    return l2_normalize([np.cos(rad), np.sin(rad), 0.0])


# cosine order from trk_a: b (10°), c (30°), d (80°)
VECTORS = {"trk_a": at(0), "trk_b": at(10), "trk_c": at(30), "trk_d": at(80)}


def rel(target: str, kind: RelationshipType, weight: float | None = None) -> TrackRelationship:
    return TrackRelationship(
        source_track_id="trk_x",
        target_track_id=target,
        relationship_type=kind,
        evidence_source=DataSource.FMA,
        weight=weight,
    )


def test_neighbors_follow_original_space_cosine_and_skip_self() -> None:
    result = NeighborService(BruteForceVectorIndex(VECTORS)).neighbors("trk_a", k=2)
    assert result.metric == "clap_cosine"
    assert result.model_id == "fake-clap-v1"
    assert result.reason is None
    assert [n.track_id for n in result.neighbors] == ["trk_b", "trk_c"]
    assert result.neighbors[0].score == pytest.approx(np.cos(np.deg2rad(10)))


class RaisingSpatialRepository:
    """Any read of 2D coordinates fails the test."""

    @property
    def projection_version(self) -> str:
        raise AssertionError("neighbor service read the projection")

    def coordinates(self, track_id: str) -> tuple[float, float] | None:
        raise AssertionError("neighbor service read 2D coordinates")

    def all_coordinates(self) -> dict[str, tuple[float, float]]:
        raise AssertionError("neighbor service read 2D coordinates")


def test_two_d_coordinates_are_never_read() -> None:
    # The service cannot even be given a spatial repository...
    spatial_spy: SpatialRepository = RaisingSpatialRepository()
    hints = get_type_hints(NeighborService.__init__)
    assert all(hint is not SpatialRepository for hint in hints.values())
    with pytest.raises(TypeError):
        NeighborService(BruteForceVectorIndex(VECTORS), spatial=spatial_spy)  # type: ignore[call-arg]
    # ...and its module never refers to projections or coordinates.
    source = Path(inspect.getfile(neighbor_service)).read_text()
    code = source.split('"""', 2)[2]  # skip the module docstring
    for forbidden in ("SpatialRepository", "coordinates", "spatial_x", "projection"):
        assert forbidden not in code


def test_track_without_embedding_gets_empty_result_with_reason() -> None:
    result = NeighborService(BruteForceVectorIndex(VECTORS)).neighbors("trk_x")
    assert result.neighbors == []
    assert result.reason == "no_audio_embedding"
    assert result.metric == "catalog_relationship"


def test_relationship_fallback_is_labeled_and_ordered() -> None:
    relationships = InMemoryRelationshipRepository()
    relationships.upsert(rel("trk_style", RelationshipType.SHARED_STYLE, 0.4))
    relationships.upsert(rel("trk_label", RelationshipType.SAME_LABEL))
    relationships.upsert(rel("trk_artist", RelationshipType.SAME_ARTIST))
    relationships.upsert(rel("trk_artist", RelationshipType.SHARED_STYLE, 0.7))
    service = NeighborService(BruteForceVectorIndex(VECTORS), relationships)

    result = service.neighbors("trk_x", k=5)

    assert result.metric == "catalog_relationship"
    assert result.reason == "no_audio_embedding"
    assert result.model_id is None
    assert [n.track_id for n in result.neighbors] == ["trk_artist", "trk_label", "trk_style"]
    artist = result.neighbors[0]
    assert artist.relationship_types == [
        RelationshipType.SAME_ARTIST,
        RelationshipType.SHARED_STYLE,
    ]
    assert artist.score == pytest.approx(0.7)
    assert result.neighbors[1].score is None  # unknown weight stays unknown
    assert len(service.neighbors("trk_x", k=1).neighbors) == 1


def test_missing_index_reports_semantic_unavailable() -> None:
    result = NeighborService(None).neighbors("trk_a")
    assert result.reason == "semantic_unavailable"
    assert result.neighbors == []


def test_k_is_bounded() -> None:
    service = NeighborService(BruteForceVectorIndex(VECTORS))
    with pytest.raises(ValueError, match="at least 1"):
        service.neighbors("trk_a", k=0)
    many = {f"trk_{i:03d}": at(i * 0.5) for i in range(120)}
    assert (
        len(NeighborService(BruteForceVectorIndex(many)).neighbors("trk_000", 500).neighbors)
        == MAX_K
    )
