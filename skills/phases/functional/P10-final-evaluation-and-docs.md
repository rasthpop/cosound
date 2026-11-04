# P10 — Final Evaluation, Hardening & Documentation

**Goal:** a frozen, reproducible evaluation of all systems and agents on the test split, an honest report with limitations, and documentation that lets a new developer reproduce everything (Milestone 7 + base §20 Definition of Done).
**base.md:** §12, §17, §18 M7, §19, §20.
**Depends on:** P05, P06, P07, P08, P09, P11

### P10.T01 — Freeze evaluation inputs
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T02, P06.T11, P10.T08, P10.T09, P10.T11, P11.T11
- **Files:** data/evaluation/CHECKSUMS.sha256, data/evaluation/README.md, docs/crisp-dm/business-understanding.md
- **Do:**
  - Test judgments follow the documented minimum (`judging_minimum.json`): q02 q04 q05 judged, the other 7 left out and named in the report.
  - CRISP-DM (ADR-0006): the owner confirms the success targets in `docs/crisp-dm/business-understanding.md` (status DRAFT → Confirmed), which are checksummed with the inputs; every judgment flagged in `docs/crisp-dm/data-understanding.md` is resolved and logged as cycle C6; the corpus is confirmed by listening (P02.T10) or the report states it is not.
  - Final review of manifest, queries, judgments, feedback cases, split; record checksums; any late change documented with reason (and never after seeing test results).
- **Done when:**
  - Every test query in the minimum has 20/20 judgments; checksums committed; `evaluate.py` verifies them before running and refuses on mismatch.
- **Status:** [ ]

