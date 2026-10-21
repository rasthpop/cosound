# P03 — CLAP Embeddings & Semantic Retrieval

**Goal:** versioned CLAP audio embeddings for the corpus and a text-to-audio retriever that returns ranked candidates — or an explicit "unavailable" status — without recomputing audio embeddings per request (Milestone 2).
**base.md:** §7.2, §7.3, §9.1–9.4, §15, §16.
**Depends on:** P02.T06, P02.T10

### P03.T01 — Checkpoint selection ADR
- **Skills:** clap-embeddings
- **Depends on:** P00.T05
- **Files:** docs/adr/0002-clap-checkpoint.md, .env.example
- **Do:**
  - Compare candidate checkpoints (music-specific LAION CLAP vs general vs HF `larger_clap_music`) on license, availability, pinning, CPU speed, footprint. Choose one; record `model_id`, download URL, SHA256, package versions, amodel/fusion flags, sample rate.
- **Done when:**
  - ADR accepted by the user; `CLAP_CHECKPOINT`/`CLAP_MODEL_VERSION` documented; download script or instructions verify the hash.
- **Status:** [~]

### P03.T02 — Embedding utilities & versioned store
- **Skills:** clap-embeddings, domain-modeling
- **Depends on:** P01.T06
- **Files:** src/music_discovery/audio/embedding_store.py, src/music_discovery/domain/vectors.py (pure normalize/cosine helpers), tests/unit/audio/test_embedding_store.py, tests/unit/domain/test_vectors.py
- **Do:**
  - `l2_normalize`, `cosine` with zero/NaN → `InvalidEmbedding`; store layout (`audio_embeddings.npy`, `track_ids.json`, `meta.json`, `failures.csv`) under `data/embeddings/{embedding_version}/`; version hashing; load-time model check → `EmbeddingVersionMismatch`.
- **Done when:**
  - Tests: normalization, invalid vectors raise, round-trip store, mismatched model refused, row/id alignment preserved.
- **Status:** [x]

### P03.T03 — CLAP encoder
- **Skills:** clap-embeddings
- **Depends on:** P03.T01, P03.T02
- **Files:** src/music_discovery/audio/clap_encoder.py, tests/integration/audio/test_clap_encoder.py (slow)
- **Do:**
  - `ClapEncoder` implementing `AudioEncoder` + `TextEncoder`: explicit checkpoint path, lazy load, eval/no-grad, batching, single-item batch handling, `model_id`/`embedding_dim`, `ModelLoadError`.
- **Done when:**
  - Slow test encodes 2 tiny clips and 3 texts with correct shapes, unit norms after normalization, and deterministic output across two runs.
  - Unit test: missing checkpoint ⇒ `ModelLoadError` without crashing the importer.
- **Status:** [x]

### P03.T04 — Offline embedding generation script
- **Skills:** clap-embeddings, fma-audio-corpus
- **Depends on:** P03.T03, P02.T10
- **Files:** scripts/build_embeddings.py, tests/integration/test_build_embeddings.py
- **Do:**
  - Steps base §9.1 1–8: manifest → validate files → load model → encode batches → normalize → persist with meta (model, ckpt hash, package versions, preprocessing, manifest hash) → failures report. Idempotent per `embedding_version`; `--force`.
  - Update `TrackAudio.embedding_*` fields in the catalog.
- **Done when:**
  - With `FakeEncoder` (injected via flag/test): artifacts written, failures reported for a missing and a corrupt file, re-run is a no-op.
  - Real run on the 20-track manifest produces embeddings for every valid file (record counts in Notes).
- **Status:** [~]

### P03.T05 — Vector index
- **Skills:** clap-embeddings
- **Depends on:** P03.T02
- **Files:** src/music_discovery/infrastructure/vector_index.py, scripts/build_indexes.py, tests/unit/infrastructure/test_vector_index.py
- **Do:**
  - `NumpyCosineIndex` (exact, top-k via argpartition, `restrict_to`, `get`, `__contains__`, `model_id`) loaded from the embedding store; FAISS left as optional implementation behind the same protocol.
  - `build_indexes.py` validates and writes any index metadata.
- **Done when:**
  - Tests: top-k order vs brute force, `restrict_to`, missing id ⇒ `None`/absent, model mismatch on query raises `EmbeddingVersionMismatch`.
- **Status:** [x]

### P03.T06 — Deterministic semantic prompt builder
- **Skills:** clap-embeddings, agent-orchestration
- **Depends on:** P01.T03
- **Files:** src/music_discovery/retrieval/prompt_builder.py, tests/unit/retrieval/test_prompt_builder.py
- **Do:**
  - Templates over spec attributes; ≤ 4 deduplicated prompts; never introduces attributes absent from the spec.
- **Done when:**
  - Tests for "Something chill with a flute" and two other queries; no prompt contains an attribute absent from the spec.
- **Status:** [x]

### P03.T07 — SemanticRetriever
- **Skills:** clap-embeddings, hybrid-retrieval
- **Depends on:** P03.T05, P03.T06
- **Files:** src/music_discovery/retrieval/semantic_retriever.py, tests/unit/retrieval/test_semantic_retriever.py
- **Do:**
  - Original query + expansions → text embeddings → index search → documented prompt-combination rule → `SemanticResult(items, model_id, status)`; reference-track query vectors; unavailable encoder/index ⇒ `status="unavailable"` with a reason.
- **Done when:**
  - Tests with fakes: tracks without embeddings absent (not zero); unavailable path returns empty + status; expansions can't outweigh the original query beyond the configured rule.
- **Status:** [x]

### P03.T08 — Semantic search smoke CLI (M2 acceptance)
- **Skills:** clap-embeddings
- **Depends on:** P03.T04, P03.T07
- **Files:** scripts/semantic_search.py
- **Do:**
  - `uv run python scripts/semantic_search.py "something chill with a flute" -k 5` prints track id, title, artist, raw cosine, rank, model_id.
- **Done when:**
  - Command runs on the real 20-track corpus and returns ranked candidates; output pasted in Notes (no quality claim).
- **Status:** [ ]

## Exit criteria (Milestone 2)
- [ ] A text query retrieves ranked candidates from the local audio corpus (P03.T08).
- [ ] Embeddings persisted with model/version metadata; mixing checkpoints is impossible.
- [ ] Missing audio and invalid embeddings are handled explicitly and tested.
