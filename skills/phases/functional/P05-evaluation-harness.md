# P05 — Evaluation Harness & Dev-Split Calibration

**Goal:** a reproducible evaluation pipeline (queries, human judgments, fixed split, metrics, runners, report) used to compare the three systems and to calibrate normalization/weights on the dev split only (Milestone 3, part 2). The final, frozen test run happens in P10.
**base.md:** §12, §6/§8 evaluation, §17 evaluation tests.
**Depends on:** P04.T07, P02.T10

### P05.T01 — Query set & fixed split
- **Skills:** retrieval-evaluation
- **Depends on:** P02.T10
- **Files:** data/evaluation/queries.jsonl, data/evaluation/split.json, data/evaluation/README.md
- **Owner:** human-in-the-loop (query authoring)
- **Do:**
  - 20 queries: the 10 from base §12.2 + 10 controlled variants (synonyms, negation, explicit hard constraint, vague, era). Each with `expected_attributes`, `expected_hard_constraints`, `intent_notes`. Written before looking at system output.
  - Fixed 10/10 dev/test split by query (seeded), stored with date.
- **Done when:**
  - Loader validation (P05.T03) passes; split file committed; README documents authoring rules.
- **Notes:** Drafted by Claude on 2026-10-22, **owner review requested**: q01-q10 are the base.md §12.2 queries (fixed by the spec; they had been run in the P04 smoke test), and q11-q20 are new variants written before running them (synonym swap, hard constraints, negation, vague, contradictory). Each query has a `family`; the split keeps families together (dev: q01 q03 q06 q07 q08 q10 q11 q12 q16 q18; test: q02 q04 q05 q09 q13 q14 q15 q17 q19 q20), so a rephrasing never sits on the other side of its original.
- **Status:** [x]

### P05.T02 — Judgment protocol & judging helper
- **Skills:** retrieval-evaluation, fma-audio-corpus
- **Depends on:** P05.T01
- **Files:** scripts/judge.py, data/evaluation/judgments.csv, data/evaluation/JUDGING.md
- **Owner:** human (listening)
- **Do:**
  - Guidelines for the 0–3 scale and the separate `instrument_present / mood_relevance / constraint_satisfied` fields; `basis` required.
  - CLI that iterates (query, track) pairs in randomized-but-seeded order, shows metadata and the audio file path (or plays it with a system player if available), and appends rows; resumable; never shows system scores (avoid bias).
  - Record `has_relevant_in_corpus` per query afterwards.
- **Done when:**
  - All 400 pairs judged (or the documented minimum), file validates, judge + date recorded.
- **Notes:** Tooling done: `scripts/judge.py` (resumable, seeded order, asks only the fields that apply, never shows system scores; the clip plays in the background so answers never wait for it, `--by-track` plays each clip once for all queries, `r`/`x` replay/stop, invalid answers are re-asked), `data/evaluation/JUDGING.md`, empty `judgments.csv`. **Blocked on the owner's listening pass** (0/400 judged), which should follow the manifest listening pass (P02.T10). Judgments use an `fma_track_id` column (not `track_id`) so rows match audio file names. **Documented minimum (owner, 2026-10-22):** dev q01 q03 q06 q10 q11 q12 q16 q18 fully judged before calibration, q07/q08 deferred (`data/evaluation/judging_minimum.json`, checked by `scripts/calibrate.py`); test q02 q04 q05 (q09 q13 q14 q15 q17 q19 q20 deferred). Done 2026-10-22: 220/400 judged by the owner (q01-q06, q10 q11 q12 q16 q18), dev minimum 160/160, file validates; `has_relevant_in_corpus` recorded in `queries.jsonl` for the 11 judged queries (all `true`), the 9 unjudged stay `null`. Not judged, by decision: dev q07 q08 and test q09 q13 q14 q15 q17 q19 q20; reports list them as left out.
- **Status:** [x]

### P05.T03 — Dataset loaders & validation
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T01
- **Files:** src/music_discovery/evaluation/datasets.py, tests/unit/evaluation/test_datasets.py
- **Do:**
  - Load/validate manifest, queries, judgments, split (ids exist, scales valid, every query in exactly one split, judgments of a query in one split).
