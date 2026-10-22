"""Run metadata-only, CLAP-only and hybrid retrieval side by side (Milestone 3).

    uv run python scripts/compare_baselines.py                    # 20-track evaluation corpus
    uv run python scripts/compare_baselines.py --corpus catalog   # the full fma_small catalog

Specs come from data/evaluation/specs_manual.jsonl (hand-written until Agent A exists, P06).
Writes artifacts/evaluation/scratch/baselines_<corpus>.csv (git-ignored). No metrics here;
those need human judgments (P05).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from _runtime import build_runtime

from music_discovery.domain.schemas import SearchSpecification
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.fma_loader import fma_track_id
from music_discovery.ingestion.fma_manifest import read_manifest
from music_discovery.retrieval.hybrid_retriever import Mode

MODES: tuple[Mode, ...] = ("metadata_only", "semantic_only", "hybrid")
COLUMNS = [
    "query_id",
    "query",
    "mode",
    "outcome",
    "rank",
    "fma_track_id",
    "title",
    "artist",
    "genre",
    "final",
    "semantic",
    "metadata",
    "sources",
    "degraded",
]


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}"


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--specs", type=Path, default=settings.evaluation_dir / "specs_manual.jsonl"
    )
    parser.add_argument("--corpus", choices=["manifest", "catalog"], default="manifest")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--out", type=Path, default=settings.evaluation_artifacts_dir / "scratch")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    runtime = build_runtime(settings)
    corpus = None
    if args.corpus == "manifest":
        manifest = read_manifest(settings.evaluation_dir / "fma_20_manifest.csv")
        corpus = [fma_track_id(int(r["fma_track_id"])) for r in manifest]
    specs = [
        json.loads(line)
        for line in args.specs.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rows: list[dict[str, str]] = []
    for item in specs:
        spec = SearchSpecification.model_validate(item["spec"])
        for mode in MODES:
            result = runtime.retriever.retrieve(spec, mode=mode, limit=args.k, corpus=corpus)
            degraded = ";".join(result.outcome.degraded)
            if not result.outcome.candidates:
                rows.append(
                    {
                        **dict.fromkeys(COLUMNS, ""),
                        "query_id": item["query_id"],
                        "query": spec.original_query,
                        "mode": mode,
                        "outcome": result.outcome.kind.value,
                        "degraded": degraded,
                    }
                )
            for candidate in result.outcome.candidates:
                track = runtime.tracks[candidate.track_id]
                fma_id = next((e.value for e in track.external_ids if e.kind.value == "track"), "")
                rows.append(
                    {
                        "query_id": item["query_id"],
                        "query": spec.original_query,
                        "mode": mode,
                        "outcome": result.outcome.kind.value,
                        "rank": str(candidate.rank),
                        "fma_track_id": fma_id,
                        "title": track.title,
                        "artist": ", ".join(a.name for a in track.artists),
                        "genre": track.genres[0] if track.genres else "",
                        "final": fmt(candidate.score.final),
                        "semantic": fmt(candidate.score.semantic),
                        "metadata": fmt(candidate.score.metadata),
                        "sources": "+".join(s.value for s in candidate.retrieval_sources),
                        "degraded": degraded,
                    }
                )

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"baselines_{args.corpus}.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    for item in specs:
        print(f"\n## {item['query_id']} {item['spec']['original_query']}")
        for mode in MODES:
            picks = [r for r in rows if r["query_id"] == item["query_id"] and r["mode"] == mode]
            text = (
                " | ".join(f"{r['title'][:22]} ({r['genre']})" for r in picks if r["rank"])
                or picks[0]["outcome"]
            )
            print(f"  {mode:<14} {text}")
    print(f"\nwrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
