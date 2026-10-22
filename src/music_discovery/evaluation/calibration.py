"""Dev-split calibration of normalization and weights (P05.T06, base.md §7.5, §12.4).

Grid search over a small, documented space; the objective is the hybrid system's mean nDCG@5
over dev queries that have a relevant track. The test split is never touched, and calibration
refuses to run until every dev (query, track) pair is judged.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import product

from music_discovery.evaluation.datasets import EvalDataset
from music_discovery.evaluation.runners import Retriever, run_systems, score_runs
from music_discovery.retrieval.config import RetrievalConfig, SignalWeights, Strategy

SEMANTIC_WEIGHTS = (0.4, 0.5, 0.6, 0.7, 0.8)
SEMANTIC_NORMALIZATION: tuple[Strategy, ...] = ("minmax", "rank", "zscore_sigmoid")
COVERAGE_GAMMA = (0.0, 1.0)


class CalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class Trial:
    config: RetrievalConfig
    ndcg: float | None
    n: int

    @property
    def label(self) -> str:
        c = self.config
        return (
            f"semantic={c.weights.semantic:.1f} metadata={c.weights.metadata:.1f} "
            f"norm={c.normalization.semantic} gamma={c.coverage_penalty_gamma:g}"
        )


def grid(base: RetrievalConfig) -> list[RetrievalConfig]:
    """The base configuration first, then every grid point (so ties keep the base)."""
    configs = [base]
    for weight, strategy, gamma in product(
        SEMANTIC_WEIGHTS, SEMANTIC_NORMALIZATION, COVERAGE_GAMMA
    ):
        configs.append(
            base.model_copy(
                update={
                    "weights": SignalWeights(
                        semantic=weight,
                        metadata=round(1 - weight, 2),
                        relationship=base.weights.relationship,
                    ),
                    "normalization": base.normalization.model_copy(update={"semantic": strategy}),
                    "coverage_penalty_gamma": gamma,
                }
            )
        )
    return configs


def check_dev_judgments(dataset: EvalDataset) -> None:
    if dataset.split is None:
        raise CalibrationError("calibration needs the fixed split (split.json)")
    judged = {(j.query_id, j.fma_track_id) for j in dataset.judgments}
    missing = [
        (q, m.fma_track_id)
        for q in dataset.split.dev
        for m in dataset.manifest
        if (q, m.fma_track_id) not in judged
    ]
    if missing:
        total = len(dataset.split.dev) * len(dataset.manifest)
        raise CalibrationError(
            f"dev judgments incomplete: {total - len(missing)}/{total} pairs judged"
        )


def calibrate(
    dataset: EvalDataset,
    retriever_for: Callable[[RetrievalConfig], Retriever],
    base: RetrievalConfig,
    *,
    split: str = "dev",
    configs: Sequence[RetrievalConfig] | None = None,
) -> list[Trial]:
    """Score every configuration on the dev split; best first (stable for ties)."""
    if split != "dev":
        raise CalibrationError("calibration only ever uses the dev split")
    check_dev_judgments(dataset)
    trials = []
    for config in configs or grid(base):
        runs = run_systems(dataset, retriever_for(config), systems=("hybrid",), split="dev")
        _, summaries = score_runs(dataset, runs)
        trials.append(Trial(config=config, ndcg=summaries[0].ndcg.value, n=summaries[0].ndcg.n))
    order = sorted(range(len(trials)), key=lambda i: (-(trials[i].ndcg or -1.0), i))
    return [trials[i] for i in order]