- **Done when:**
  - Tests with tiny synthetic files, including each validation failure.
- **Status:** [x]

### P05.T04 — Metrics
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T03
- **Files:** src/music_discovery/evaluation/metrics.py, tests/unit/evaluation/test_metrics.py
- **Do:**
  - P@5, R@5, nDCG@5 (linear gains, IDCG over all judged), MRR (queries with ≥1 relevant), constraint satisfaction (+ unknown share); undefined handling for no-relevant queries.
- **Done when:**
  - Hand-computed examples in tests (incl. ties, fewer than 5 results, no relevant tracks).
- **Status:** [x]

### P05.T05 — Runners & evaluate CLI
- **Skills:** retrieval-evaluation, hybrid-retrieval
- **Depends on:** P05.T04, P04.T09
- **Files:** src/music_discovery/evaluation/runners.py, src/music_discovery/evaluation/report.py, scripts/evaluate.py, tests/evaluation/test_evaluate_reproducible.py
- **Do:**
  - Run systems over a split; write `per_query_results.csv`, `metrics.json`, `comparison.csv`, `config_snapshot.json`, copies of manifest/queries/judgments into `artifacts/evaluation/{run_id}/`; data-coverage counts; no-relevant queries reported separately.
  - Until Agent A exists, specs come from a temporary hand-written spec file for the queries (`data/evaluation/specs_manual.jsonl`); switch to the deterministic Agent A in P06.T11.
- **Done when:**
  - Two runs with the same config ⇒ identical `metrics.json` (excluding timestamps); missing data reported, not crashed; CI version runs on synthetic data with the fake encoder.
- **Notes:** Specs come from `specs_manual.jsonl` (20 hand-written) until P06.T11. The test split needs `--allow-test`. A real dev run works (30 query runs; metrics undefined with 0 judgments, and the report says so).
- **Status:** [x]

### P05.T06 — Dev-split calibration
- **Skills:** retrieval-evaluation, hybrid-retrieval
- **Depends on:** P05.T05, P05.T02
- **Files:** config/retrieval.yaml, docs/calibration.md
- **Do:**
  - On **dev only**: choose normalization strategy, weights (small grid), MMR λ scale, semantic strength threshold τ, relationship weight (0 unless it helps). Record grid, results, and chosen `weights_version`.
- **Done when:**
  - `docs/calibration.md` shows the dev-only procedure; test split untouched (assert in script that `--split test` is refused in calibration mode).
- **Notes:** Tool built and tested on synthetic judgments: grid of 31 configurations (semantic weight 0.4-0.8, semantic normalization, coverage gamma), hybrid nDCG@5 on dev, writes a proposal (`config/retrieval.calibrated.yaml`) and `docs/calibration.md`. MMR scale, the semantic strength threshold τ and the relationship weight are not in the grid (see the PR). Calibration checks the documented dev minimum, not all of dev. Run 2026-10-22 on 8 dev queries: the starting configuration scored best (hybrid nDCG@5 0.780, next 0.756), adopted unchanged as `weights_version: w1-dev-2026-10-22`; gamma has no effect on this corpus; MMR scale and relationship weight not tuned, and there is no τ in the code (reasons in `docs/calibration.md`).
- **Status:** [x]

### P05.T07 — Report generator skeleton
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T05
- **Files:** src/music_discovery/evaluation/report.py, templates/report.md.j2 (or inline)
- **Do:**
  - `report.md` with all required sections (dataset, versions, config, split, metric definitions, results, per-query failures, coverage, limitations, reproduction commands); limitations section seeded with the fixed smoke-test caveats.
- **Done when:**
  - Generated from a dev run; test asserts every required heading exists and Limitations is non-empty.
- **Notes:** Report includes every required section, states "judgments incomplete" instead of presenting undefined metrics, and lists no-relevant / no-confident-match / skipped queries.
- **Status:** [x]

## Exit criteria (Milestone 3, part 2)
- [x] `scripts/evaluate.py --systems metadata_only,semantic_only,hybrid --split dev` produces all artifacts reproducibly.
- [x] Calibration used dev split only and is documented.
- [x] Judgments are human, listening-based, with basis recorded. *(220/400 per the documented minimum.)*
