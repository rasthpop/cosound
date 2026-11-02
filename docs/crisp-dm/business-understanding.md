# Business understanding (CRISP-DM step 1)

- **Status:** the CRISP-DM process was confirmed by the owner on 2026-11-02 (ADR-0006 accepted).
  The targets below are still DRAFT values, for the owner to confirm or change **before P10.T01
  freezes the evaluation inputs**. After the freeze they cannot change.
- **Drafted:** 2026-11-02, from the dev-split evidence of runs `w0-initial-dev` → `p06-agents-dev`
  and the UMAP quality artifact.

## Objective

A listener describes a sound in their own words ("something chill with a flute") and gets a short
list of real tracks that fit it. Each track comes with an honest explanation of why it matched and
a way to listen. The same catalog can be explored as a map. (`base.md` §1.)

What success means for the listener:

1. **Relevant first.** The top of the list fits the request better than keyword search alone or
   sound similarity alone would manage. This is the reason the hybrid system exists.
2. **Requirements are respected.** "Without vocals" means without vocals. When the system cannot
   check a requirement, it says so instead of guessing.
3. **Nothing is invented.** No made-up tracks, links, numbers or claims about the audio.
4. **Feedback works.** "More like this" or "less electronic" changes the results in the expected
   direction and never drops what the listener explicitly required.
5. **It keeps working.** Search still works when sound matching, the map or the language model is
   unavailable.

Out of scope for the MVP (ADR-0005): Discogs data, and any claim of quality beyond this
smoke-test corpus.

## Success targets (draft)

Retrieval targets are measured on the **test split** by the P10 evaluation (`retrieval-evaluation`
§3 has the definitions), with k = 5 and relevance ≥ 2. The test split has 3 judged queries
(`judging_minimum.json`), so every retrieval target is a smoke-test check, not a statistical
claim. Dev values are shown as evidence only.

**Must** targets gate the release: a miss opens an iteration cycle (`iterations.md`). **Should**
targets are reported honestly when missed.

| ID | Objective | Metric | Target | Dev evidence (latest) | Status on dev |
|---|---|---|---|---|---|
| T1 | 1 | Hybrid nDCG@5 vs the best baseline | hybrid ≥ max(metadata-only, semantic-only) — **must** | 0.741 vs 0.720 / 0.436 (`p06-agents-dev`) | met (margin 0.021) |
| T2 | 1 | Hybrid nDCG@5, absolute | ≥ 0.70 — should | 0.741 | met |
| T3 | 1 | Hybrid MRR | ≥ 0.90 — should | 0.938 | met |
| T4 | 1 | Hybrid Precision@5 | ≥ 0.50 — should | 0.550 | met |
| T5 | 2 | Top-5 slots judged as **violating** a hard constraint, over constraint queries | ≤ 10 % — **must**; the "unknown" share is reported next to it | 27 % (4 of 15 slots, q06 + q12; q16 all unknown) | **missed** |
| T6 | 2 | Agent A: micro-F1 on attributes, hard-constraint accuracy | F1 ≥ 0.90 and accuracy = 1.0 — should (the lexicon was written against these labels, so the test split is the real check) | 1.000 / 1.000 (dev, n = 10) | met |
| T7 | 4 | Agent C: constraint preservation · spec-delta accuracy · ranking direction | 1.0 (**must**) · ≥ 0.90 · ≥ 0.75 | 1.0 · 1.0 · 1.0 (8 cases) | met |
| T8 | 3 | Unsupported claims in generated descriptions (claim validator + manual audit, P10.T04) | 0 — **must** | not measured yet | open |
| T9 | 3 | No fabricated values: nulls stay null, links only when present | all contract and evidence tests pass — **must** | backend API tests and frontend view tests pass | met |
| T10 | 5 | Search with sound matching, the map or the LLM unavailable | degraded-mode API tests pass — **must** | `tests/api/test_degraded_modes.py` passes | met |
| T11 | — | Map faithfulness: UMAP trustworthiness@10 | ≥ 0.90 — should (kNN overlap@10 is reported, with no target: the caption already says nearness is suggestive) | 0.955 (overlap 0.267) | met |
| T12 | — | Warm search latency, 8k catalog, CLAP on CPU, dev machine | p95 ≤ 2 s — should | not measured; one cold request took ~5 s (2026-11-02 smoke test) | open |
| T13 | — | Catalog audio + embedding coverage | ≥ 99 % — should | 99.9 % (7,993 of 8,000) | met |
| T14 | — | Evaluation data ready for the freeze | the documented-minimum queries are fully judged, the 20-track corpus is confirmed by listening (P02.T10), and every judgment flagged in `data-understanding.md` is resolved — **must** | minimum judged; corpus 0 of 20 confirmed; 3 flagged judgments | **missed** |

## Decisions for the owner

1. **Confirm or change each threshold**, especially T5 (≤ 10 % violations) and T12 (2 s). The
   others follow from what the dev runs already show.
2. **T5 is missed on dev today.** Iteration cycle C4 (`iterations.md`) is proposed to address it
   before the freeze.
3. **T14 needs your listening time**: confirming the corpus (P02.T10) and deciding the three
   flagged q06 judgments. No code can do that.
4. **Should T1 require a minimum margin** over the best baseline (for example +0.02)? The dev
   margin is 0.021 over 8 queries, which is within noise. The draft asks only for "not worse".
