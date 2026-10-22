# Retrieval calibration (P05.T06)

Weights and normalization in `config/retrieval.yaml` are tuned on the **dev split only**
(base.md §7.5, §12.4). The test split is evaluated once per reported configuration and never
used for tuning.

## Procedure

1. All dev (query, track) pairs are judged (`scripts/judge.py`); the tool refuses to run otherwise.
2. `uv run python scripts/calibrate.py` scores the hybrid system on the dev split for:
   - semantic weight 0.4, 0.5, 0.6, 0.7, 0.8 (metadata weight = 1 - semantic; relationship
     weight unchanged, 0 by default),
   - semantic normalization `minmax`, `rank`, `zscore_sigmoid` (metadata stays `max_scale`),
   - coverage penalty gamma 0 and 1,

   plus the current configuration: 31 configurations in total.
3. Objective: mean nDCG@5 over dev queries that have at least one relevant track. Ties keep the
   current configuration, then the earlier grid point.
4. The best configuration is written to `config/retrieval.calibrated.yaml` with a new
   `weights_version`. A person reviews it and copies it over `config/retrieval.yaml`.
5. The test split is then evaluated once: `scripts/evaluate.py --split test --allow-test`.

With 10 dev queries the differences between configurations are small and noisy; prefer simpler
configurations when scores are close, and do not read the ranking as a significance result.

## Results

Not run yet: judgments are pending (0/400 on 2026-10-22).
