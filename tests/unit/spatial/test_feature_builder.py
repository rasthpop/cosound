from __future__ import annotations

import logging

import numpy as np
import pytest

from music_discovery.domain.errors import FeatureAlignmentError, InvalidEmbedding
from music_discovery.domain.protocols import Matrix, Vector
from music_discovery.spatial.feature_builder import build_features
from tests.fakes import InMemoryEmbeddingStore, hashed_unit_vector

DIM = 8
IDS = [f"trk_{i}" for i in range(5)]
VECTORS = {track_id: hashed_unit_vector(track_id, DIM) for track_id in IDS}


class RawStore:
    """Store whose matrix() returns exactly what it was given, to inject broken layouts."""

    def __init__(self, ids: list[str], matrix: Matrix, lookup: dict[str, Vector]) -> None:
        self._ids, self._matrix, self._lookup = ids, matrix, lookup

    @property
    def model_id(self) -> str:
        return "fake-clap-v1"

    @property
    def embedding_version(self) -> str:
        return "ev-raw"

    def track_ids(self) -> list[str]:
        return list(self._ids)

    def get(self, track_id: str) -> Vector | None:
        return self._lookup.get(track_id)

    def matrix(self) -> tuple[list[str], Matrix]:
        return list(self._ids), self._matrix


def test_rows_align_with_ids_and_missing_audio_is_excluded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryEmbeddingStore(VECTORS)
    catalog = [*IDS, "trk_no_audio_1", "trk_no_audio_2"]

    with caplog.at_level(logging.INFO):
        features = build_features(store, catalog)

    assert features.track_ids == tuple(sorted(IDS))
    for row, track_id in enumerate(features.track_ids):
        np.testing.assert_array_equal(features.matrix[row], VECTORS[track_id])
    assert features.excluded_track_ids == ("trk_no_audio_1", "trk_no_audio_2")
    assert features.excluded_count == 2
    assert features.embedding_version == "ev-test"
    assert "2 catalog tracks excluded" in caplog.text


def test_shuffled_ids_raise() -> None:
    matrix = np.stack([VECTORS[t] for t in IDS])
    shuffled = [IDS[1], IDS[0], *IDS[2:]]  # ids no longer describe their rows
    store = RawStore(shuffled, matrix, VECTORS)
    with pytest.raises(FeatureAlignmentError, match="row 0"):
        build_features(store, IDS)


def test_duplicate_ids_raise() -> None:
    ids = [*IDS[:4], IDS[0]]
    matrix = np.stack([VECTORS[t] for t in ids])
    with pytest.raises(FeatureAlignmentError, match="duplicate"):
        build_features(RawStore(ids, matrix, VECTORS), IDS)


def test_nan_rows_raise() -> None:
    matrix = np.stack([VECTORS[t] for t in IDS])
    matrix[2, 3] = np.nan
    with pytest.raises(InvalidEmbedding, match="non-finite") as info:
        build_features(RawStore(IDS, matrix, VECTORS), IDS)
    assert info.value.details["track_ids"] == [IDS[2]]


def test_unknown_ids_raise() -> None:
    store = InMemoryEmbeddingStore(VECTORS)
    with pytest.raises(FeatureAlignmentError, match="not in the catalog") as info:
        build_features(store, IDS[:3])
    assert info.value.details["track_ids"] == IDS[3:]


def test_row_count_and_norm_are_checked() -> None:
    matrix = np.stack([VECTORS[t] for t in IDS])
    with pytest.raises(InvalidEmbedding, match="rows"):
        build_features(RawStore(IDS[:4], matrix, VECTORS), IDS)
    with pytest.raises(InvalidEmbedding, match="L2-normalized"):
        build_features(RawStore(IDS, matrix * 2, VECTORS), IDS)


def test_empty_store_raises() -> None:
    with pytest.raises(InvalidEmbedding, match="empty"):
        build_features(InMemoryEmbeddingStore({}), IDS)
