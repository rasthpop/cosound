# Retrieval calibration (P05.T06)

Weights and normalization in `config/retrieval.yaml` are tuned on the **dev split only**
(base.md §7.5, §12.4). The test split is evaluated once per reported configuration and never
used for tuning.

## Procedure

1. The required dev queries are fully judged (`scripts/judge.py`); the tool refuses to run
   otherwise. On 2026-10-22 the owner set the minimum to 8 of the 10 dev queries
   (`data/evaluation/judging_minimum.json`: q01 q03 q06 q10 q11 q12 q16 q18); q07 and q08 are
   deferred and left out unless fully judged. A partly judged dev query is refused.
2. `uv run python scripts/calibrate.py` scores the hybrid system on the dev split for:
   - semantic weight 0.4, 0.5, 0.6, 0.7, 0.8 (metadata weight = 1 - semantic; relationship
     weight unchanged, 0 by default),
   - semantic normalization `minmax`, `rank`, `zscore_sigmoid` (metadata stays `max_scale`),
   - coverage penalty gamma 0 and 1,

   plus the current configuration: 31 configurations in total.
3. Objective: mean nDCG@5 over dev queries that have at least one relevant track. Ties keep the
   current configuration, then the earlier grid point.
4. The best configuration is written to `config/retrieval.calibrated.yaml` with a new
   `weights_version`. A person reviews it and copies it over `config/retrieval.yaml`; the
   proposal file is then deleted (it is regenerated on every run).
5. The test split is then evaluated once: `scripts/evaluate.py --split test --allow-test`.

With 8 (at most 10) dev queries the differences between configurations are small and noisy;
prefer simpler configurations when scores are close, and do not read the ranking as a
significance result.

## Decision (2026-10-22)

Run on 8 dev queries (q01 q03 q06 q10 q11 q12 q16 q18; q07 q08 unjudged and left out), all with
at least one relevant track. Adopted as `weights_version: w1-dev-2026-10-22`, with the **same
values as `w0-initial`**: semantic 0.6 / metadata 0.4, semantic normalization `minmax`, gamma 0.

- The starting configuration ranked first (hybrid nDCG@5 0.780). The next best (semantic 0.7,
  `zscore_sigmoid`) scored 0.756; a gap of 0.024 over 8 queries is noise, so the simpler,
  unchanged configuration is kept.
- `minmax` was the best semantic normalization at 0.6 and 0.8 weight. Weights of 0.4-0.5
  were worst under every normalization, consistent with metadata-only being the weakest system
  (nDCG@5 0.412 vs 0.757 semantic-only, run `w0-initial-dev`).
- Coverage gamma had no effect: every corpus track has both an embedding and metadata, so no
  candidate is missing a modality. It stays 0 and is untested on this corpus.
- Not tuned, deliberately: the MMR scale (0.6), because diversity only acts on specs that ask
  for it and nDCG@5 does not reward it, and the relationship weight (0), because the relationship
  signal only runs for specs with reference tracks and no evaluation query has one. The semantic strength
  threshold τ is not a retrieval parameter: it sets the strength bands of track descriptions
  (grounded-explanations) and does not exist until P06.T05, which sets it on dev only.
- Dev-only: `calibrate()` refuses any split but dev, and the test split was not run.

## Results

Run 2026-10-22, 31 configurations. Unjudged dev queries left out: q07, q08.

