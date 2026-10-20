---
name: hybrid-retrieval
description: The deterministic relevance engine — MetadataRetriever, RelationshipRetriever, CandidateMerger with provenance, score normalization, tri-state hard-constraint filtering, the weighted HybridRanker with explicit missing-modality handling, MMR diversity reranking, and the no-confident-match state. Load for any work in src/music_discovery/retrieval/ (except CLAP internals), ranking config, or when debugging why a track ranked where it did.
---

# Hybrid Retrieval & Ranking

Spec: `base.md` §7 (all), §9.4, §16. This engine must run **without any LLM and without agents** — the evaluation baselines call it directly.

## 1. Pipeline & module map

```
SearchSpecification
  ├─ MetadataRetriever        retrieval/metadata_retriever.py
  ├─ SemanticRetriever        retrieval/semantic_retriever.py   (see clap-embeddings)
  └─ RelationshipRetriever    retrieval/relationship_retriever.py (optional, late)
        ↓
  CandidateMerger             retrieval/candidate_merger.py
        ↓
  ConstraintFilter            retrieval/constraints.py
        ↓
  ScoreNormalizer             retrieval/normalization.py
        ↓
  HybridRanker                retrieval/ranker.py
        ↓
  MMRReranker                 retrieval/diversity.py
        ↓
  RankedCandidateSet (+ RetrievalTrace)
```

`retrieval/hybrid_retriever.py` composes these with a `RetrievalConfig` and supports **modes** `metadata_only`, `semantic_only`, `hybrid` — the three evaluation systems are the same code path with different modes.

## 2. MetadataRetriever

- Index over normalized catalog fields: track/release title, artist names + aliases, genres, styles, labels, year, tracklist text, FMA genres/tags. Use SQLite FTS5 or an in-memory BM25 (`rank-bm25`) behind a `LexicalIndex` protocol.
- Query terms come from the spec: preference values (+ lexicon synonyms) and the original query tokens. Genre/style preferences match tags; era preferences match year ranges.
- Output per track: `metadata_score_raw`, `matched_fields: list[FieldMatch(field, term, source)]`. The matched fields become explanation evidence.
- **Tags do not encode audible attributes.** A "flute" token matching a *title* is a lexical match, not instrument evidence (`FieldMatch.kind = "lexical"`).

## 3. CandidateMerger

- Union by internal `track_id`; each candidate keeps `{source: (raw_score, rank)}` for every retriever that returned it, plus `retrieval_sources`.
- A candidate missing from a retriever ⇒ that signal is **missing** for ranking, unless the retriever *did* evaluate it (e.g. semantic retriever scoring a restricted pool). Distinguish:
  - `not_retrieved` — scored but outside top-k → fetch its actual score via `restrict_to` (semantic) or recompute (metadata) so ranking isn't biased by cutoff;
  - `not_available` — modality absent for that track (no embedding) → `None`.
- Pool size target 50–100 (config); for the 20-track corpus the pool is the whole corpus — record that in the trace.

## 4. Hard constraints (`retrieval/constraints.py`)

Each constraint evaluates per track to `SATISFIED | VIOLATED | UNKNOWN` with the evidence used:

| Constraint | Reliable evidence | Weak evidence (flag only) |
|---|---|---|
| vocals excluded/required | human label, curated metadata (e.g. Discogs credits "Vocals", style "Instrumental" on track) | echonest `instrumentalness` (estimated), CLAP — never decisive |
| genre required/excluded | genre/style tags (source-labeled) | — |
| era range | year | — |
| duration range | duration | — |
| instrument required | human label only | CLAP score, tags — never decisive |

Policy (`ConstraintPolicy.unknown`): `keep_flagged` (default) | `demote` | `exclude`. `VIOLATED` is always excluded **independently of the weighted score**. If nothing remains with `SATISFIED` or tolerated `UNKNOWN`, return `SearchOutcome.NO_CONFIDENT_MATCH` with the reasons — **never relax constraints silently**.

## 5. Score normalization (`retrieval/normalization.py`)

Strategies (config `normalization.semantic`, `normalization.metadata`): `minmax` (per query over the pool), `rank` (`1 - (rank-1)/(n-1)` or reciprocal), `zscore→sigmoid`, `calibrated` (affine fit on **dev split only**, stored in config with its fit date). Rules:

- Normalize only over candidates that *have* the signal.
- Degenerate pools (n < 3 or zero variance) fall back to `rank` and log it.
- CLAP cosines live in a narrow band; never present raw cosine as a probability.

Pick the default strategy using the dev split in P05; document it in `config/retrieval.yaml`.

## 6. HybridRanker (`retrieval/ranker.py`)

```
S(t,q) = Σ_i w_i · s_i(t,q) / Σ_{i ∈ available(t)} w_i      over i ∈ {semantic, metadata, relationship}
```

- **Renormalize over available signals** (default) — the documented fallback for missing modalities. Optional `coverage_penalty` (default 0, configurable) multiplies by `(Σ_avail w_i / Σ w_i)^γ` to slightly prefer fully-evidenced tracks; if used, it is in the trace.
- Feedback signals: `negative_reference_penalty · max_sim(t, negative_refs)` and `negative_preference` term matches subtract; `excluded_track_ids` are removed before ranking.
- `relationship` weight is 0 until P04.T08 is implemented and tested.
- Weights live in `config/retrieval.yaml` (`weights_version`), never in code. Tuning uses only the dev split.
- Output `ScoreBreakdown(semantic, metadata, relationship, final, normalization, weights_version)` — `None` for missing signals, preserved to the API.

## 7. Diversity — MMR (`retrieval/diversity.py`)

```
select argmax_{t ∉ S}  λ·rel(t) − (1−λ)·max_{s ∈ S} sim(t, s)        λ = 1 − spec.diversity·config.diversity_scale
```

- `sim` = cosine of audio embeddings when both exist; else Jaccard over (artists ∪ release ∪ styles); `same_master`/`same_release` count as near-duplicates (sim = 1).
- First pick is always the top relevance item (MMR guarantees it with any λ>0 — test it).
- Deterministic tie-breaking by `track_id`.

## 8. RetrievalTrace

Every call returns a trace (mode, config versions, model_id, pool size, per-stage counts, per-candidate signals, constraint statuses, normalization fallbacks, timing). It feeds evidence building, evaluation CSVs, and debugging. It is not sent wholesale to the frontend.

## 9. Tests (unit, all with fakes)

- Merger: dedupe, provenance preserved, `not_available` vs `not_retrieved`.
- Missing modality: track A (semantic 0.9, metadata missing) vs track B (semantic missing, metadata 0.9) — both scored by renormalization; a track with evaluated-low semantic score is *not* treated like a track without audio.
- Constraints: VIOLATED excluded even with top score; UNKNOWN policy variants; empty ⇒ NO_CONFIDENT_MATCH; contradictory constraints raise upstream.
- Normalization: degenerate pool fallback; normalization ignores missing values.
- MMR: λ=1 equals relevance order; near-duplicate versions spread out; deterministic ties.
- Modes: `metadata_only` never touches the encoder (fake asserts not called).
