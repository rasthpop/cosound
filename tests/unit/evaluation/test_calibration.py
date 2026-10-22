from __future__ import annotations

import hashlib
import shutil
from collections.abc import Collection
from pathlib import Path

import pytest

from music_discovery.domain.enums import RetrievalSource, SearchOutcomeKind
from music_discovery.domain.schemas import (
    RankedCandidate,
    RetrievalTrace,
    ScoreBreakdown,
    SearchOutcome,
    SearchSpecification,
)
from music_discovery.evaluation.calibration import CalibrationError, calibrate, grid
from music_discovery.evaluation.datasets import JUDGMENT_COLUMNS, internal_track_id, load_dataset
from music_discovery.retrieval.config import RetrievalConfig
from music_discovery.retrieval.hybrid_retriever import HybridResult, Mode

REAL = Path(__file__).parents[3] / "data" / "evaluation"
BASE = RetrievalConfig(weights_version="w-base")


class ConfigSensitiveRetriever:
    """The higher the semantic weight, the closer the ranking is to the ideal one."""

    def __init__(self, config: RetrievalConfig, ideal: dict[str, list[str]]) -> None:
        self.config = config
        self.ideal = ideal

    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Collection[str] | None = None,
    ) -> HybridResult:
        assert corpus is not None
        ideal = self.ideal[spec.original_query]
        noise = sorted(corpus, key=lambda t: hashlib.sha256(t.encode()).hexdigest())
        keep = int(self.config.weights.semantic * 10) - 3  # 1 (w=0.4) .. 5 (w=0.8)
        order = list(dict.fromkeys([*ideal[:keep], *noise]))
        candidates = [
            RankedCandidate(
                track_id=t,
                rank=i,
                score=ScoreBreakdown(semantic=1 / i, final=1 / i),
                retrieval_sources=[RetrievalSource.SEMANTIC],
            )
            for i, t in enumerate(order[:limit], start=1)
        ]
        return HybridResult(
            outcome=SearchOutcome(kind=SearchOutcomeKind.OK, candidates=candidates),
            trace=RetrievalTrace(mode=mode),
        )


@pytest.fixture
def evaldir(tmp_path: Path) -> Path:
    for name in ("fma_20_manifest.csv", "queries.jsonl", "split.json", "specs_manual.jsonl"):
        shutil.copy(REAL / name, tmp_path / name)
    (tmp_path / "judgments.csv").write_text(",".join(JUDGMENT_COLUMNS) + "\n")
    return tmp_path


def judge_dev(directory: Path) -> dict[str, list[str]]:
    """Synthetic judgments for dev only: the first 5 manifest tracks are relevant (3..2)."""
    dataset = load_dataset(directory)
    assert dataset.split is not None
    lines = [",".join(JUDGMENT_COLUMNS)]
    ideal: dict[str, list[str]] = {}
    for qid in dataset.split.dev:
        ideal[dataset.specs[qid]["original_query"]] = [m.track_id for m in dataset.manifest[:5]]
        for i, m in enumerate(dataset.manifest):
            rel = 3 if i < 2 else 2 if i < 5 else 0
            lines.append(
                f"{qid},{m.fma_track_id},{rel},,,,synthetic,generated,2026-10-22T10:00:00Z"
            )
    (directory / "judgments.csv").write_text("\n".join(lines) + "\n")
    return ideal


def test_grid_starts_with_base_and_is_documented_size() -> None:
    configs = grid(BASE)
    assert configs[0] == BASE
    assert len(configs) == 31
    assert all(abs(c.weights.semantic + c.weights.metadata - 1.0) < 1e-9 for c in configs[1:])


def test_refuses_test_split_and_missing_judgments(evaldir: Path) -> None:
    dataset = load_dataset(evaldir)
    with pytest.raises(CalibrationError, match="only ever uses the dev split"):
        calibrate(dataset, lambda c: ConfigSensitiveRetriever(c, {}), BASE, split="test")
    with pytest.raises(CalibrationError, match="dev judgments incomplete: 0/200"):
        calibrate(dataset, lambda c: ConfigSensitiveRetriever(c, {}), BASE)


def test_picks_the_best_dev_configuration(evaldir: Path) -> None:
    ideal = judge_dev(evaldir)
    dataset = load_dataset(evaldir)
    trials = calibrate(dataset, lambda c: ConfigSensitiveRetriever(c, ideal), BASE)
    assert trials[0].config.weights.semantic == 0.8
    assert trials[0].ndcg == pytest.approx(1.0)
    assert trials[0].n == len(dataset.split.dev)  # type: ignore[union-attr]
    scores = [t.ndcg for t in trials]
    assert scores == sorted(scores, reverse=True)
    assert internal_track_id(dataset.manifest[0].fma_track_id) == ideal[next(iter(ideal))][0]