| Rank | Configuration | nDCG@5 (dev) | n |
|---|---|---|---|
| 1 | semantic=0.6 metadata=0.4 norm=minmax gamma=0 | 0.780 | 8 |
| 2 | semantic=0.6 metadata=0.4 norm=minmax gamma=0 | 0.780 | 8 |
| 3 | semantic=0.6 metadata=0.4 norm=minmax gamma=1 | 0.780 | 8 |
| 4 | semantic=0.7 metadata=0.3 norm=zscore_sigmoid gamma=0 | 0.756 | 8 |
| 5 | semantic=0.7 metadata=0.3 norm=zscore_sigmoid gamma=1 | 0.756 | 8 |
| 6 | semantic=0.8 metadata=0.2 norm=minmax gamma=0 | 0.749 | 8 |
| 7 | semantic=0.8 metadata=0.2 norm=minmax gamma=1 | 0.749 | 8 |
| 8 | semantic=0.7 metadata=0.3 norm=minmax gamma=0 | 0.749 | 8 |
| 9 | semantic=0.7 metadata=0.3 norm=minmax gamma=1 | 0.749 | 8 |
| 10 | semantic=0.8 metadata=0.2 norm=rank gamma=0 | 0.748 | 8 |
| 11 | semantic=0.8 metadata=0.2 norm=rank gamma=1 | 0.748 | 8 |
| 12 | semantic=0.8 metadata=0.2 norm=zscore_sigmoid gamma=0 | 0.737 | 8 |
| 13 | semantic=0.8 metadata=0.2 norm=zscore_sigmoid gamma=1 | 0.737 | 8 |
| 14 | semantic=0.7 metadata=0.3 norm=rank gamma=0 | 0.737 | 8 |
| 15 | semantic=0.7 metadata=0.3 norm=rank gamma=1 | 0.737 | 8 |
| 16 | semantic=0.5 metadata=0.5 norm=minmax gamma=0 | 0.722 | 8 |
| 17 | semantic=0.5 metadata=0.5 norm=minmax gamma=1 | 0.722 | 8 |
| 18 | semantic=0.6 metadata=0.4 norm=rank gamma=0 | 0.719 | 8 |
| 19 | semantic=0.6 metadata=0.4 norm=rank gamma=1 | 0.719 | 8 |
| 20 | semantic=0.6 metadata=0.4 norm=zscore_sigmoid gamma=0 | 0.710 | 8 |
| 21 | semantic=0.6 metadata=0.4 norm=zscore_sigmoid gamma=1 | 0.710 | 8 |
| 22 | semantic=0.4 metadata=0.6 norm=rank gamma=0 | 0.707 | 8 |
| 23 | semantic=0.4 metadata=0.6 norm=rank gamma=1 | 0.707 | 8 |
| 24 | semantic=0.5 metadata=0.5 norm=rank gamma=0 | 0.707 | 8 |
| 25 | semantic=0.5 metadata=0.5 norm=rank gamma=1 | 0.707 | 8 |
| 26 | semantic=0.4 metadata=0.6 norm=zscore_sigmoid gamma=0 | 0.706 | 8 |
| 27 | semantic=0.4 metadata=0.6 norm=zscore_sigmoid gamma=1 | 0.706 | 8 |
| 28 | semantic=0.5 metadata=0.5 norm=zscore_sigmoid gamma=0 | 0.700 | 8 |
| 29 | semantic=0.5 metadata=0.5 norm=zscore_sigmoid gamma=1 | 0.700 | 8 |
| 30 | semantic=0.4 metadata=0.6 norm=minmax gamma=0 | 0.699 | 8 |
| 31 | semantic=0.4 metadata=0.6 norm=minmax gamma=1 | 0.699 | 8 |

## Description strength threshold τ (P06.T05)

`config/descriptions.yaml` (`semantic_bands`) sets the strength band a track's CLAP match is
described with: **strong** = semantic rank ≤ 3 and normalized semantic score ≥ `tau_strong`;
**partial** = normalized ≥ `tau_partial`; otherwise **weak**. Bands only change the wording of
descriptions ("strong match for …" / "partial match" / "only a loose match"); they never change
ranking.

Procedure (2026-10-23, dev split only, the 8 judged dev queries of `judging_minimum.json`):
Agent A deterministic specs, hybrid mode with `w1-dev-2026-10-22`, whole 20-track corpus per
query; every returned track's semantic rank and minmax-normalized semantic score was paired with
the owner's `overall_relevance` (relevant = ≥ 2). 147 judged pairs, base rate 0.26 relevant.
The test split was not used.

| Band rule | Precision (relevant) | n |
|---|---|---|
| top-3, any score | 0.67 | 21 |
| top-3, normalized ≥ 0.80 | 0.71 | 17 |
| top-3, normalized ≥ 0.85 | 0.71 | 14 |
| top-3, normalized ≥ 0.95 | 0.78 | 9 |
| rank > 3, normalized ≥ 0.6 | 0.44 | 25 |
| rank > 3, normalized ≥ 0.5 | 0.34 | 41 |
| normalized < 0.6 | 0.13 | 101 |

Decision: `tau_strong: 0.8` (same precision as 0.85 with more coverage; higher thresholds
differ by one or two tracks, which is noise at this size) and `tau_partial: 0.6` (the clearest
split: 0.44 above vs 0.13 below, against a 0.26 base rate). Version `d1-dev-2026-10-23`. With
eight queries these are coarse settings; re-check them when more dev queries are judged.
