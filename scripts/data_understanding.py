"""CRISP-DM step 2: the data-understanding report (docs/adr/0006-crisp-dm.md).

Profiles the local catalog (field completeness, genre balance, audio and embedding coverage) and
the evaluation inputs (judgment coverage, relevance distribution, constraint judgments and
judgments that contradict their own listening notes). Read-only; never uses the network.

    uv run python scripts/data_understanding.py   # writes artifacts/data-understanding/
    uv run python scripts/data_understanding.py --out docs/crisp-dm/data-understanding.md

Writes `report.md` and `profile.json` to `--out-dir` (default `artifacts/data-understanding`).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from music_discovery.evaluation.data_profile import EvalProfile, profile_dataset
from music_discovery.evaluation.datasets import load_dataset
from music_discovery.evaluation.metrics import DEFAULT_THRESHOLD
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import SqlTrackAudioRepository, SqlTrackRepository
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.catalog_report import CatalogProfile, profile


def pct(n: int, total: int) -> str:
    return "n/a" if total == 0 else f"{100 * n / total:.1f} %"


def catalog_section(c: CatalogProfile) -> list[str]:
    lines = [
        "## Catalog",
        "",
        f"- Tracks: **{c.tracks}** ({', '.join(f'{k}: {v}' for k, v in c.by_source.items())})",
        f"- Validated, decodable audio: {c.with_decodable_audio}"
        f" ({pct(c.with_decodable_audio, c.tracks)})",
        f"- Audio embeddings: {c.with_embeddings} ({pct(c.with_embeddings, c.tracks)});"
        " only these tracks are on the map and in sound-based search",
        f"- Tracks without audio: {len(c.without_audio)}"
        + (
            f" ({', '.join(c.without_audio[:10])}{' …' if len(c.without_audio) > 10 else ''})"
            if c.without_audio
            else ""
        ),
        "",
        "### Field completeness",
        "",
        "Missing values are counted, never filled (missing is not zero).",
        "",
        "| Field | Present | Share |",
        "|---|---|---|",
        *[f"| `{name}` | {n} | {pct(n, c.tracks)} |" for name, n in c.present.items()],
        "",
        "### Genre balance (first genre per track, the map colour)",
        "",
        "| Genre | Tracks | Share |",
        "|---|---|---|",
        *[f"| {g} | {n} | {pct(n, c.tracks)} |" for g, n in c.first_genre.items()],
        "",
        "Genre tags per track: " + ", ".join(f"{k}: {v}" for k, v in c.genres_per_track.items()),
        "",
        "### Audio licenses",
        "",
        *[f"- {lic}: {n}" for lic, n in list(c.audio_licenses.items())[:10]],
        *(
            [
                f"- … {len(c.audio_licenses) - 10} more license texts"
                f" ({sum(list(c.audio_licenses.values())[10:])} tracks); full list in profile.json"
            ]
            if len(c.audio_licenses) > 10
            else []
        ),
        "",
    ]
    return lines


def evaluation_section(e: EvalProfile) -> list[str]:
    status = ", ".join(f"{k}: {v}" for k, v in sorted(e.listening_status.items()))
    lines = [
        "## Evaluation inputs",
        "",
        f"- Corpus: {e.corpus_tracks} tracks; listening status {status}",
        f"- Queries: {e.queries} in {e.families} families;"
        + "".join(f" {split} {len(ids)}" for split, ids in e.by_split.items()),
        f"- Judged pairs: {e.judged_pairs} of {e.total_pairs}"
        f" ({pct(e.judged_pairs, e.total_pairs)})",
        f"- Fully judged queries: {len(e.fully_judged)} ({', '.join(e.fully_judged) or 'none'})",
    ]
    if e.minimum:
        lines.append(
            "- Documented minimum (`judging_minimum.json`): "
            + "; ".join(f"{k} {', '.join(v)}" for k, v in e.minimum.items())
        )
        lines.append(
            "- Required but not fully judged: " + (", ".join(e.missing_from_minimum) or "none")
        )
    lines += [
        "",
        "### Relevance",
        "",
        "Overall relevance distribution (0-3, all judged pairs): "
        + ", ".join(f"{k}: {v}" for k, v in e.relevance_distribution.items()),
        "",
        "| Query | Judged | Relevant (≥ threshold) |",
        "|---|---|---|",
        *[
            f"| {qid} | {n} | {e.relevant_per_query.get(qid, '—')} |"
            for qid, n in e.judged_per_query.items()
        ],
        "",
        "Fully judged queries without any relevant track: "
        + (", ".join(e.without_relevant) or "none"),
        "",
        "### Hard constraints",
        "",
        "Queries with hard constraints: "
        f"{', '.join(e.constraint_queries) or 'none'}. Their constraint"
        " judgments: " + ", ".join(f"{k}: {v}" for k, v in sorted(e.constraint_judgments.items())),
        "",
        "### Judgments to review",
        "",
    ]
    if e.flagged:
        lines += [
            "These rows look inconsistent with the judge's own listening note (heuristic; a person"
            " decides, nothing is changed automatically):",
            "",
            "| Query | FMA track | constraint_satisfied | Note | Problem |",
            "|---|---|---|---|---|",
            *[
                f"| {f.query_id} | {f.fma_track_id} | {f.constraint_satisfied}"
                f" | {f.basis} | {f.problem} |"
                for f in e.flagged
            ],
        ]
    else:
        lines.append("None found.")
    return [*lines, ""]


def render(catalog: CatalogProfile, evaluation: EvalProfile, *, created_at: datetime) -> str:
    header = [
        "# Data understanding report",
        "",
        f"Generated {created_at:%Y-%m-%d %H:%M} UTC by `scripts/data_understanding.py`"
        " (CRISP-DM step 2, `docs/adr/0006-crisp-dm.md`). Read-only; regenerate rather than edit.",
        "",
    ]
    return "\n".join([*header, *catalog_section(catalog), *evaluation_section(evaluation)])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="also copy report.md here")
    args = parser.parse_args()
    settings = get_settings()
    database = Database(settings.database_url)
    database.init_schema()
    catalog = profile(SqlTrackRepository(database), SqlTrackAudioRepository(database))
    minimum_path = settings.evaluation_dir / "judging_minimum.json"
    minimum = json.loads(minimum_path.read_text()) if minimum_path.exists() else None
    evaluation = profile_dataset(
        load_dataset(settings.evaluation_dir),
        relevance_threshold=DEFAULT_THRESHOLD,
        minimum=minimum,
    )
    report = render(catalog, evaluation, created_at=datetime.now(UTC))
    out_dir = args.out_dir or settings.artifacts_dir / "data-understanding"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(report)
    (out_dir / "profile.json").write_text(
        json.dumps(
            {"catalog": asdict(catalog), "evaluation": asdict(evaluation)}, indent=2, default=str
        )
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    print(f"wrote {out_dir / 'report.md'}" + (f" and {args.out}" if args.out else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
