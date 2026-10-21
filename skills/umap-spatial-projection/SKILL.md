---
name: umap-spatial-projection
description: The offline spatial pipeline — building the aligned feature matrix from persisted CLAP embeddings, fitting a seeded UMAP projection, persisting coordinates with full metadata, validating artifact/track alignment, measuring neighborhood preservation, and serving map points and original-space neighbors. Load for src/music_discovery/spatial/, scripts/build_map.py, map/neighbor services, or questions about what map coordinates mean.
---

# UMAP Spatial Projection

Spec: `base.md` §11, §13.4–13.5, §12.7 (UMAP), §16. Reference: https://umap-learn.readthedocs.io/en/latest/

## 1. Invariants

- UMAP runs **only** in `scripts/build_map.py` (offline / explicit rebuild). The request path reads persisted coordinates.
- Search works when the projection is missing (`ProjectionMissing` ⇒ map endpoints return 503-style "unavailable", search unaffected).
- Neighbors come from the **original embedding space**, never 2D distances.
- MVP: one audio-based projection for tracks with embeddings. Tracks without audio are **excluded** (or, later, a separately-labeled metadata projection — never mixed).

## 2. Feature builder (`spatial/feature_builder.py`)

Load the embedding store for the configured `embedding_version` → matrix `X (n, d)` + `track_ids` (row order) → validate shape, finiteness, unit norm, no duplicate ids, every id exists in the catalog. Metadata-augmented features are a **separate experiment** with an explicit normalization/weighting doc; not in MVP.

## 3. Projector (`spatial/umap_projector.py`)

```python
import umap
reducer = umap.UMAP(n_components=2, n_neighbors=cfg.n_neighbors, min_dist=cfg.min_dist,
                    metric="cosine", random_state=cfg.random_state, transform_seed=cfg.random_state)
coords = reducer.fit_transform(X)
```

- Setting `random_state` makes the run reproducible but disables parallelism — accept it.
- **Small corpora:** `n_neighbors` must be `< n`. For the 20-track corpus use `min(cfg.n_neighbors, n - 1)` and record the effective value; note in the report that a 20-point UMAP is illustrative only. Spectral init can fail on tiny/disconnected graphs — fall back to `init="random"` and record it.
- Optionally center/scale coordinates to a fixed range (record the transform) so renderers get sane bounds; raw UMAP values have no units.
- Persist the fitted reducer (`joblib`) **only** if `transform` of new points is going to be used; test `transform` stability before relying on it (base §11.3).

## 4. Persistence (`spatial/spatial_repository.py` + infrastructure storage)

```
artifacts/umap/{projection_version}/
├── coordinates.parquet   # track_id, x, y  (row order = track_ids.json of the embedding version)
├── meta.json             # projection_version, embedding_version, model_id, preprocessing version,
│                         # umap params (requested + effective), random_state, umap-learn/numpy versions,
│                         # created_at, n_points, coordinate transform, sha256 of coordinates
└── quality.json          # trustworthiness@k, kNN overlap@k, notes
```

`projection_version` = `umap-` + short hash of (embedding_version + params). `config: ACTIVE_PROJECTION_VERSION`. Loader validates: embedding_version matches the active embedding store, every track_id exists, counts match ⇒ else `ProjectionMismatch` (map unavailable, logged).

Coordinates may also be copied into `Track.spatial_x/y` for convenience, but the artifact is the source of truth and carries the version.

## 5. Quality (`spatial/quality.py`)

- `sklearn.manifold.trustworthiness(X, coords, n_neighbors=k, metric="cosine")`.
- kNN overlap@k: mean |N_k^orig(i) ∩ N_k^2D(i)| / k.
- Manual check list: pick 3 tracks, list their 3 nearest neighbors in original vs 2D space, write to `quality.json` notes. Visual attractiveness is not a criterion.

## 6. Services

- `application/map_service.py`: `list_points(filters, limit, cursor)` — filters `genre`, `style`, `artist_id`, `has_audio`; keyset pagination on `(track_id)`; returns `x, y, title, artist, genre, style, source_url, projection_version`. Never returns embeddings.
- `spatial/neighbor_service.py`: `neighbors(track_id, k)` via `VectorIndex` (original space), `metric="clap_cosine"` in the response. Track without embedding ⇒ empty list with `reason="no_audio_embedding"` (or a clearly-labeled relationship-based fallback, metric `"catalog_relationship"`).

## 7. Tests

- Determinism: same X + seed ⇒ identical coordinates (allclose) — `slow` marker for real UMAP; unit tests use a fake projector.
- Alignment: shuffled ids, missing ids, extra ids, non-finite rows ⇒ errors.
- Small-n parameter clamping.
- Map service pagination, filters, and the "projection unavailable" path.
- Neighbor service never reads 2D coords (fake index asserted).
