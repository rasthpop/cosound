# Iteration log (CRISP-DM loop)

Every change made because of an evaluation result is a cycle (ADR-0006). Each cycle records the
hypothesis, the change, the **dev** result and the decision. The test split is never used to
choose a change. Metrics are means over the 8 judged dev queries (k = 5, relevance ≥ 2); with
n = 8, differences of a few hundredths are noise.

Cycles C0–C3 are backfilled from the run artifacts in `artifacts/evaluation/` and the task
notes. C4 onward are open.

## Summary

| Cycle | Run | Change | Hybrid nDCG@5 | Semantic-only | Metadata-only | Decision |
|---|---|---|---|---|---|---|
| C0 | `w0-initial-dev` | starting weights | 0.780 | 0.757 | 0.412 | baseline |
| C1 | `w1-dev-2026-10-22-dev` | 31-configuration calibration grid | 0.780 | 0.757 | 0.412 | kept C0 values |
| C2 | `p06t01-expansion-dev` | lexicon synonym expansion for metadata search | 0.787 | 0.757 | 0.436 | adopted |
| C3 | `p06-agents-dev` | Agent A specs instead of hand-written ones | 0.741 | 0.720 | 0.436 | adopted for honesty; gap → C5 |
| C4 | — | hard-constraint violations | — | — | — | **open** |
| C5 | — | CLAP prompt expansions from Agent A | — | — | — | **open** |
| C6 | — | evaluation-data fixes before the freeze | — | — | — | **open** (owner) |

## C0 — Starting weights (2026-10-22)

- **Stage:** Modeling → Evaluation.
- **Configuration:** semantic 0.6 / metadata 0.4, semantic normalization `minmax`, MMR scale 0.6,
  unknown constraints kept but demoted ×0.5 (`keep_flagged`).
- **Result:** hybrid nDCG@5 0.780, P@5 0.525, MRR 1.000; semantic-only 0.757; metadata-only 0.412.
  Hard-constraint top-5: 40 % satisfied, 33 % unknown.
- **Decision:** baseline for every later cycle.

## C1 — Dev calibration (2026-10-22, P05.T06)

- **Hypothesis:** a different weight or normalization lifts hybrid nDCG@5.
- **Change:** grid of 31 configurations (semantic weight 0.4–0.8, three normalizations, coverage
  penalty γ 0/1), with dev-split nDCG@5 as the objective (`docs/calibration.md`).
- **Result:** the starting configuration ranked first (0.780). The next best was 0.756.
  Metadata-heavy weights (0.4–0.5 semantic) were worst under every normalization.
- **Decision:** keep the C0 values as `weights_version: w1-dev-2026-10-22`. The MMR scale and the
  relationship weight were deliberately not tuned (no evaluation query exercises them).

## C2 — Lexicon expansion for metadata search (2026-10-22, P06.T01)

- **Hypothesis:** synonyms ("laid-back" for "relaxed") let metadata search find tagged tracks the
  literal words miss.
- **Change:** the lexicon is wired into `MetadataRetriever` synonym expansion. Synonyms that
  contain a shorter expansion are dropped ("chill out" next to "chill"), because FMA's "Chill-out"
  genre was otherwise double-counted and lowered q01.
- **Result:** metadata-only 0.412 → 0.436; hybrid 0.780 → 0.787, P@5 0.525 → 0.550.
- **Decision:** adopted.

## C3 — Agent A instead of hand-written specs (2026-10-23, P06.T11)

- **Hypothesis:** none. This removes a crutch: until P06 the evaluation used hand-written search
  specs, so it measured retrieval with a perfect query reader.
- **Change:** `evaluate.py` uses Agent A's deterministic specs by default (`--specs manual` keeps
  the old ones).
- **Result:** hybrid 0.787 → 0.741, semantic-only 0.757 → 0.720. The only difference is the CLAP
  prompt expansions Agent A adds; q01 and q16 lose the most. Agent A attribute F1 1.000, and Agent
  C 8 of 8 cases.
- **Decision:** adopted, because it is what users get. The gap becomes C5.

## C4 — Hard-constraint violations (open)

- **Evidence (dev, `p06-agents-dev`):** over the three constraint queries, the hybrid top-5 has
  6 slots judged satisfied, 4 violated and 5 unknown. q06 "calm acoustic music without vocals" has
  1 violation, q12 "instrumental electronic, no vocals" has 3, and q16 "under three minutes" is
  unknown in all 5 slots. Target T5 (≤ 10 % violated) is missed at 27 %.
- **Hypotheses:**
  1. Vocal presence is never verified (no vocal detector), so "no vocals" stays `unknown` and
     only demotes a track ×0.5 (`constraints.unknown_demotion`). A stronger demotion, or a CLAP
     probe ("music with singing") used as evidence rather than as a filter, could push vocal
     tracks out of the top 5.
  2. q16 is a measurement gap, not a ranking one: duration is in the catalog for 100 % of tracks
     (`data-understanding.md`), so "under three minutes" can be checked from catalog data. The
     constraint should then read `satisfied`/`violated`, not `unknown`, and the judgments can be
     filled from the same fact.
- **Plan:** dev only. Try hypothesis 2 first (a factual fix), then sweep `unknown_demotion` and
  test the CLAP vocal probe. Accept a change only if T5 improves on dev without T1 regressing.
- **Status:** open, to run before the P10.T01 freeze.

## C5 — CLAP prompt expansions (open)

- **Evidence:** C3. Agent A's deterministic prompt expansions cost about 0.046 hybrid nDCG@5 on dev
  against hand-written specs, mostly on q01 and q16. The 2026-11-02 smoke test on the full catalog
  showed the same pattern: for "something chill with a flute", the top 5 came from "Chill-out"
  tags, and no flute track appeared before rank 6.
- **Hypothesis:** the expansions dilute the instrument term, and tag matches outweigh the audio
  score.
- **Plan:** dev-only calibration of the expansion count and weight (left open by P06.T11), and a
  check of the per-query effect on q01 and q16.
- **Status:** open.

## C6 — Evaluation-data fixes (open, owner)

- **Evidence:** `data-understanding.md`. Three q06 judgments contradict their own listening notes
  (35184 and 45152 are marked as satisfying "no vocals" with the note "vocals present"; 107476 is
  marked as violating it with the note "vocals are not present"). The 20-track corpus is still
  "pending" listening (P02.T10).
- **Change:** the owner re-listens and corrects or confirms each row, then confirms the corpus.
  This is a data change, so it is logged here and done before the freeze (T14).
- **Status:** open; needs the owner.
