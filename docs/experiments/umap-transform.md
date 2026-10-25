# Experiment: UMAP `transform()` for new tracks (P07.T07)

**Date:** 2026-10-25 · **Decision:** do not use `transform()`; catalog changes require an explicit
rebuild with `scripts/build_map.py`.

## Question

base.md §11.3 allows placing new tracks into a fitted projection with UMAP's `transform` instead of
refitting, but only after testing it. Is it good enough to use for incremental catalog updates?

## Setup

- Embeddings `ev-bbaddcb7bdc4` (CLAP `larger_clap_music_and_speech`, 7,993 fma_small tracks).
- UMAP parameters from `config/umap.yaml`: `n_neighbors=15`, `min_dist=0.1`, `metric=cosine`,
  `init=spectral`, `random_state=42`; umap-learn 0.5.12.
- Held out a seeded 20 % (1,599 tracks, seed 42). Fitted on the other 80 %, transformed the held-out
  tracks into that map, and compared with a full refit on all 7,993 tracks.
- Metrics at k = 10 (same definitions as `spatial/quality.py`):
  - **kNN overlap**: share of a track's 10 original-space (cosine) neighbors that are also among its
    10 nearest points on the map.
  - **trustworthiness**: penalizes map neighbors that are far apart in the original space.
  - **neighbor gap**: median 2D distance from a track to its 10 original-space neighbors, divided by
    the median distance between random pairs. Scale-free; lower means better placed.
- Reproduce: `uv run python scripts/experiments/umap_transform_check.py`
  (output: `artifacts/experiments/umap_transform/ev-bbaddcb7bdc4.json`).

## Results

| | Full refit | 80 % fit + transform |
|---|---:|---:|
| trustworthiness@10 (all points) | 0.9555 | 0.9524 |
| kNN overlap@10, all points | 0.267 | 0.233 |
| kNN overlap@10, **held-out points** | 0.274 | **0.191** |
| kNN overlap@10, fitted points | — | 0.243 |
| neighbor gap, **held-out points** | 0.049 | **0.064** |
| neighbor gap, fitted points | — | 0.053 |

| Time (CPU, single thread) | Seconds |
|---|---:|
| full fit, 7,993 tracks | 23.9 |
| fit on 6,394 tracks | 6.1 |
| transform 1,599 tracks | 11.8 |

`transform` is deterministic: transforming the same tracks twice gave identical coordinates
(max shift 0.0).

## Reading

- Global structure survives: trustworthiness barely moves (0.955 → 0.952), so transformed tracks
  rarely land somewhere absurd.
- Local structure for the new tracks is clearly worse. They keep about 30 % fewer of their true
  neighbors (0.274 → 0.191), and land about 30 % farther from them (gap 0.049 → 0.064). The map is
  meant for exploring local neighborhoods, so this is the part that matters.
- The fitted 80 % also does slightly worse (0.243) than in the full refit, because it was fitted on
  less data.
- A full refit is cheap at this catalog size (about 25–45 s, including the build script's overhead),
  so the speed of `transform` does not buy anything.
- To use `transform`, the fitted reducer would also have to be persisted (a pickled numba-backed
  object), versioned and validated next to the coordinates. That is more artifact surface for a
  worse result.
- Limitation: 20 % is a large batch. Adding a handful of tracks would probably degrade less, but
  that was not measured, and the MVP has no incremental catalog-update flow anyway.

## Decision

- Do **not** use `transform()` in the MVP. `UmapProjector` does not persist the reducer.
- Any catalog or embedding change means an explicit rebuild: `scripts/build_map.py` makes a new
  content-addressed `projection_version`, and the loader rejects stale projections
  (`ProjectionMismatch`). The map then reports itself unavailable instead of showing wrong
  coordinates.
- Revisit only if the catalog grows enough that refitting gets expensive (on the order of 100k
  tracks), and then re-run this script with realistic batch sizes.
