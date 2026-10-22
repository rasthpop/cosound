"""Run the evaluation: metadata-only, CLAP-only and hybrid on the 20-track corpus.

    uv run python scripts/evaluate.py                       # dev split (default)
    uv run python scripts/evaluate.py --split test --allow-test

Writes artifacts/evaluation/<run_id>/ (and copies it to artifacts/evaluation/): manifest.csv,
queries.jsonl, judgments.csv, per_query_results.csv, metrics.json, comparison.csv,
config_snapshot.json, report.md. The test split is run once per reported configuration, so it
needs --allow-test.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime

from _runtime import build_runtime

from music_discovery.evaluation.datasets import (
    JUDGMENTS_FILE,
    MANIFEST_FILE,
    QUERIES_FILE,
    SPECS_FILE,
    SPLIT_FILE,
    file_sha256,
    load_dataset,
)
from music_discovery.evaluation.report import write_run
from music_discovery.evaluation.runners import SYSTEMS, run_systems, score_runs
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import SqlTrackAudioRepository
from music_discovery.infrastructure.settings import get_settings


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--systems", default=",".join(SYSTEMS))
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.split in ("test", "all") and not args.allow_test:
        print(
            "the test split is held out; pass --allow-test for the final, reported run",
            file=sys.stderr,
        )
        return 2

    dataset_dir = settings.evaluation_dir
    dataset = load_dataset(dataset_dir)
    runtime = build_runtime(settings)
    config = runtime.retriever.config
    systems = [s for s in args.systems.split(",") if s]
    runs = run_systems(dataset, runtime.retriever, systems=systems, split=args.split)
    rows, summaries = score_runs(dataset, runs)

    audio = {
        a.track_id: a for a in SqlTrackAudioRepository(Database(settings.database_url)).list_all()
    }
    corpus_audio = [audio[m.track_id] for m in dataset.manifest if m.track_id in audio]
    coverage = {
        "corpus_tracks": len(dataset.manifest),
        "corpus_tracks_with_valid_audio": len(corpus_audio),
        "corpus_tracks_with_embeddings": sum(a.has_embedding for a in corpus_audio),
        "queries_in_split": len({r.query_id for r in runs}),
        "queries_with_relevant_track": len({r.query_id for r in rows if r.relevant_in_corpus > 0}),
        "queries_skipped": len({r.query_id for r in rows if r.skipped}),
        "judged_pairs": len(dataset.judgments),
    }
    run_id = args.run_id or f"{config.weights_version}-{args.split}"
    snapshot = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "split": args.split,
        "systems": systems,
        "model_id": settings.clap_model_version,
        "embedding_version": runtime.embedding_version,
        "weights_version": config.weights_version,
        "retrieval_config": config.model_dump(mode="json"),
        "inputs_sha256": {
            name: file_sha256(dataset_dir / name)
            for name in (MANIFEST_FILE, QUERIES_FILE, JUDGMENTS_FILE, SPLIT_FILE, SPECS_FILE)
            if (dataset_dir / name).is_file()
        },
    }
    out_root = settings.evaluation_artifacts_dir
    run_dir = write_run(
        out_root / run_id,
        dataset=dataset,
        dataset_dir=dataset_dir,
        runs=runs,
        rows=rows,
        summaries=summaries,
        split=args.split,
        snapshot=snapshot,
        coverage=coverage,
    )
    for path in run_dir.iterdir():
        shutil.copy(path, out_root / path.name)  # latest run at artifacts/evaluation/

    total = len(dataset.queries) * len(dataset.manifest)
    print(f"run {run_id}: {len(runs)} query runs, judgments {len(dataset.judgments)}/{total}")
    for s in summaries:
        ndcg = "—" if s.ndcg.value is None else f"{s.ndcg.value:.3f}"
        print(f"  {s.system:<14} nDCG@5 {ndcg} (n={s.ndcg.n})")
    print(f"artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
