"""Evaluation artifacts and the markdown report (base.md §12.8).

`metrics.json` contains no timestamps, so two runs with the same inputs and configuration
produce identical files. Run metadata (time, commit) goes to `config_snapshot.json`.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from music_discovery.evaluation.datasets import (
    JUDGMENTS_FILE,
    MANIFEST_FILE,
    QUERIES_FILE,
    SPLIT_FILE,
    EvalDataset,
)
from music_discovery.evaluation.metrics import DEFAULT_K, DEFAULT_THRESHOLD, Mean
from music_discovery.evaluation.runners import QueryMetrics, QueryRun, SystemSummary

REPORT_SECTIONS = (
    "Dataset composition",
    "Model and checkpoint versions",
    "Retrieval configuration",
    "Evaluation split",
    "Metric definitions",
    "Results",
    "Per-query results and failures",
    "Component evaluations",
    "Data coverage",
    "Known limitations",
    "Reproduction",
)

K, T = DEFAULT_K, DEFAULT_THRESHOLD
METRIC_DEFINITIONS = f"""\
Let `rel(q, t)` in {{0, 1, 2, 3}} be the judged overall relevance; a track is **relevant** iff
`rel >= {T}`. Cutoff k = {K}.

- **Precision@{K}** = |relevant in top {K}| / {K} (the denominator stays {K} even if fewer
  results were returned).
- **Recall@{K}** = |relevant in top {K}| / |relevant(q)|; undefined if q has no relevant track.
- **nDCG@{K}** with linear gains: DCG = sum over i of rel_i / log2(i + 1); IDCG from the ideal
  ordering of all judged tracks for q; undefined if IDCG = 0.
- **MRR**: 1 / rank of the first relevant result (0 if none returned), over queries with at
  least one relevant track.
- **Hard-constraint satisfaction**: over queries with hard constraints, the share of the top
  {K} judged `constraint_satisfied = yes`; the `unknown` share is reported separately.

Queries with no relevant track in the corpus are reported separately and excluded from the
R@{K}, nDCG@{K} and MRR means. Means are reported with the number of queries (n).
"""

LIMITATIONS = """\
- **Twenty tracks is a smoke-test corpus.** These numbers show the workflow and expose failure
  cases; they do not measure general retrieval quality, and with 10 queries per split no
  significance claims are made.
- Relevance judgments come from listening by a small number of judges (see the judge column);
  they are subjective, especially for mood.
- The 20 tracks were first drafted from metadata (genre, title, tags, echonest estimates) and
  then checked by ear; corpus composition still shapes which queries have relevant tracks.
- Search specifications are hand-written (`specs_manual.jsonl`) until Agent A exists (P06),
  so these results isolate retrieval from query understanding.
- Retrieval runs over the 20-track corpus only; min-max normalization over so few candidates
  exaggerates differences between close scores.
