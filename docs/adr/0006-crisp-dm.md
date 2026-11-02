# ADR-0006: CRISP-DM as the project's development cycle

- **Status:** Accepted (owner, 2026-11-02)
- **Date:** 2026-11-02
- **Phase/Task:** P10.T08–T10

## Context

The executable plan (`skills/phases/`) runs P00 → P10 in a straight line. It already covers every
CRISP-DM stage, but it lacks three things CRISP-DM requires:

- **Measurable success criteria** stated up front (`base.md` §1 lists requirements, and §18
  milestones list deliverables, but neither says what result counts as good enough);
- **A data-understanding report**: catalog completeness and evaluation-data quality were never
  written down in one place;
- **The loop**: evaluation in P10 has no path back to data preparation or modeling when the
  results miss the targets. Dev runs `w0` → `p06-agents-dev` were real iterations, but nobody
  recorded why each change was made or what it was expected to do.

## Decision

Adopt CRISP-DM (Cross-Industry Standard Process for Data Mining) as the project's cycle,
layered over the existing phases rather than replacing them:

| CRISP-DM stage | Where it lives |
|---|---|
| 1. Business understanding | `base.md` §1; success targets in `docs/crisp-dm/business-understanding.md` (P10.T08) |
| 2. Data understanding | `scripts/data_understanding.py` → `docs/crisp-dm/data-understanding.md` (P10.T09); `docs/data-sources.md` |
| 3. Data preparation | P02 (ingestion, audio validation), P03 (embeddings), P07 (projection) |
| 4. Modeling | P03, P04 (hybrid ranking), P06 (agents), P07 (UMAP); choices in ADRs |
| 5. Evaluation | P05 harness, `docs/calibration.md`, P10; **the evaluation gate (P10.T10)** checks results against the targets |
| 6. Deployment | P08 (API), P09 (data layer), U01–U05 (interface), CI |

The loop: every change made because of an evaluation result is a **cycle** in
`docs/crisp-dm/iterations.md`, recording the hypothesis, the change, the dev result and the
decision. A missed target at the gate opens a cycle that goes back to stage 3 or 4.

Rules that keep the loop honest:
- **Targets are fixed before the test split is run** (P10.T01 freezes them with the inputs).
  Changing a target after seeing test results is not allowed; if one is wrong, the report says
  so.
- **Iterations tune on dev only.** The test split is run once per reported configuration. After
  an iteration, at most one more test run is allowed, and the report shows both runs.
- **Data fixes are cycles too.** Correcting a judgment changes the evaluation data, so it is
  logged like a model change and done before the freeze.

## Consequences

- The final report (P10.T05) states, for each target, whether it was met, with the evidence.
- Missed targets lead to new work (cycles) rather than being explained away in the report.
- Stage 6 (deployment monitoring, and feeding real sessions back into evaluation) is not covered
  yet; it is follow-up work once the interface ships.
- Small samples stay small: with 8 dev and 3 test queries, targets are checks on a smoke test,
  not significance claims (`retrieval-evaluation` §3).

## Reversible by

Dropping the gate task and the two documents; the phases and the evaluation code do not depend
on them.
