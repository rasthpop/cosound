"""Can UMAP `transform()` place new tracks instead of a full rebuild? (P07.T07, base.md §11.3)

    uv run python scripts/experiments/umap_transform_check.py [--holdout 0.2] [--seed 42]

Fits config/umap.yaml parameters on a seeded subset of the active embeddings, transforms the
held-out tracks into that map, and compares with a full refit on all tracks:

- neighborhood preservation of the held-out points (kNN overlap@k with their original-space
  neighbors; trustworthiness@k of the whole layout),
- where held-out points land relative to their original-space neighbors in the same map,
- transform determinism (same input twice).

Writes artifacts/experiments/umap_transform/<embedding_version>.json and prints it.
Nothing here is used by the request path; it only informs the decision in
docs/experiments/umap-transform.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import numpy.typing as npt
import umap

from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.infrastructure.settings import get_settings
from music_discovery.spatial.quality import neighborhood_scores
from music_discovery.spatial.umap_projector import MapConfig, UmapParams

Floats = npt.NDArray[np.float64]


def fit(x: npt.NDArray[np.float32], params: UmapParams) -> umap.UMAP:
    reducer = umap.UMAP(
        n_components=params.n_components,
        n_neighbors=params.n_neighbors,
        min_dist=params.min_dist,
        metric=params.metric,
        init=params.init,
        random_state=params.random_state,
        transform_seed=params.random_state,
        n_jobs=1,
    )
    reducer.fit(x)
    return reducer


def knn_rows(dist: Floats, k: int) -> npt.NDArray[np.int64]:
    return np.argsort(dist, axis=1, kind="stable")[:, :k].astype(np.int64)


def heldout_overlap(
    x: npt.NDArray[np.float32], coords: Floats, rows: npt.NDArray[np.int64], k: int
) -> float:
    """Mean kNN overlap@k of the given rows, neighbors searched among all points."""
    d_orig = 1.0 - (x[rows] @ x.T).astype(np.float64)
    d_orig[np.arange(rows.size), rows] = np.inf
    diff = coords[rows, None, :] - coords[None, :, :]
    d_2d = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    d_2d[np.arange(rows.size), rows] = np.inf
    a, b = knn_rows(d_orig, k), knn_rows(d_2d, k)
    return float(np.mean([np.intersect1d(p, q).size / k for p, q in zip(a, b, strict=True)]))


def neighbor_gap(
    x: npt.NDArray[np.float32],
    coords: Floats,
    rows: npt.NDArray[np.int64],
    k: int,
) -> float:
    """Median 2D distance from each row to its k original-space neighbors, divided by the
    median 2D distance between random point pairs (scale-free; lower = better placed)."""
    d_orig = 1.0 - (x[rows] @ x.T).astype(np.float64)
    d_orig[np.arange(rows.size), rows] = np.inf
    nn = knn_rows(d_orig, k)
    gaps = np.linalg.norm(coords[nn] - coords[rows][:, None, :], axis=2)
    rng = np.random.default_rng(0)
    i, j = rng.integers(0, len(coords), 20000), rng.integers(0, len(coords), 20000)
    baseline = float(np.median(np.linalg.norm(coords[i] - coords[j], axis=1)))
    return float(np.median(gaps)) / baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--holdout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    settings = get_settings()
    config = MapConfig.load(
        settings.project_root / "config" / "umap.yaml",
        random_state=settings.umap_random_state,
        n_components=settings.umap_n_components,
    )
    params, k = config.umap, config.quality.k
    directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
    store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    _, x = store.matrix()
    n = x.shape[0]

    rng = np.random.default_rng(args.seed)
    held = np.sort(rng.choice(n, size=round(n * args.holdout), replace=False))
    train = np.setdiff1d(np.arange(n), held)

    t0 = time.perf_counter()
    full = np.asarray(fit(x, params).embedding_, dtype=np.float64)
    t_full = time.perf_counter() - t0

    t0 = time.perf_counter()
    partial = fit(x[train], params)
    t_partial = time.perf_counter() - t0
    t0 = time.perf_counter()
    placed = np.asarray(partial.transform(x[held]), dtype=np.float64)
    t_transform = time.perf_counter() - t0
    placed_again = np.asarray(partial.transform(x[held]), dtype=np.float64)

    combined = np.empty((n, 2), dtype=np.float64)
    combined[train] = partial.embedding_
    combined[held] = placed

    full_scores = neighborhood_scores(x, full, k)
    combined_scores = neighborhood_scores(x, combined, k)
    result: dict[str, Any] = {
        "embedding_version": store.embedding_version,
        "n": n,
        "n_heldout": int(held.size),
        "seed": args.seed,
        "k": k,
        "umap": params.model_dump(mode="json"),
        "umap_learn": umap.__version__,
        "seconds": {
            "full_fit": round(t_full, 1),
            "subset_fit": round(t_partial, 1),
            "transform_heldout": round(t_transform, 1),
        },
        "full_refit": {
            "trustworthiness": round(float(full_scores["trustworthiness"]), 4),
            "knn_overlap_all": round(float(full_scores["knn_overlap"]), 4),
            "knn_overlap_heldout": round(heldout_overlap(x, full, held, k), 4),
            "neighbor_gap_heldout": round(neighbor_gap(x, full, held, k), 4),
        },
        "subset_fit_plus_transform": {
            "trustworthiness": round(float(combined_scores["trustworthiness"]), 4),
            "knn_overlap_all": round(float(combined_scores["knn_overlap"]), 4),
            "knn_overlap_heldout": round(heldout_overlap(x, combined, held, k), 4),
            "knn_overlap_train": round(heldout_overlap(x, combined, train, k), 4),
            "neighbor_gap_heldout": round(neighbor_gap(x, combined, held, k), 4),
            "neighbor_gap_train": round(neighbor_gap(x, combined, train, k), 4),
        },
        "transform_deterministic": bool(np.allclose(placed, placed_again)),
        "transform_max_repeat_shift": float(np.max(np.abs(placed - placed_again))),
        "created_at": datetime.now(UTC).isoformat(),
    }
    out_dir = settings.artifacts_dir / "experiments" / "umap_transform"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{store.embedding_version}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
