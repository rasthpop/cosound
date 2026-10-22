"""The evaluation pipeline is reproducible and complete (base.md §17 evaluation tests).

Uses the committed inputs, synthetic judgments for every pair and a deterministic fake
retriever; the real run (CLAP, catalog) is `scripts/evaluate.py`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Collection
from datetime import UTC, datetime
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
from music_discovery.evaluation.datasets import JUDGMENT_COLUMNS, load_dataset
from music_discovery.evaluation.report import REPORT_SECTIONS, write_run
from music_discovery.evaluation.runners import run_systems, score_runs
from music_discovery.retrieval.hybrid_retriever import HybridResult, Mode

REAL = Path(__file__).parents[2] / "data" / "evaluation"


class FakeRetriever:
    """Ranks the corpus by a hash of (mode, query, track): deterministic and mode-dependent."""

    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Collection[str] | None = None,
    ) -> HybridResult:
        assert corpus is not None
        if spec.hard_constraints and mode == "metadata_only":
            return HybridResult(
                outcome=SearchOutcome(
                    kind=SearchOutcomeKind.NO_CONFIDENT_MATCH, reasons=["vocals: 0 satisfied"]
                ),
                trace=RetrievalTrace(mode=mode),
            )
        order = sorted(
            corpus,
            key=lambda t: hashlib.sha256(f"{mode}:{spec.original_query}:{t}".encode()).hexdigest(),
        )
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
    dataset = load_dataset(tmp_path)
    lines = [",".join(JUDGMENT_COLUMNS)]
    for q in dataset.queries:
        for m in dataset.manifest:
            rel = int(hashlib.sha256(f"{q.query_id}:{m.fma_track_id}".encode()).hexdigest(), 16) % 4
            if q.query_id == "q14":
                rel = min(rel, 1)  # a query with no relevant track in the corpus
            constraint = "yes" if rel >= 2 else "unknown"
            lines.append(
                f"{q.query_id},{m.fma_track_id},{rel},,,{constraint},synthetic,generated,2026-10-22T10:00:00Z"
            )
    (tmp_path / "judgments.csv").write_text("\n".join(lines) + "\n")
    specs = [
        line
        for line in (tmp_path / "specs_manual.jsonl").read_text().splitlines()
        if '"q20"' not in line
    ]
    (tmp_path / "specs_manual.jsonl").write_text("\n".join(specs) + "\n")  # q20 has no spec
    return tmp_path


def run_once(evaldir: Path, out: Path, split: str = "all") -> Path:
    dataset = load_dataset(evaldir)
    runs = run_systems(dataset, FakeRetriever(), split=split)  # type: ignore[arg-type]
    rows, summaries = score_runs(dataset, runs)
    snapshot = {
        "run_id": "test",
        "created_at": datetime.now(UTC).isoformat(),
        "weights_version": "w-test",
    }
    return write_run(
        out,
        dataset=dataset,
        dataset_dir=evaldir,
        runs=runs,
        rows=rows,
        summaries=summaries,
        split=split,
        snapshot=snapshot,
        coverage={"corpus_tracks": 20},
    )


def test_metrics_are_reproducible(evaldir: Path, tmp_path: Path) -> None:
    first = run_once(evaldir, tmp_path / "run1")
    second = run_once(evaldir, tmp_path / "run2")
    assert (first / "metrics.json").read_text() == (second / "metrics.json").read_text()
    assert (first / "per_query_results.csv").read_text() == (
        second / "per_query_results.csv"
    ).read_text()


def test_all_artifacts_and_report_sections(evaldir: Path, tmp_path: Path) -> None:
    run = run_once(evaldir, tmp_path / "run")
    for name in (
        "manifest.csv",
        "queries.jsonl",
        "judgments.csv",
        "per_query_results.csv",
        "metrics.json",
        "comparison.csv",
        "report.md",
        "config_snapshot.json",
    ):
        assert (run / name).is_file(), name
    report = (run / "report.md").read_text()
    for section in REPORT_SECTIONS:
        assert f"## {section}" in report, section
    limitations = report.split("## Known limitations", 1)[1].split("## Reproduction", 1)[0]
    assert "smoke-test corpus" in limitations
    assert "Judgments incomplete" not in report


def test_missing_data_is_reported_not_fatal(evaldir: Path, tmp_path: Path) -> None:
    metrics = json.loads((run_once(evaldir, tmp_path / "run") / "metrics.json").read_text())
    hybrid = metrics["systems"]["hybrid"]
    assert hybrid["skipped_queries"] == ["q20"]
    assert "q14" in hybrid["no_relevant_queries"], "no-relevant queries are reported separately"
    assert metrics["systems"]["metadata_only"]["no_confident_match"], "explicit outcome is recorded"
    assert metrics["judgments"] == {"complete": True, "judged": 400, "total": 400}
    for system in ("metadata_only", "semantic_only", "hybrid"):
        summary = metrics["systems"][system]
        assert summary["ndcg"]["n"] > 0
        assert 0.0 <= summary["ndcg"]["value"] <= 1.0
    per_query = {(r["query_id"], r["system"]): r for r in metrics["per_query"]}
    assert per_query[("q14", "hybrid")]["ndcg"] is None
    assert per_query[("q06", "hybrid")]["constraint_satisfied"] is not None


def test_dev_split_only_runs_dev_queries(evaldir: Path, tmp_path: Path) -> None:
    metrics = json.loads(
        (run_once(evaldir, tmp_path / "run", split="dev") / "metrics.json").read_text()
    )
    dataset = load_dataset(evaldir)
    assert dataset.split is not None
    assert {r["query_id"] for r in metrics["per_query"]} == set(dataset.split.dev)


def drop_judgments(evaldir: Path, keep: Callable[[str, str], bool]) -> None:
    path = evaldir / "judgments.csv"
    header, *rows = path.read_text().splitlines()
    kept = [r for r in rows if keep(*r.split(",", 2)[:2])]
    path.write_text("\n".join([header, *kept]) + "\n")


def test_report_names_unjudged_queries_left_out(evaldir: Path, tmp_path: Path) -> None:
    drop_judgments(evaldir, lambda q, _: q not in {"q09", "q13"})
    report = (run_once(evaldir, tmp_path / "run", split="test") / "report.md").read_text()
    assert "Judgments incomplete" not in report
    assert "8/10 queries of this split are judged" in report
    assert "left out of every mean: q09, q13" in report


def test_report_warns_on_partly_judged_query(evaldir: Path, tmp_path: Path) -> None:
    first = load_dataset(evaldir).manifest[0].fma_track_id
    drop_judgments(evaldir, lambda q, t: not (q == "q09" and t == str(first)))
    report = (run_once(evaldir, tmp_path / "run", split="test") / "report.md").read_text()
    assert "Judgments incomplete: 199/200 pairs judged in this split" in report
