"""Run the evaluation: metadata-only, CLAP-only and hybrid on the 20-track corpus.

    uv run python scripts/evaluate.py                       # dev split (default)
    uv run python scripts/evaluate.py --split test --allow-test
    uv run python scripts/evaluate.py --components agent_a,agent_c --split dev

Writes artifacts/evaluation/<run_id>/ (and copies it to artifacts/evaluation/): manifest.csv,
queries.jsonl, judgments.csv, per_query_results.csv, metrics.json, comparison.csv,
config_snapshot.json, report.md, and agent_a.csv / agent_c.csv for --components. Specs come
from Agent A (deterministic parser) unless --specs manual. The test split is run once per
reported configuration, so it needs --allow-test.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime

from _runtime import build_runtime

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.evaluation import agent_eval
from music_discovery.evaluation.datasets import (
    JUDGMENTS_FILE,
    MANIFEST_FILE,
    QUERIES_FILE,
    SPECS_FILE,
    SPLIT_FILE,
    file_sha256,
    load_dataset,
)
from music_discovery.evaluation.report import write_csv, write_run
from music_discovery.evaluation.runners import SYSTEMS, run_systems, score_runs
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
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
    parser.add_argument("--specs", choices=["agent_a", "manual"], default="agent_a")
    parser.add_argument(
        "--components", default="", help="comma-separated: agent_a, agent_c (component evals)"
    )
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
    components = [c for c in args.components.split(",") if c]
    if unknown := set(components) - {"agent_a", "agent_c"}:
        print(f"unknown components: {sorted(unknown)}", file=sys.stderr)
        return 2
    lexicon = load_lexicon()
    query_agent = QueryAgent(lexicon)
    query_ids = (
        dataset.split.of(args.split) if dataset.split else [q.query_id for q in dataset.queries]
    )
    specs = (
        {q: query_agent.interpret(dataset.query(q).text) for q in query_ids}
        if args.specs == "agent_a"
        else None
    )
    runs = run_systems(dataset, runtime.retriever, systems=systems, split=args.split, specs=specs)
    rows, summaries = score_runs(dataset, runs)

    component_metrics: dict[str, object] = {}
    component_csv: dict[str, list[dict[str, object]]] = {}
    queries = [dataset.query(q) for q in query_ids]
    if "agent_a" in components:
        a_rows = agent_eval.evaluate_agent_a(queries, query_agent)
        component_metrics["agent_a"] = agent_eval.agent_a_metrics(a_rows, llm_enabled=False)
        component_csv["agent_a.csv"] = agent_eval.agent_a_csv_rows(a_rows)
    if "agent_c" in components:
        corpus = [m.track_id for m in dataset.manifest]

        def retrieve(spec: SearchSpecification) -> list[str]:
            result = runtime.retriever.retrieve(
                spec, mode="hybrid", limit=len(corpus), corpus=corpus
            )
            return [c.track_id for c in result.outcome.candidates]

        descriptions = DescriptionConfig.load(
            settings.project_root / "config" / "descriptions.yaml"
        )
        feedback_agent = FeedbackAgent(
            lexicon,
            SqlTrackRepository(Database(settings.database_url)),
            EvidenceBuilder(descriptions.semantic_bands),
            DescriptionService(descriptions),
        )
        in_split = set(query_ids)
        cases = [c for c in agent_eval.load_cases(dataset_dir) if c.query_id in in_split]
        c_rows = agent_eval.evaluate_agent_c(
            cases,
            dataset,
            query_agent=query_agent,
            feedback_agent=feedback_agent,
            retrieve=retrieve,
            normalizer=FeedbackTextNormalizer(lexicon),
        )
        component_metrics["agent_c"] = agent_eval.agent_c_metrics(c_rows)
        component_csv["agent_c.csv"] = agent_eval.agent_c_csv_rows(c_rows)

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
        "specs_source": args.specs,
        "lexicon_version": lexicon.version,
        "components": components,
        "retrieval_config": config.model_dump(mode="json"),
        "inputs_sha256": {
            name: file_sha256(dataset_dir / name)
            for name in (
                MANIFEST_FILE,
                QUERIES_FILE,
                JUDGMENTS_FILE,
                SPLIT_FILE,
                SPECS_FILE,
                agent_eval.CASES_FILE,
            )
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
        components=component_metrics,
        component_lines=agent_eval.components_markdown(
            component_metrics.get("agent_a"),  # type: ignore[arg-type]
            component_metrics.get("agent_c"),  # type: ignore[arg-type]
        ),
    )
    for name, csv_rows in component_csv.items():
        write_csv(run_dir / name, csv_rows, list(csv_rows[0]) if csv_rows else ["id"])
    for path in run_dir.iterdir():
        shutil.copy(path, out_root / path.name)  # latest run at artifacts/evaluation/

    total = len(dataset.queries) * len(dataset.manifest)
    print(f"run {run_id}: {len(runs)} query runs, judgments {len(dataset.judgments)}/{total}")
    for s in summaries:
        ndcg = "—" if s.ndcg.value is None else f"{s.ndcg.value:.3f}"
        print(f"  {s.system:<14} nDCG@5 {ndcg} (n={s.ndcg.n})")
    for name, metrics in component_metrics.items():
        print(f"  {name}: {metrics}")
    print(f"artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
