from __future__ import annotations

import numpy as np
import pytest
from sklearn.manifold import trustworthiness

from music_discovery.domain.vectors import l2_normalize
from music_discovery.spatial import quality
from music_discovery.spatial.quality import (
    effective_k,
    neighborhood_scores,
    probe_table,
    projection_quality,
)


def unit_angles(degrees: list[float]) -> np.ndarray:
    """Unit vectors in a plane: cosine distance follows the angle between them."""
    rad = np.deg2rad(degrees)
    return l2_normalize(np.stack([np.cos(rad), np.sin(rad), np.zeros_like(rad)], axis=1))


def test_known_half_overlap_at_k1() -> None:
    # original nearest neighbors: a<->b, c<->d
    x = unit_angles([0, 10, 90, 100])
    # on the line: a->b (kept), b->c (lost), c->b (lost), d->c (kept)
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [1.6, 0.0], [10.0, 0.0]])
    scores = neighborhood_scores(x, coords, k=1)
    assert scores["k"] == 1
    assert scores["knn_overlap"] == pytest.approx(0.5)


def irregular_angles(n: int) -> list[float]:
    """Distinct, unevenly spaced angles in [0, 170] so no two neighbor distances tie."""
    return sorted(np.random.default_rng(7).uniform(0, 170, n).tolist())


def test_faithful_layout_scores_one() -> None:
    angles = irregular_angles(30)
    x = unit_angles(angles)
    coords = np.stack([np.deg2rad(angles), np.zeros(len(angles))], axis=1)
    scores = neighborhood_scores(x, coords, k=5)
    assert scores["knn_overlap"] == pytest.approx(1.0)
    assert scores["trustworthiness"] == pytest.approx(1.0)


@pytest.mark.parametrize("block", [7, 512])
def test_trustworthiness_matches_sklearn(monkeypatch: pytest.MonkeyPatch, block: int) -> None:
    monkeypatch.setattr(quality, "BLOCK", block)
    rng = np.random.default_rng(0)
    x = l2_normalize(rng.standard_normal((60, 12)))
    coords = rng.standard_normal((60, 2))
    expected = trustworthiness(x, coords, n_neighbors=5, metric="cosine")
    assert neighborhood_scores(x, coords, k=5)["trustworthiness"] == pytest.approx(expected)


def test_scrambled_layout_scores_lower_than_faithful() -> None:
    angles = irregular_angles(40)
    x = unit_angles(angles)
    faithful = np.stack([np.deg2rad(angles), np.zeros(len(angles))], axis=1)
    scrambled = np.random.default_rng(1).permutation(faithful)
    good, bad = neighborhood_scores(x, faithful, 5), neighborhood_scores(x, scrambled, 5)
    assert bad["knn_overlap"] < good["knn_overlap"]
    assert bad["trustworthiness"] < good["trustworthiness"]


def test_k_is_reduced_for_small_n() -> None:
    assert effective_k(10, 20) == 9
    assert effective_k(10, 5) == 2
    x = unit_angles(list(range(0, 50, 10)))
    report = projection_quality(
        [f"t{i}" for i in range(5)],
        x,
        np.arange(10.0).reshape(5, 2),
        k=10,
        probes=3,
        probe_neighbors=3,
        seed=0,
    )
    assert report["k"] == 2
    assert report["notes"] == ["k reduced from 10 to 2 (needs k < n / 2, n=5)"]


def test_probe_table_lists_both_neighbor_sets() -> None:
    x = unit_angles([0, 10, 90, 100])
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [1.6, 0.0], [10.0, 0.0]])
    ids = ["a", "b", "c", "d"]
    table = probe_table(
        ids, x, coords, probes=4, neighbors=1, seed=0, labels={"b": "Track B — Artist"}
    )
    by_probe = {row["probe"]["track_id"]: row for row in table}
    assert [n["track_id"] for n in by_probe["b"]["original_neighbors"]] == ["a"]
    assert [n["track_id"] for n in by_probe["b"]["map_neighbors"]] == ["c"]
    assert by_probe["b"]["shared"] == 0
    assert by_probe["a"]["shared"] == 1
    assert by_probe["a"]["original_neighbors"][0]["label"] == "Track B — Artist"
    assert by_probe["a"]["original_neighbors"][0]["cosine"] == pytest.approx(
        np.cos(np.deg2rad(10)), abs=1e-4
    )
    assert table == probe_table(
        ids, x, coords, probes=4, neighbors=1, seed=0, labels={"b": "Track B — Artist"}
    )
