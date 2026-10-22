import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from music_discovery.evaluation.datasets import (
    JUDGMENT_COLUMNS,
    DatasetError,
    EvalQuery,
    internal_track_id,
    load_dataset,
    make_split,
)

REAL = Path(__file__).parents[3] / "data" / "evaluation"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def evaldir(tmp_path: Path) -> Path:
    for name in (
        "fma_20_manifest.csv",
        "queries.jsonl",
        "split.json",
        "specs_manual.jsonl",
        "judgments.csv",
    ):
        shutil.copy(REAL / name, tmp_path / name)
    return tmp_path


def add_judgments(directory: Path, *rows: str) -> None:
    with (directory / "judgments.csv").open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row + "\n")


FIRST_TRACK = 76075  # first manifest row


def test_committed_inputs_are_valid() -> None:
    dataset = load_dataset(REAL)
    assert len(dataset.manifest) == 20
    assert len(dataset.queries) == 20
    assert dataset.split is not None
    assert len(dataset.split.dev) == len(dataset.split.test) == 10
    assert set(dataset.specs) == {q.query_id for q in dataset.queries}
    assert dataset.judged_fraction() == len(dataset.judgments) / 400


def test_judgments_load_with_blank_optional_fields(evaldir: Path) -> None:
    add_judgments(
        evaldir, f"q01,{FIRST_TRACK},3,2,yes,,ann,clear flute melody,2026-10-22T10:00:00Z"
    )
    dataset = load_dataset(evaldir)
    j = dataset.judgment("q01", FIRST_TRACK)
    assert j is not None
    assert (
        j.overall_relevance,
        j.mood_relevance,
        j.instrument_present,
        j.constraint_satisfied,
    ) == (3, 2, "yes", None)
    assert dataset.relevance("q01") == {FIRST_TRACK: 3}
    assert j.track_id == internal_track_id(FIRST_TRACK)


@pytest.mark.parametrize(
    ("row", "problem"),
    [
        (f"q99,{FIRST_TRACK},1,,,,ann,heard it,2026-10-22T10:00:00Z", "unknown query"),
        ("q01,123456789,1,,,,ann,heard it,2026-10-22T10:00:00Z", "outside the corpus"),
        (f"q01,{FIRST_TRACK},4,,,,ann,heard it,2026-10-22T10:00:00Z", "judgments.csv row 1"),
        (f"q01,{FIRST_TRACK},2,,,,ann,,2026-10-22T10:00:00Z", "judgments.csv row 1"),
        (f"q01,{FIRST_TRACK},2,,maybe,,ann,heard it,2026-10-22T10:00:00Z", "judgments.csv row 1"),
    ],
)
def test_invalid_judgments_are_reported(evaldir: Path, row: str, problem: str) -> None:
    add_judgments(evaldir, row)
    with pytest.raises(DatasetError) as info:
        load_dataset(evaldir)
    assert any(problem in p for p in info.value.problems)


def test_duplicate_judgments_rejected(evaldir: Path) -> None:
    row = f"q01,{FIRST_TRACK},2,,,,ann,heard it,2026-10-22T10:00:00Z"
    add_judgments(evaldir, row, row)
    with pytest.raises(DatasetError, match="duplicate judgment"):
        load_dataset(evaldir)


def test_split_must_cover_queries_and_keep_families(evaldir: Path) -> None:
    split = json.loads((evaldir / "split.json").read_text())
    split["dev"].remove("q11")
    split["test"].append("q11")  # q11 is a rephrasing of q01 (dev)
    (evaldir / "split.json").write_text(json.dumps(split))
    with pytest.raises(DatasetError, match="families split"):
        load_dataset(evaldir)
    (evaldir / "split.json").unlink()
    with pytest.raises(DatasetError, match=r"split\.json is missing"):
        load_dataset(evaldir)
    assert load_dataset(evaldir, require_split=False).split is None


def q(qid: str, family: str) -> EvalQuery:
    return EvalQuery.model_validate(
        {"query_id": qid, "family": family, "text": qid, "expected_attributes": {}}
    )


def test_make_split_is_deterministic_and_keeps_families() -> None:
    queries = [q(f"q{i:02d}", f"f{i % 7}") for i in range(1, 21)]
    a = make_split(queries, seed=42, created_at=NOW)
    b = make_split(list(reversed(queries)), seed=42, created_at=NOW)
    assert (a.dev, a.test) == (b.dev, b.test)
    assert sorted(a.dev + a.test) == sorted(x.query_id for x in queries)
    for family in {x.family for x in queries}:
        members = {x.query_id for x in queries if x.family == family}
        assert members <= set(a.dev) or members <= set(a.test)


def test_judgment_columns_match_committed_header() -> None:
    header = (REAL / "judgments.csv").read_text().splitlines()[0].split(",")
    assert tuple(header) == JUDGMENT_COLUMNS
