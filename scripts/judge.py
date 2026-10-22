"""Judge (query, track) relevance by listening. Resumable; never shows system scores.

    uv run python scripts/judge.py --judge "your name"
    uv run python scripts/judge.py --judge ann --play "mpv --really-quiet {path}"
    uv run python scripts/judge.py --judge ann --query q01           # one query only

Answers are appended to data/evaluation/judgments.csv immediately. Guidelines:
data/evaluation/JUDGING.md. Enter "s" to skip a pair, "q" to stop.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from datetime import UTC, datetime

from music_discovery.evaluation.datasets import JUDGMENTS_FILE, load_dataset
from music_discovery.evaluation.judging import (
    AnswerError,
    append_judgment,
    asked_fields,
    build_judgment,
    pending_pairs,
)
from music_discovery.infrastructure.settings import get_settings

PROMPTS = {
    "overall_relevance": "overall relevance 0-3 (3 strong, 2 good, 1 partial, 0 not relevant)",
    "mood_relevance": "mood relevance 0-3",
    "instrument_present": "requested instrument audible? yes / no / uncertain",
    "constraint_satisfied": "hard constraint satisfied? yes / no / unknown",
    "basis": "basis: what you heard (short note)",
}


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--judge", required=True)
    parser.add_argument("--play", help="command template to play a clip, with {path}")
    parser.add_argument("--query", action="append", help="limit to these query ids")
    args = parser.parse_args()

    directory = settings.evaluation_dir
    dataset = load_dataset(directory)
    pairs = pending_pairs(dataset, only_queries=args.query)
    total = len(dataset.queries) * len(dataset.manifest)
    print(f"{len(dataset.judgments)}/{total} judged; {len(pairs)} pending in this session.\n")

    for pair in pairs:
        path = settings.data_dir / pair.track.audio_path
        print("=" * 72)
        print(f"Query {pair.query.query_id}: {pair.query.text}")
        track = pair.track
        print(f"Track {track.fma_track_id}: {track.title} — {track.artist} [{track.genre}]")
        print(f"Audio: {path}")
        if args.play:
            subprocess.run(shlex.split(args.play.format(path=path)), check=False)
        answers: dict[str, str] = {}
        for field in asked_fields(pair.query):
            value = input(f"  {PROMPTS[field]}: ").strip()
            if value.lower() == "q":
                print("stopped; progress is saved.")
                return 0
            if value.lower() == "s":
                break
            answers[field] = value
        else:
            try:
                judgment = build_judgment(
                    pair, answers, judge=args.judge, judged_at=datetime.now(UTC)
                )
            except AnswerError as exc:
                print(f"  not saved: {exc}")
                continue
            append_judgment(directory / JUDGMENTS_FILE, judgment)
    print("no pending pairs left." if pairs else "nothing to judge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