### P10.T02 — Test-split baseline run
- **Skills:** retrieval-evaluation
- **Depends on:** P10.T01, P05.T06
- **Files:** artifacts/evaluation/{run_id}/* (+ latest copy in artifacts/evaluation/)
- **Do:**
  - Run metadata_only, semantic_only, hybrid (+ ablations: no-MMR, LLM Agent A with the ADR-0004 OpenRouter model if enabled; LLM responses taken from the cached run so the result is reproducible) once on test with the frozen dev-calibrated config; also report dev numbers for reference.
- **Done when:**
  - All files from base §12.8 exist; run is reproducible (second run identical metrics).
- **Status:** [ ]

### P10.T03 — Component evaluations
- **Skills:** retrieval-evaluation, agent-orchestration, umap-spatial-projection
- **Depends on:** P10.T02, P07.T04
- **Files:** artifacts/evaluation/{run_id}/{agent_a,agent_c,umap_quality}.*
- **Do:**
  - Agent A extraction/constraint metrics; Agent C feedback cases; UMAP quality (trustworthiness, overlap, manual table); per-query failure analysis.
- **Done when:**
  - Results included in `metrics.json` and referenced by the report.
- **Status:** [ ]

### P10.T04 — Description factuality audit
- **Skills:** grounded-explanations
- **Depends on:** P10.T02
- **Files:** artifacts/evaluation/{run_id}/descriptions_audit.csv
- **Do:**
  - Run claim validator on every generated description; manual check of each one (use the `evidence-auditor` agent as a second pass); record unsupported instrument/mood/genre claims and fixes.
- **Done when:**
  - Audit file complete; unsupported-claim count reported (target 0; if not, either fixed and re-run, or reported honestly).
- **Status:** [ ]

### P10.T05 — Evaluation report
- **Skills:** retrieval-evaluation
- **Depends on:** P10.T03, P10.T04, P10.T10
- **Files:** artifacts/evaluation/report.md, docs/evaluation.md
- **Do:**
  - Generate and edit `report.md` with all required sections; explicit statement that 20 tracks is a smoke test and results don't generalize; per-query failures with causes; data coverage numbers.
- **Done when:**
  - Every required section present (test); limitations reviewed by the user.
- **Status:** [ ]

### P10.T06 — Reproduction & developer documentation
- **Skills:** implementation-roadmap, music-discovery-architecture
- **Depends on:** P10.T05
- **Files:** README.md, docs/reproduce.md, docs/architecture.md, Makefile (reproduce target)
- **Do:**
  - Clean-machine walkthrough: env setup, FMA download (`fma_small`), FMA import, embeddings, index, map, API, frontend (mock + real), evaluation. `make reproduce` chains offline steps. Architecture doc explains how each component contributes to a result (base §18 M7).
- **Done when:**
  - Someone (or a fresh clone in a temp dir) follows `docs/reproduce.md` end-to-end and gets the same `metrics.json`.
- **Status:** [ ]

### P10.T07 — Definition-of-done & hygiene audit
- **Skills:** music-discovery-architecture, api-contracts, grounded-explanations
- **Depends on:** P10.T06
- **Files:** docs/definition-of-done.md
- **Do:**
  - Walk base §20 checklist item by item with evidence links (tests, artifacts); run secrets scan, `git ls-files` audit for audio/large files, boundary check, contract check, full test suite incl. `--run-slow`; review base §19 non-goals not violated.
- **Done when:**
  - Every DoD box ticked with evidence or explicitly documented as deferred with reason.
- **Status:** [ ]

## CRISP-DM cycle (appended 2026-11-02, ADR-0006)

The plan already covered every CRISP-DM stage; these tasks add what was missing: stated success
targets, a data-understanding report, and the loop from evaluation back to modeling.

### P10.T08 — Business understanding & success targets
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T06, P06.T11
- **Files:** docs/adr/0006-crisp-dm.md, docs/crisp-dm/business-understanding.md
- **Do:**
  - Adopt CRISP-DM over the existing phases (ADR-0006) and map each stage to its phases.
  - State the objective in the listener's terms and draft measurable targets (T1–T14) with must/should levels, each with its current dev evidence.
- **Done when:**
  - Every target has a metric, a threshold, a level and evidence or "not measured"; the owner's open decisions are listed. Confirmation happens in P10.T01, before the freeze.
- **Status:** [x]
- **Notes:** Drafted from runs `w0-initial-dev` → `p06-agents-dev`. On dev, T5 (hard-constraint violations ≤ 10 %; 27 % today) and T14 (evaluation data ready; corpus unconfirmed, 3 flagged judgments) are missed, and T8 and T12 are not measured yet.

### P10.T09 — Data-understanding report
- **Skills:** retrieval-evaluation, fma-audio-corpus
- **Depends on:** P02.T12, P05.T02
- **Files:** scripts/data_understanding.py, src/music_discovery/ingestion/catalog_report.py, src/music_discovery/evaluation/data_profile.py, tests/unit/ingestion/test_catalog_profile.py, tests/unit/evaluation/test_data_profile.py, docs/crisp-dm/data-understanding.md
- **Do:**
  - Profile the catalog (field completeness with missing values counted, genre balance, audio/embedding coverage, licenses) and the evaluation inputs (split, judgment coverage against the minimum, relevance distribution, constraint judgments, judgments contradicting their own listening notes).
  - Write `artifacts/data-understanding/{report.md,profile.json}` and commit a reviewed snapshot under `docs/crisp-dm/`.
- **Done when:**
  - Unit tests cover both profiles; the report runs on the real catalog read-only.
- **Status:** [x]
- **Notes:** First run (2026-11-02): 8,000 tracks, 7,993 with audio and embeddings; `year` present for 67 %, `styles` for 0 % (FMA has none); 8 genres × 1,000. Evaluation: 220/400 pairs judged (the documented minimum), the corpus is 0/20 confirmed, three q06 judgments contradict their notes, and the q16 duration constraint is judged "unknown" for every track although duration is in the catalog for all of them. The contradiction check is a heuristic for vocals constraints only; it flags rows, it never changes them.

### P10.T10 — Evaluation gate
- **Skills:** retrieval-evaluation
- **Depends on:** P10.T02, P10.T03, P10.T04, P10.T08
- **Files:** src/music_discovery/evaluation/report.py, artifacts/evaluation/{run_id}/gate.json, docs/crisp-dm/iterations.md
- **Do:**
  - Compare the test-run results with the confirmed targets: met / missed / not measured per target, with the evidence, in `gate.json` and a "Success targets" section of `report.md`.
  - A missed **must** target opens an iteration cycle in `iterations.md` that goes back to data preparation or modeling and tunes on dev only. After it, at most one more test run, and the report shows both.
  - A missed **should** target is reported with its cause.
- **Done when:**
  - Every target has a verdict backed by a metric or a test; the gate fails loudly (non-zero exit from `evaluate.py --gate`) when a must target is missed without an open cycle explaining it.
- **Status:** [ ]

### P10.T11 — Pre-freeze iteration cycles (C4, C5)
- **Skills:** hybrid-retrieval, retrieval-evaluation, agent-orchestration
- **Depends on:** P10.T08, P10.T09, P05.T06
- **Files:** src/music_discovery/retrieval/constraints.py, config/retrieval.yaml, docs/calibration.md, docs/crisp-dm/iterations.md
- **Do:**
  - C4 (hard constraints, target T5): check duration constraints from catalog facts so they read satisfied/violated instead of unknown, then sweep `unknown_demotion` and try a CLAP vocal probe as evidence. Dev only.
  - C5 (CLAP prompt expansions): calibrate the expansion count and weight on dev; check q01 and q16 per query.
  - Record each cycle's hypothesis, change, dev result and decision; adopt a change only if its target improves on dev without T1 regressing.
- **Done when:**
  - C4 and C5 are closed in `iterations.md` (adopted or rejected, with dev numbers) and any adopted configuration has a new `weights_version`.
- **Status:** [ ]

## Exit criteria (Milestone 7)
- [ ] A new developer can reproduce the small evaluation and understand each component's contribution.
- [ ] base §20 Definition of Done complete.
- [ ] CRISP-DM gate (P10.T10): every must target met, or missed with an open iteration cycle and an honest report (ADR-0006).
