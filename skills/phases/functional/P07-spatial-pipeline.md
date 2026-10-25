# P07 — UMAP Spatial Pipeline, Map & Neighbor Services

**Goal:** a stable, versioned 2D projection of tracks with audio embeddings, built offline, validated against track IDs, and served by map/neighbor services that never run UMAP and never use 2D distance for recommendations (Milestone 5).
**base.md:** §11, §13.4, §13.5, §12.7 (UMAP), §16.
**Depends on:** P03.T04 (embeddings). Runs in parallel with P04–P06.

### P07.T01 — Feature builder & matrix validation
- **Skills:** umap-spatial-projection, clap-embeddings
- **Depends on:** P03.T02
- **Files:** src/music_discovery/spatial/feature_builder.py, tests/unit/spatial/test_feature_builder.py
- **Do:**
  - Load embedding store for the active version; align rows with track ids; validate shape/finite/unit-norm/unique ids/catalog existence; exclude tracks without audio (logged count).
- **Done when:**
  - Tests: shuffled ids, duplicates, NaN rows, unknown ids each raise; exclusion count reported.
- **Notes:** Alignment errors raise the new `FeatureAlignmentError` (code `feature_alignment_error`); matrix content errors raise `InvalidEmbedding`.
- **Status:** [x]

### P07.T02 — UMAP projector & build script
- **Skills:** umap-spatial-projection
- **Depends on:** P07.T01
- **Files:** src/music_discovery/spatial/umap_projector.py, config/umap.yaml, scripts/build_map.py, tests/integration/spatial/test_umap_projector.py (slow)
- **Do:**
  - Seeded UMAP with explicit params from config/settings; small-n clamping of `n_neighbors`; init fallback; optional coordinate normalization (recorded); `build_map.py` orchestrates load → fit → persist → quality.
- **Done when:**
  - Slow test: two runs ⇒ allclose coordinates; 20-point corpus works with clamped params recorded in meta.
  - Unit test with a fake projector covers the script flow.
- **Notes:** Orchestration lives in `spatial/map_builder.py` (collaborators injected) so the script is a thin composition root and the fake-projector test runs the real flow. Coordinates are normalized into [-1, 1] (transform in meta). Real run on fma_small (2026-10-25): 7,993 points, 7 tracks without audio excluded, ~45 s, trustworthiness@10 0.955, kNN overlap@10 0.267.
- **Status:** [x]

### P07.T03 — Projection persistence & loader validation
- **Skills:** umap-spatial-projection
- **Depends on:** P07.T02
- **Files:** src/music_discovery/spatial/spatial_repository.py, src/music_discovery/infrastructure/spatial_store.py, tests/unit/spatial/test_spatial_repository.py
- **Do:**
  - Write `coordinates.parquet` (or CSV), `meta.json` (all base §11.3 fields + effective params + hashes); loader checks embedding version, id set, counts ⇒ `ProjectionMismatch` / `ProjectionMissing`; optional copy into `Track.spatial_x/y`.
- **Done when:**
  - Tests: valid load; mismatched embedding version, missing ids, corrupted file each produce the right error; search code path does not import `umap` (boundary check).
- **Notes:** CSV instead of parquet (no pyarrow dependency); floats via `repr` so the sha256 round-trips. `ProjectionMeta`/`ProjectionArtifact` in `domain/schemas.py` and a new `ProjectionStore` protocol (fake: `InMemoryProjectionStore`) so `spatial/` validates without importing infrastructure. Loader also rejects projections whose id set differs from the embedding store. Copy into `Track.spatial_x/y` not done: the artifact stays the only source.
- **Status:** [x]

### P07.T04 — Projection quality metrics
- **Skills:** umap-spatial-projection, retrieval-evaluation
- **Depends on:** P07.T02
- **Files:** src/music_discovery/spatial/quality.py, tests/unit/spatial/test_quality.py
- **Do:**
  - Trustworthiness@k, kNN overlap@k, manual neighbor table (3 probe tracks) into `quality.json`.
- **Done when:**
  - Tests on a synthetic dataset where the expected overlap is known; `quality.json` produced by `build_map.py`.
- **Notes:** Trustworthiness is computed in row blocks (own implementation, checked against `sklearn.manifold.trustworthiness` in tests) so 8k tracks need no n-by-n matrices; k is reduced to < n/2 for tiny corpora and the reduction noted. Probe table entries carry `title — artist` labels.
- **Status:** [x]

### P07.T05 — Map service
- **Skills:** umap-spatial-projection, api-contracts
- **Depends on:** P07.T03
- **Files:** src/music_discovery/application/map_service.py, tests/unit/application/test_map_service.py
- **Do:**
  - `list_points(filters, limit, cursor)` with keyset pagination; filters genre/style/artist_id/has_audio; `meta()` with projection_version, bounds, counts, availability; unavailable projection ⇒ explicit status (not exception leak).
- **Done when:**
  - Tests: pagination stable & complete, filters, bounded limit, no embeddings in output, unavailable path.
- **Notes:** `MapService.from_loader` turns `ProjectionMissing`/`ProjectionMismatch` into `status="unavailable"` + the error code. Points are built once and cached (catalog and projection are static while the app runs). Every point is in the audio projection, so `has_audio` is always true and `has_audio=false` returns no points. `limit` default 500, max 5000. Points carry `source_url` (ADR-0005), not `discogs_url`. Smoke-tested on the real catalog: 7,993 points, loaded in ~0.8 s.
- **Status:** [x]

### P07.T06 — Neighbor service (original space)
- **Skills:** umap-spatial-projection, clap-embeddings
- **Depends on:** P03.T05
- **Files:** src/music_discovery/spatial/neighbor_service.py, tests/unit/spatial/test_neighbor_service.py
- **Do:**
  - k nearest via `VectorIndex` with `metric="clap_cosine"`; no-embedding track ⇒ empty + reason, or labeled relationship fallback (`metric="catalog_relationship"`).
- **Done when:**
  - Test asserts 2D coordinates are never read (fake spatial repo raises if accessed).
- **Notes:** The service takes no spatial repository at all; the test checks its signature rejects one and that the module never refers to coordinates/projections. Fallback neighbors are ordered same_release > same_master > same_artist > same_label > shared_style; unknown relationship weights stay `None`. `k` capped at 50.
- **Status:** [x]

### P07.T07 — `transform()` for new points (experiment, optional)
- **Skills:** umap-spatial-projection
- **Depends on:** P07.T03
- **Files:** docs/experiments/umap-transform.md, scripts/experiments/umap_transform_check.py
- **Do:**
  - Fit on a subset, transform held-out points, compare with full refit (trustworthiness, displacement). Decide whether incremental updates are acceptable; until then catalog changes require an explicit rebuild.
- **Done when:**
  - Experiment doc with numbers and a decision.
- **Notes:** Run on the full fma_small embeddings (80/20 seeded split): held-out kNN overlap@10 0.191 vs 0.274 for a full refit; trustworthiness 0.952 vs 0.955; full refit ~24 s. Decision: no `transform()` in the MVP, catalog changes require an explicit rebuild (see the doc).
- **Status:** [x]

## Exit criteria (Milestone 5)
- [x] Backend returns stable map coordinates without recalculating UMAP during searches.
- [x] Coordinate ↔ track-id alignment validated on load.
- [x] Neighbors computed in the original embedding space.
