"""Dev-split calibration of normalization and weights (P05.T06, base.md §7.5, §12.4).

Grid search over a small, documented space; the objective is the hybrid system's mean nDCG@5
over dev queries that have a relevant track. The test split is never touched. Calibration
refuses to run until every pair of the required dev queries is judged (all of dev by default,
or the documented minimum in data/evaluation/judging_minimum.json). Other dev queries count
only when fully judged; a partly judged one is refused, unjudged ones are left out.
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


def check_dev_judgments(dataset: EvalDataset, required: Sequence[str] | None = None) -> list[str]:
    """Raise unless the required dev queries are fully judged; return the dev queries left out."""
    if dataset.split is None:
        raise CalibrationError("calibration needs the fixed split (split.json)")
    dev = dataset.split.dev
    required = list(dev) if required is None else list(required)
    if outside := sorted(set(required) - set(dev)):
        raise CalibrationError(f"required queries not in the dev split: {', '.join(outside)}")
    judged = {(j.query_id, j.fma_track_id) for j in dataset.judgments}
    counts = {q: sum((q, m.fma_track_id) in judged for m in dataset.manifest) for q in dev}
    full = len(dataset.manifest)
    missing = sum(full - counts[q] for q in required)
    if missing:
        total = len(required) * full
        raise CalibrationError(f"dev judgments incomplete: {total - missing}/{total} pairs judged")
    if partial := sorted(q for q in dev if 0 < counts[q] < full):
        raise CalibrationError(f"dev queries partly judged: {', '.join(partial)}")
    return [q for q in dev if counts[q] == 0]


def calibrate(
    dataset: EvalDataset,
    retriever_for: Callable[[RetrievalConfig], Retriever],
    base: RetrievalConfig,
    *,
    split: str = "dev",
    configs: Sequence[RetrievalConfig] | None = None,
    required: Sequence[str] | None = None,
) -> list[Trial]:
    """Score every configuration on the dev split; best first (stable for ties)."""
    if split != "dev":
        raise CalibrationError("calibration only ever uses the dev split")
    check_dev_judgments(dataset, required)
    trials = []
    for config in configs or grid(base):
        runs = run_systems(dataset, retriever_for(config), systems=("hybrid",), split="dev")
        _, summaries = score_runs(dataset, runs)
        trials.append(Trial(config=config, ndcg=summaries[0].ndcg.value, n=summaries[0].ndcg.n))
    order = sorted(range(len(trials)), key=lambda i: (-(trials[i].ndcg or -1.0), i))
    return [trials[i] for i in order]
