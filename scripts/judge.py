"""Judge (query, track) relevance by listening. Resumable; never shows system scores.

    uv run python scripts/judge.py --judge ann --play "cvlc --play-and-exit --quiet {path}"
    uv run python scripts/judge.py --judge ann --play "..." --by-track      # each clip once
    uv run python scripts/judge.py --judge ann --play "..." --query q01     # one query only
    uv run python scripts/judge.py --judge ann --play "..." --track 76075   # one track only

The clip plays in the background: answer whenever you have heard enough, there is no need to
wait for it to finish. At any prompt: "r" replays the clip, "x" stops it, "s" skips the pair,
"q" (or Ctrl+C) stops judging. Answers are saved after every pair; rerun to resume.
Guidelines: data/evaluation/JUDGING.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from music_discovery.evaluation.datasets import JUDGMENTS_FILE, load_dataset
from music_discovery.evaluation.judging import (
    FIELD_CHOICES,
    AnswerError,
    Pair,
    Player,
    append_judgment,
    asked_fields,
    build_judgment,
    check_answer,
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


class QuitJudgingError(Exception):
    pass


def ask_pair(pair: Pair, player: Player, path: Path) -> dict[str, str] | None:
    """Collect the answers for one pair; None means the pair was skipped."""
    answers: dict[str, str] = {}
    for field in asked_fields(pair.query):
        while True:
            value = input(f"  {PROMPTS[field]}: ").strip()
            command = value.lower()
            if command == "q":
                raise QuitJudgingError
            if command == "s":
                return None
            if command == "r":
                player.play(path)
                continue
            if command == "x":
                player.stop()
                continue
            checked = check_answer(field, value)
            if checked is None:
                choices = " / ".join(FIELD_CHOICES.get(field, ())) or "a short note"
                print(f"    please answer {choices}")
                continue
            answers[field] = checked
            break
    return answers


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--judge", required=True)
    parser.add_argument("--play", help="command template to play a clip, with {path}")
    parser.add_argument("--query", action="append", help="limit to these query ids")
    parser.add_argument("--track", action="append", type=int, help="limit to these FMA track ids")
    parser.add_argument(
        "--by-track", action="store_true", help="judge every query for one clip before the next"
    )
    args = parser.parse_args()

    directory = settings.evaluation_dir
    dataset = load_dataset(directory)
    pairs = pending_pairs(
        dataset,
        only_queries=args.query,
        only_tracks=args.track,
        order="track" if args.by_track else "pair",
    )
    total = len(dataset.queries) * len(dataset.manifest)
    print(f"{len(dataset.judgments)}/{total} judged; {len(pairs)} pending in this session.")
    print('Commands at any prompt: "r" replay, "x" stop clip, "s" skip pair, "q" quit.\n')

    player = Player(args.play)
    current_track: int | None = None
    saved = 0
    try:
        for pair in pairs:
            track = pair.track
            path = settings.data_dir / track.audio_path
            if track.fma_track_id != current_track:
                current_track = track.fma_track_id
                print("=" * 72)
                print(f"Track {track.fma_track_id}: {track.title} — {track.artist} [{track.genre}]")
                print(f"Audio: {path}")
                player.play(path)
            elif not args.by_track:
                player.play(path)
            print(f"\n Query {pair.query.query_id}: {pair.query.text}")
            answers = ask_pair(pair, player, path)
            if not args.by_track:
                player.stop()  # moving on: never wait for the clip to end
            if answers is None:
                continue
            try:
                judgment = build_judgment(
                    pair, answers, judge=args.judge, judged_at=datetime.now(UTC)
                )
            except AnswerError as exc:
                print(f"  not saved: {exc}")
                continue
            append_judgment(directory / JUDGMENTS_FILE, judgment)
            saved += 1
    except (QuitJudgingError, KeyboardInterrupt, EOFError):
        print(f"\nstopped; {saved} judgments saved this session.")
        return 0
    finally:
        player.stop()
    print(f"done: {saved} judgments saved; no pending pairs left in this selection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