- FMA genres and tags are sparse (few mood tags), which limits metadata-only retrieval.
"""


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _mean(m: Mean) -> str:
    return f"{_fmt(m.value)} (n={m.n})"


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: "" if row.get(c) is None else row[c] for c in columns})


def metrics_payload(
    summaries: Sequence[SystemSummary],
    rows: Sequence[QueryMetrics],
    *,
    split: str,
    judged: int,
    total: int,
) -> dict[str, Any]:
    return {
        "split": split,
        "k": DEFAULT_K,
        "relevance_threshold": DEFAULT_THRESHOLD,
        "judgments": {"judged": judged, "total": total, "complete": judged == total},
        "systems": {s.system: asdict(s) for s in summaries},
        "per_query": [asdict(r) for r in rows],
    }


def write_run(
    out_dir: Path,
    *,
    dataset: EvalDataset,
    dataset_dir: Path,
    runs: Sequence[QueryRun],
    rows: Sequence[QueryMetrics],
    summaries: Sequence[SystemSummary],
    split: str,
    snapshot: Mapping[str, Any],
    coverage: Mapping[str, int],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(dataset_dir / MANIFEST_FILE, out_dir / "manifest.csv")
    shutil.copy(dataset_dir / QUERIES_FILE, out_dir / "queries.jsonl")
    if (dataset_dir / JUDGMENTS_FILE).is_file():
        shutil.copy(dataset_dir / JUDGMENTS_FILE, out_dir / "judgments.csv")
    if (dataset_dir / SPLIT_FILE).is_file():
        shutil.copy(dataset_dir / SPLIT_FILE, out_dir / "split.json")

    total = len(dataset.queries) * len(dataset.manifest)
    payload = metrics_payload(
        summaries, rows, split=split, judged=len(dataset.judgments), total=total
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "config_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    by_run = {(r.query_id, r.system): r for r in runs}
    per_query = []
    for row in rows:
        run = by_run[(row.query_id, row.system)]
        per_query.append(
            {
                **asdict(row),
                "ranked_fma_track_ids": " ".join(map(str, run.ranked)),
                "degraded": ";".join(run.degraded),
            }
        )
    _write_csv(
        out_dir / "per_query_results.csv",
        per_query,
        [*asdict(rows[0]).keys(), "ranked_fma_track_ids", "degraded"] if rows else ["query_id"],
    )
    comparison = [
        {
            "system": s.system,
            f"precision@{DEFAULT_K}": _fmt(s.precision.value),
            f"recall@{DEFAULT_K}": _fmt(s.recall.value),
            f"ndcg@{DEFAULT_K}": _fmt(s.ndcg.value),
            "mrr": _fmt(s.mrr.value),
            "constraint_satisfied": _fmt(s.constraint_satisfied.value),
            "constraint_unknown": _fmt(s.constraint_unknown.value),
            "n_scored": s.ndcg.n,
            "no_relevant_queries": " ".join(s.no_relevant_queries),
        }
        for s in summaries
    ]
    _write_csv(
        out_dir / "comparison.csv", comparison, list(comparison[0]) if comparison else ["system"]
    )
    (out_dir / "report.md").write_text(
        render_report(
            dataset, rows, summaries, split=split, snapshot=snapshot, coverage=coverage, runs=runs
        ),
        encoding="utf-8",
    )
    return out_dir


def render_report(
    dataset: EvalDataset,
    rows: Sequence[QueryMetrics],
    summaries: Sequence[SystemSummary],
    *,
    split: str,
    snapshot: Mapping[str, Any],
    coverage: Mapping[str, int],
    runs: Sequence[QueryRun],
) -> str:
    total = len(dataset.queries) * len(dataset.manifest)
    judged = len(dataset.judgments)
    lines = [f"# Evaluation report: {snapshot.get('run_id', '')}", ""]
    if judged < total:
        lines += [
            f"> **Judgments incomplete: {judged}/{total} pairs judged.** Metrics below are",
            "> undefined (—) or computed on partial judgments and must not be read as results.",
            "",
        ]
    genres: dict[str, int] = {}
    for m in dataset.manifest:
        genres[m.genre] = genres.get(m.genre, 0) + 1
    confirmed = sum(m.listening_status == "confirmed" for m in dataset.manifest)
    lines += [
        "## Dataset composition",
        "",
        f"- Corpus: {len(dataset.manifest)} FMA tracks (`fma_small`), "
        f"{confirmed} confirmed by listening.",
        f"- Top genres: {', '.join(f'{g} {n}' for g, n in sorted(genres.items()))}.",
        f"- Queries: {len(dataset.queries)} ({len({q.family for q in dataset.queries})} families).",
        f"- Judgments: {judged}/{total} (query, track) pairs.",
        "",
        "## Model and checkpoint versions",
        "",
        f"- CLAP model: `{snapshot.get('model_id')}`",
        f"- Embedding version: `{snapshot.get('embedding_version')}`",
        f"- Code commit: `{snapshot.get('git_commit')}`",
        "",
        "## Retrieval configuration",
        "",
        f"- Weights version: `{snapshot.get('weights_version')}`",
        "```json",
        json.dumps(snapshot.get("retrieval_config", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Evaluation split",
        "",
        f"- Evaluated split: **{split}**",
    ]
    if dataset.split is not None:
        lines += [
            f"- dev: {', '.join(dataset.split.dev)}",
            f"- test: {', '.join(dataset.split.test)}",
            f"- Method: {dataset.split.method}, seed {dataset.split.seed}.",
        ]
    lines += ["", "## Metric definitions", "", METRIC_DEFINITIONS, "## Results", ""]
    lines += [
        f"| System | P@{K} | R@{K} | nDCG@{K} | MRR | Constraints met | Constraints unknown |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.system} | {_mean(s.precision)} | {_mean(s.recall)} | {_mean(s.ndcg)} | "
            f"{_mean(s.mrr)} | "
            f"{_mean(s.constraint_satisfied)} | {_mean(s.constraint_unknown)} |"
        )
    lines += ["", "## Per-query results and failures", ""]
    for s in summaries:
        notes = []
        if s.no_relevant_queries:
            notes.append(f"no relevant track in corpus: {', '.join(s.no_relevant_queries)}")
        if s.no_confident_match:
            notes.append(f"no confident match: {', '.join(s.no_confident_match)}")
        if s.skipped_queries:
            notes.append(f"skipped (no spec): {', '.join(s.skipped_queries)}")
        lines.append(f"- **{s.system}**: {'; '.join(notes) if notes else 'no special cases'}.")
    lines += [
        "",
        "| Query | System | Returned | Relevant | P@5 | nDCG@5 | RR | Top results (FMA ids) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    by_run = {(r.query_id, r.system): r for r in runs}
    for row in rows:
        top = " ".join(map(str, by_run[(row.query_id, row.system)].ranked[:DEFAULT_K]))
        lines.append(
            f"| {row.query_id} | {row.system} | {row.returned} | {row.relevant_in_corpus} | "
            f"{_fmt(row.precision)} | {_fmt(row.ndcg)} | {_fmt(row.reciprocal_rank)} | {top} |"
        )
    lines += [
        "",
        "## Component evaluations",
        "",
        "- Agent A (attribute extraction) and Agent C (feedback): P06.T11.",
        "- UMAP neighborhood preservation: P07.T04.",
        "- Description factuality audit: P10.T04.",
        "",
        "## Data coverage",
        "",
        *[f"- {name.replace('_', ' ')}: {value}" for name, value in sorted(coverage.items())],
        "",
        "## Known limitations",
        "",
        LIMITATIONS,
        "## Reproduction",
        "",
        "```bash",
        "uv sync",
        "uv run python scripts/download_fma.py --subset metadata --subset small",
        "uv run python scripts/import_fma.py --subset small",
        "uv run python scripts/fetch_clap_model.py",
        "uv run python scripts/build_embeddings.py",
        f"uv run python scripts/evaluate.py --split {split}",
        "```",
        "",
    ]
    return "\n".join(lines)
