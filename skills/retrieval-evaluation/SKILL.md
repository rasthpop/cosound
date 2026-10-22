---
name: retrieval-evaluation
description: The small reproducible evaluation — 20-track FMA corpus, 20-query set, ordinal relevance judgments with separate instrument/mood/constraint fields, fixed dev/test query split, metadata-only vs CLAP-only vs hybrid baselines, metric definitions (P@5, R@5, nDCG@5, MRR, constraint satisfaction), component evaluations for Agents A/C, UMAP and descriptions, and the artifacts/evaluation report. Load for scripts/evaluate.py, src/music_discovery/evaluation/, data/evaluation/, weight calibration, or any claim about system quality.
---

# Retrieval Evaluation

Spec: `base.md` §12 (all), §6/§8 evaluation subsections, §17 evaluation tests. **Twenty tracks is a smoke-test corpus.** The evaluation demonstrates the workflow and finds failures; it does not prove quality.

## 1. Inputs (committed under `data/evaluation/`)

| File | Content |
|---|---|
| `fma_20_manifest.csv` | fixed corpus (see `fma-audio-corpus`) |
| `queries.jsonl` | `{query_id, text, split, intent_notes, expected_attributes: {mood:[…], instrument:[…], …}, expected_hard_constraints:[…], has_relevant_in_corpus: bool|null}` |
| `judgments.csv` | `query_id, fma_track_id, overall_relevance(0–3), mood_relevance(0–3|), instrument_present(yes|no|uncertain|), constraint_satisfied(yes|no|unknown|), judge, basis, judged_at`. Keyed by FMA id so rows match audio files; optional fields only where the query asks for them |
| `feedback_cases.jsonl` | Agent C cases: initial query, feedback events, expected spec deltas, expected ranking direction |
| `split.json` | `{dev: [q…10], test: [q…10], seed, created_at}` |
| `README.md` | selection procedure, judging guidelines, limitations |

Rules:
- Queries: the 10 from base §12.2 + 10 more with controlled phrasing variants (synonym swap, negation, hard constraint, vague, contradictory-ish). Write them **before** looking at system output.
- Judgments: listen to the audio. `basis` records what was heard. Instrument presence never from CLAP output. Judge all 20×20 pairs (400) — manageable, and avoids pooling bias; at minimum all pairs any system ranks in its top-10.
- Split is by **query family** (a query and its rephrasings, `family` in `queries.jsonl`); all judgments of a query live in its split. Fixed once (`scripts/make_split.py`).
- Tuning (normalization strategy, weights, λ, τ) touches **dev only**; test is run once per reported configuration.

## 2. Code layout

```
src/music_discovery/evaluation/      # (add 'evaluation' to the boundary checker: may import domain, retrieval, agents, descriptions, spatial)
├── datasets.py      # load + validate manifest/queries/judgments/split
├── metrics.py       # pure functions, unit-tested against hand-computed examples
├── runners.py       # run a system (mode/config) over queries → ranked lists + traces
├── agent_eval.py    # Agent A attribute P/R/F1, constraint accuracy, validity; Agent C cases
├── report.py        # CSV/JSON/markdown writers
scripts/evaluate.py  # CLI: --systems metadata_only,semantic_only,hybrid --split dev|test|all --out artifacts/evaluation/{run_id}
```

## 3. Metric definitions (put these verbatim in the report)

Let `rel(q,t) ∈ {0,1,2,3}` = `overall_relevance`; a track is **relevant** iff `rel ≥ 2` (config `relevance_threshold`). Cutoff k = 5.

- **Precision@5** = |relevant ∩ top5| / 5 (denominator 5 even if fewer results are returned — report result counts too).
- **Recall@5** = |relevant ∩ top5| / |relevant(q)|; undefined if |relevant(q)| = 0.
- **nDCG@5** with linear gains: `DCG = Σ_{i=1..5} rel_i / log2(i+1)`; `IDCG` from the ideal ordering of *all* judged tracks for q; undefined if IDCG = 0.
- **MRR** over queries with ≥ 1 relevant track: `1 / rank of first relevant` (0 if none in the returned list).
- **Hard-constraint satisfaction rate** over queries with hard constraints: share of top-5 results with `constraint_satisfied = yes`; report `unknown` share separately.

Queries with no relevant tracks are **reported separately** (base §12.6) and excluded from R@5/nDCG/MRR means. Report means with n, plus per-query values; with n=10 per split, don't report significance claims.

## 4. Systems

Same catalog, same judgments, same code path (`HybridRetriever` modes):
- **A — metadata_only**, **B — semantic_only** (CLAP cosine), **Proposed — hybrid** (+ hard constraints + MMR). Optional ablations: hybrid without MMR, hybrid with deterministic vs LLM Agent A.
- Agents are evaluated separately; the retrieval comparison uses Agent A's deterministic spec for all systems so the comparison isolates retrieval.

## 5. Component evaluations

- **Agent A:** micro/macro P/R/F1 per attribute category vs `expected_attributes`; hard-constraint classification accuracy; structured-output validity rate (LLM path); disagreements listed.
- **Agent C:** per case — spec delta correctness, constraint preservation (must be 100 %), ranking direction (e.g., nDCG change on a case-specific relevance target), "what changed" text present.
- **UMAP:** trustworthiness@k, kNN overlap@k, manual neighbor table (from `quality.json`).
- **Descriptions:** run `claim_validator` on every generated description + manual check of every description in the run; record unsupported claims (target: 0).

## 6. Outputs (`artifacts/evaluation/{run_id}/`, latest copied/symlinked to `artifacts/evaluation/`)

`manifest.csv, queries.jsonl, judgments.csv, per_query_results.csv, metrics.json, comparison.csv, report.md` (+ `config_snapshot.json`, `agent_a.csv`, `agent_c.csv`, `descriptions_audit.csv`).

`report.md` sections (all required): dataset composition · model & checkpoint versions (CLAP checkpoint, plus the exact OpenRouter model IDs, prompt versions and run date for any LLM path) · retrieval configuration (weights_version, normalization, λ) · evaluation split · metric definitions · results for all systems · per-query failures (with why) · component evaluations · data coverage (tracks with valid audio / embeddings, queries with ≥1 relevant, failed/skipped queries) · known limitations · reproduction commands.

## 7. Reproducibility tests (`tests/evaluation/`)

All configured systems run; missing data reported not crashed; two runs with the same config produce identical `metrics.json` (excluding timestamps); all artifacts written; report contains a non-empty Limitations section. Use the fake encoder + a tiny synthetic judgment set for the CI version; the real run is `slow`.
