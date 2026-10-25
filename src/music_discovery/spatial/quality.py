"""Neighborhood preservation of a projection (base.md §11.2, §12.7).

- trustworthiness@k: penalizes 2D neighbors that are far apart in the original space
  (same definition as `sklearn.manifold.trustworthiness`, computed in row blocks so 8k tracks
  do not need n-by-n matrices in memory).
- kNN overlap@k: mean |N_k^orig(i) ∩ N_k^2D(i)| / k.
- a probe table: original vs 2D neighbors of a few tracks, for a manual check.

Original space = cosine on the L2-normalized embeddings; 2D = Euclidean on coordinates.
Visual attractiveness is not a criterion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from music_discovery.domain.protocols import Matrix

BLOCK = 512

IntArray = npt.NDArray[np.int64]


def effective_k(k: int, n: int) -> int:
    """trustworthiness is defined for k < n / 2."""
    return max(1, min(k, (n - 1) // 2))


def _original_distances(x: Matrix, rows: IntArray) -> npt.NDArray[np.float64]:
    dist = 1.0 - (x[rows] @ x.T).astype(np.float64)
    dist[np.arange(rows.size), rows] = np.inf
    return dist


def _planar_distances(coords: npt.NDArray[np.float64], rows: IntArray) -> npt.NDArray[np.float64]:
    diff = coords[rows, None, :] - coords[None, :, :]
    dist: npt.NDArray[np.float64] = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    dist[np.arange(rows.size), rows] = np.inf
    return dist


def _knn(dist: npt.NDArray[np.float64], k: int) -> IntArray:
    """Indices of the k smallest distances per row, nearest first (ties by index)."""
    part = np.argpartition(dist, k - 1, axis=1)[:, :k]
    order = np.lexsort((part, np.take_along_axis(dist, part, axis=1)), axis=1)
    return np.take_along_axis(part, order, axis=1).astype(np.int64)


def neighborhood_scores(matrix: Matrix, coords: npt.ArrayLike, k: int) -> dict[str, float | int]:
    x = np.asarray(matrix, dtype=np.float32)
    y = np.asarray(coords, dtype=np.float64)
    n = x.shape[0]
    if y.shape[0] != n:
        raise ValueError(f"{y.shape[0]} coordinates for {n} embeddings")
    k = effective_k(k, n)
    penalty = 0.0
    overlap = 0.0
    for start in range(0, n, BLOCK):
        rows = np.arange(start, min(start + BLOCK, n), dtype=np.int64)
        d_orig = _original_distances(x, rows)
        ranks = np.empty_like(d_orig, dtype=np.int64)
        order = np.argsort(d_orig, axis=1, kind="stable")
        np.put_along_axis(ranks, order, np.arange(1, n + 1)[None, :], axis=1)
        nn_2d = _knn(_planar_distances(y, rows), k)
        excess = np.take_along_axis(ranks, nn_2d, axis=1) - k
        penalty += float(excess[excess > 0].sum())
        nn_orig = order[:, :k]
        for a, b in zip(nn_orig, nn_2d, strict=True):
            overlap += np.intersect1d(a, b, assume_unique=True).size / k
    trust = 1.0 - penalty * (2.0 / (n * k * (2.0 * n - 3.0 * k - 1.0)))
    return {"k": k, "trustworthiness": trust, "knn_overlap": overlap / n}


def probe_table(
    track_ids: Sequence[str],
    matrix: Matrix,
    coords: npt.ArrayLike,
    *,
    probes: int,
    neighbors: int,
    seed: int,
    labels: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Original vs 2D nearest neighbors of `probes` seeded-random tracks."""
    x = np.asarray(matrix, dtype=np.float32)
    y = np.asarray(coords, dtype=np.float64)
    n = len(track_ids)
    probes = min(probes, n)
    neighbors = min(neighbors, n - 1)
    if probes == 0 or neighbors == 0:
        return []
    labels = labels or {}
    picked = np.sort(np.random.default_rng(seed).choice(n, size=probes, replace=False))
    rows = picked.astype(np.int64)
    d_orig = _original_distances(x, rows)
    d_2d = _planar_distances(y, rows)
    nn_orig, nn_2d = _knn(d_orig, neighbors), _knn(d_2d, neighbors)

    def entry(j: int, **score: float) -> dict[str, Any]:
        return {"track_id": track_ids[j], "label": labels.get(track_ids[j]), **score}

    table = []
    for i, row in enumerate(rows):
        orig = [entry(int(j), cosine=round(1.0 - d_orig[i, j], 4)) for j in nn_orig[i]]
        planar = [entry(int(j), distance_2d=round(float(d_2d[i, j]), 4)) for j in nn_2d[i]]
        table.append(
            {
                "probe": entry(int(row)),
                "original_neighbors": orig,
                "map_neighbors": planar,
                "shared": len(set(nn_orig[i].tolist()) & set(nn_2d[i].tolist())),
            }
        )
    return table


def projection_quality(
    track_ids: Sequence[str],
    matrix: Matrix,
    coords: npt.ArrayLike,
    *,
    k: int,
    probes: int,
    probe_neighbors: int,
    seed: int,
    labels: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The content of `quality.json`."""
    scores = neighborhood_scores(matrix, coords, k)
    notes = []
    if scores["k"] != k:
        notes.append(f"k reduced from {k} to {scores['k']} (needs k < n / 2, n={len(track_ids)})")
    return {
        "n_points": len(track_ids),
        "k_requested": k,
        "k": scores["k"],
        "trustworthiness": round(float(scores["trustworthiness"]), 6),
        "knn_overlap": round(float(scores["knn_overlap"]), 6),
        "original_metric": "cosine",
        "map_metric": "euclidean_2d",
        "probe_neighbors": probe_table(
            track_ids,
            matrix,
            coords,
            probes=probes,
            neighbors=probe_neighbors,
            seed=seed,
            labels=labels,
        ),
        "notes": notes,
    }
