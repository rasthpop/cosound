# P04 — Hybrid Retrieval, Constraints, Ranking & Diversity

**Goal:** the deterministic relevance engine: metadata + semantic (+ optional relationship) retrieval, provenance-preserving merge, reliable hard constraints, transparent weighted ranking that handles missing modalities, MMR diversity, and three comparable modes (Milestone 3).
**base.md:** §7.1, §7.4–7.6, §9.4, §16.
**Depends on:** P03

### P04.T01 — Lexical index & MetadataRetriever
- **Skills:** hybrid-retrieval
- **Depends on:** P02.T09, P01.T06
- **Files:** src/music_discovery/retrieval/metadata_retriever.py, src/music_discovery/infrastructure/lexical_index.py, tests/unit/retrieval/test_metadata_retriever.py
- **Do:**
  - `LexicalIndex` implementation (SQLite FTS5 or in-memory BM25) over titles, artists/aliases, genres, styles, labels, tracklist text, FMA tags; year/era matching; synonym expansion via lexicon hook (stub until P06.T01).
  - Output raw score + `matched_fields` (field, term, source, kind).
  - **MVP (ADR-0005):** the catalog is FMA-only, so the indexed fields are title, artist name, album title, genre names (`genres`, with the `genres_all` parents) and FMA `tags`. Discogs styles, labels and tracklists are empty until post-MVP.
- **Done when:**
  - Tests: genre tag match, artist alias match, era range match, lexical "flute" in title flagged as `lexical` not instrument evidence; works with semantic components absent.
- **Status:** [ ]

### P04.T02 — CandidateMerger
- **Skills:** hybrid-retrieval
- **Depends on:** P04.T01, P03.T07
- **Files:** src/music_discovery/retrieval/candidate_merger.py, tests/unit/retrieval/test_candidate_merger.py
- **Do:**
  - Union by track id, per-source (raw score, rank), `retrieval_sources`, back-fill scores for `not_retrieved` candidates (semantic `restrict_to`, metadata recompute), `not_available` ⇒ `None`; pool size config.
- **Done when:**
  - Tests: dedupe, provenance preserved, back-fill vs not-available distinguished, pool cap honored.
- **Status:** [ ]

### P04.T03 — Score normalization strategies
- **Skills:** hybrid-retrieval
- **Depends on:** P04.T02
- **Files:** src/music_discovery/retrieval/normalization.py, tests/unit/retrieval/test_normalization.py
- **Do:**
  - `minmax`, `rank`, `zscore_sigmoid`, `calibrated` (params from config); ignore missing values; degenerate-pool fallback to `rank` with a trace note.
- **Done when:**
  - Tests per strategy, missing values untouched, degenerate pools fall back and log.
- **Status:** [ ]

### P04.T04 — Hard-constraint evaluation & no-confident-match
- **Skills:** hybrid-retrieval, domain-modeling
- **Depends on:** P04.T02
- **Files:** src/music_discovery/retrieval/constraints.py, tests/unit/retrieval/test_constraints.py
- **Do:**
  - Per-constraint evaluators returning `ConstraintResult(status, evidence)`; reliable vs weak evidence table from the skill; `unknown` policy (`keep_flagged`/`demote`/`exclude`); VIOLATED always excluded; empty result ⇒ `NO_CONFIDENT_MATCH` with reasons (never relax silently).
- **Done when:**
  - Tests: top-scoring violator excluded; unknown handling per policy; weak evidence never decides; NO_CONFIDENT_MATCH returned with constraint list.
- **Status:** [ ]

### P04.T05 — HybridRanker & retrieval config
- **Skills:** hybrid-retrieval
- **Depends on:** P04.T03, P04.T04
- **Files:** src/music_discovery/retrieval/ranker.py, config/retrieval.yaml, src/music_discovery/retrieval/config.py, tests/unit/retrieval/test_ranker.py
- **Do:**
  - Weighted sum with renormalization over available signals, optional `coverage_penalty`, negative-reference and negative-preference terms, excluded ids; `ScoreBreakdown` with `weights_version`; config loaded/validated (weights, normalization, pool size, constraint policy, λ, thresholds).
- **Done when:**
  - Tests: missing-modality scenarios from the skill; evaluated-low semantic ≠ missing semantic; weights only from config; relationship weight 0 by default.
- **Status:** [ ]

### P04.T06 — MMR diversity reranker
- **Skills:** hybrid-retrieval
- **Depends on:** P04.T05
- **Files:** src/music_discovery/retrieval/diversity.py, tests/unit/retrieval/test_diversity.py
- **Do:**
  - MMR with λ from spec diversity × config scale; similarity = audio cosine, fallback catalog Jaccard, same master/release = duplicate; deterministic ties.
- **Done when:**
  - Tests: λ=1 equals relevance order; first item always top relevance; duplicate versions spread; deterministic output.
- **Status:** [ ]

### P04.T07 — HybridRetriever composition, modes & trace
- **Skills:** hybrid-retrieval
- **Depends on:** P04.T06
- **Files:** src/music_discovery/retrieval/hybrid_retriever.py, tests/integration/retrieval/test_hybrid_retriever.py
- **Do:**
  - Compose retrievers → merger → constraints → normalization → ranker → MMR; modes `metadata_only` / `semantic_only` / `hybrid`; semantic-unavailable degradation; full `RetrievalTrace`.
- **Done when:**
  - Integration test on a small real local index (fake or real encoder) runs all three modes; `metadata_only` never calls the encoder; degraded flag set when semantic is unavailable.
- **Status:** [ ]

### P04.T08 — RelationshipRetriever (optional signal)
- **MVP:** FMA relationships only (same artist, same album); label/master/style edges arrive with Discogs post-MVP.
- **Skills:** hybrid-retrieval, fma-audio-corpus
- **Depends on:** P04.T07, P02.T07
- **Files:** src/music_discovery/retrieval/relationship_retriever.py, tests/unit/retrieval/test_relationship_retriever.py
- **Do:**
  - Score candidates by relationship edges to reference tracks / strong candidates; contributes only when weight > 0 in config; never labeled as audio similarity.
- **Done when:**
  - Tests pass with weight 0 (no effect) and weight > 0 (expected boost); evaluation decides whether to enable (P05.T06).
- **Status:** [ ]

### P04.T09 — Side-by-side baseline runner (M3 acceptance)
- **Skills:** hybrid-retrieval, retrieval-evaluation
- **Depends on:** P04.T07
- **Files:** scripts/compare_baselines.py
- **Do:**
  - For a list of query texts (deterministic parser stub or hand-built specs until P06), run all three modes on the same catalog and print/CSV the top-k with score breakdowns.
- **Done when:**
  - Runs on the 20-track corpus; output CSV in `artifacts/evaluation/scratch/` (git-ignored); identical across two runs.
- **Status:** [ ]

## Exit criteria (Milestone 3, part 1)
- [ ] All three retrieval approaches run against the same catalog and can be compared.
- [ ] Hard constraints enforced independently of weighted score; NO_CONFIDENT_MATCH path tested.
- [ ] Missing modalities never treated as zero.
