# P10 — Final Evaluation, Hardening & Documentation

**Goal:** a frozen, reproducible evaluation of all systems and agents on the test split, an honest report with limitations, and documentation that lets a new developer reproduce everything (Milestone 7 + base §20 Definition of Done).
**base.md:** §12, §17, §18 M7, §19, §20.
**Depends on:** P05, P06, P07, P08, P09

### P10.T01 — Freeze evaluation inputs
- **Skills:** retrieval-evaluation
- **Depends on:** P05.T02, P06.T11
- **Files:** data/evaluation/CHECKSUMS.sha256, data/evaluation/README.md
- **Do:**
  - Test judgments follow the documented minimum (`judging_minimum.json`): q02 q04 q05 judged, the other 7 left out and named in the report.
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
- **Depends on:** P10.T03, P10.T04
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

## Exit criteria (Milestone 7)
- [ ] A new developer can reproduce the small evaluation and understand each component's contribution.
- [ ] base §20 Definition of Done complete.
