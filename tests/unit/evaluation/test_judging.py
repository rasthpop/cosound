import shutil
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import pytest

from music_discovery.evaluation.datasets import JUDGMENT_COLUMNS, load_dataset
from music_discovery.evaluation.judging import (
    AnswerError,
    append_judgment,
    asked_fields,
    build_judgment,
    pending_pairs,
)

REAL = Path(__file__).parents[3] / "data" / "evaluation"
NOW = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)


@pytest.fixture
def evaldir(tmp_path: Path) -> Path:
    for name in ("fma_20_manifest.csv", "queries.jsonl", "split.json", "specs_manual.jsonl"):
        shutil.copy(REAL / name, tmp_path / name)
    # start from no judgments: tests never depend on the owner's judging progress
    (tmp_path / "judgments.csv").write_text(",".join(JUDGMENT_COLUMNS) + "\n")
    return tmp_path


def test_asked_fields_follow_the_query() -> None:
    dataset = load_dataset(REAL)
    assert asked_fields(dataset.query("q01")) == [
        "overall_relevance",
        "mood_relevance",
        "instrument_present",
        "basis",
    ]
    assert asked_fields(dataset.query("q06")) == [
        "overall_relevance",
        "mood_relevance",
        "constraint_satisfied",
        "basis",
    ]
    assert asked_fields(dataset.query("q14")) == ["overall_relevance", "basis"]


def test_pairs_cover_the_grid_in_a_fixed_shuffled_order(evaldir: Path) -> None:
    dataset = load_dataset(evaldir)
    pairs = pending_pairs(dataset)
    assert len(pairs) == 400 - len(dataset.judgments)
    assert pairs == pending_pairs(dataset)
    first_queries = [p.query.query_id for p in pairs[:10]]
    assert len(set(first_queries)) > 3, "not one query after another"
    assert {p.query.query_id for p in pending_pairs(dataset, only_queries=["q05"])} == {"q05"}


def test_build_judgment_validates_answers(evaldir: Path) -> None:
    dataset = load_dataset(evaldir)
    pair = next(p for p in pending_pairs(dataset) if p.query.query_id == "q01")
    answers = {
        "overall_relevance": "3",
        "mood_relevance": "2",
        "instrument_present": "yes",
        "basis": "flute lead",
    }
    judgment = build_judgment(pair, answers, judge="ann", judged_at=NOW)
    assert (
        judgment.overall_relevance,
        judgment.instrument_present,
        judgment.constraint_satisfied,
    ) == (3, "yes", None)
    with pytest.raises(AnswerError, match="missing answers: basis"):
        build_judgment(pair, {**answers, "basis": " "}, judge="ann", judged_at=NOW)
    with pytest.raises(AnswerError, match="overall_relevance"):
        build_judgment(pair, {**answers, "overall_relevance": "5"}, judge="ann", judged_at=NOW)
    with pytest.raises(AnswerError, match="instrument_present"):
        build_judgment(pair, {**answers, "instrument_present": "maybe"}, judge="ann", judged_at=NOW)


def test_append_then_resume(evaldir: Path) -> None:
    dataset = load_dataset(evaldir)
    pair = pending_pairs(dataset)[0]
    answers = dict.fromkeys(asked_fields(pair.query), "1")
    answers["basis"] = "heard it"
    for field in ("instrument_present",):
        if field in answers:
            answers[field] = "uncertain"
    if "constraint_satisfied" in answers:
        answers["constraint_satisfied"] = "unknown"
    append_judgment(
        evaldir / "judgments.csv", build_judgment(pair, answers, judge="ann", judged_at=NOW)
    )
    reloaded = load_dataset(evaldir)
    assert len(reloaded.judgments) == 1
    remaining = pending_pairs(reloaded)
    assert len(remaining) == 399
    assert pair not in remaining


def test_append_creates_header(tmp_path: Path) -> None:
    dataset = load_dataset(REAL)
    pair = next(p for p in pending_pairs(dataset) if p.query.query_id == "q14")
    path = tmp_path / "new.csv"
    append_judgment(
        path,
        build_judgment(
            pair, {"overall_relevance": "0", "basis": "harsh noise"}, judge="ann", judged_at=NOW
        ),
    )
    lines = path.read_text().splitlines()
    assert lines[0].startswith("query_id,fma_track_id,overall_relevance")
    assert lines[1].startswith(f"q14,{pair.track.fma_track_id},0,,,,ann,harsh noise,")


def test_track_order_groups_each_clip() -> None:
    dataset = load_dataset(REAL)
    pairs = pending_pairs(dataset, order="track")
    tracks = [p.track.fma_track_id for p in pairs]
    changes = sum(1 for a, b in pairwise(tracks) if a != b)
    assert changes == len(set(tracks)) - 1, "all pairs of a track are consecutive"
    assert pairs == pending_pairs(dataset, order="track")
    only = pending_pairs(dataset, only_tracks=[76075], order="track")
    assert {p.track.fma_track_id for p in only} == {76075}


def test_player_plays_in_background_and_stops_early(tmp_path: Path) -> None:
    from music_discovery.evaluation.judging import Player

    player = Player("sleep 30 {path}")
    player.play(tmp_path / "clip.mp3")
    assert player.playing, "playback does not block judging"
    player.stop()
    assert not player.playing
    player.play(tmp_path / "a.mp3")
    player.play(tmp_path / "b.mp3")  # starting a new clip stops the previous one
    assert player.playing
    player.stop()
    silent = Player(None)
    silent.play(tmp_path / "clip.mp3")
    assert not silent.playing


def test_check_answer() -> None:
    from music_discovery.evaluation.judging import check_answer

    assert check_answer("overall_relevance", " 2 ") == "2"
    assert check_answer("overall_relevance", "4") is None
    assert check_answer("overall_relevance", "great") is None
    assert check_answer("instrument_present", "YES") == "yes"
    assert check_answer("instrument_present", "maybe") is None
    assert check_answer("constraint_satisfied", "unknown") == "unknown"
    assert check_answer("basis", "  soft flute  ") == "soft flute"
    assert check_answer("basis", "   ") is None
