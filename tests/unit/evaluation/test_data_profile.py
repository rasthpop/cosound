from __future__ import annotations

from datetime import UTC, datetime

from music_discovery.domain.schemas import ConstraintAttribute, ConstraintOperator, HardConstraint
from music_discovery.evaluation.data_profile import profile_dataset
from music_discovery.evaluation.datasets import (
    EvalDataset,
    EvalQuery,
    ExpectedAttributes,
    Judgment,
    ManifestEntry,
)

NOW = datetime(2026, 11, 2, tzinfo=UTC)
NO_VOCALS = HardConstraint(
    attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
)


def manifest(n: int) -> list[ManifestEntry]:
    return [
        ManifestEntry(
            fma_track_id=i,
            title=f"T{i}",
            artist="A",
            genre="Folk",
            audio_path=f"{i}.mp3",
            license="CC BY",
        )
        for i in range(1, n + 1)
    ]


def query(qid: str, constraints: list[HardConstraint] | None = None) -> EvalQuery:
    return EvalQuery(
        query_id=qid, family=f"f{qid}", text="x", expected_attributes=ExpectedAttributes(),
        expected_hard_constraints=constraints or [],
    )  # fmt: skip


def judgment(
    qid: str, tid: int, rel: int, satisfied: str | None = None, basis: str = "listened"
) -> Judgment:
    return Judgment(
        query_id=qid, fma_track_id=tid, overall_relevance=rel, constraint_satisfied=satisfied,
        judge="t", basis=basis, judged_at=NOW,
    )  # fmt: skip


def dataset() -> EvalDataset:
    return EvalDataset(
        manifest=manifest(2),
        queries=[query("q01"), query("q02", [NO_VOCALS]), query("q03")],
        judgments=[
            judgment("q01", 1, 3),
            judgment("q01", 2, 0),
            judgment("q02", 1, 0, "yes", "vocals present"),
            judgment("q02", 2, 1, "no", "no vocals, just piano"),
            judgment("q03", 1, 2),  # q03 is only partly judged
        ],
        split=None,
        specs={},
    )


def test_coverage_relevance_and_minimum() -> None:
    p = profile_dataset(dataset(), minimum={"dev": ["q01", "q03"], "test": ["q02"]})
    assert (p.judged_pairs, p.total_pairs) == (5, 6)
    assert p.fully_judged == ["q01", "q02"]
    assert p.relevant_per_query == {"q01": 1, "q02": 0}
    assert p.without_relevant == ["q02"]
    assert p.relevance_distribution == {0: 2, 1: 1, 2: 1, 3: 1}
    assert p.missing_from_minimum == ["q03"]
    assert p.listening_status == {"pending": 2}


def test_flags_constraint_judgments_that_contradict_the_note() -> None:
    p = profile_dataset(dataset())
    assert p.constraint_queries == ["q02"]
    assert p.constraint_judgments == {"yes": 1, "no": 1}
    flagged = {(f.fma_track_id, f.constraint_satisfied) for f in p.flagged}
    assert flagged == {(1, "yes"), (2, "no")}


def test_consistent_notes_are_not_flagged() -> None:
    ds = dataset()
    ds.judgments[2:4] = [
        judgment("q02", 1, 0, "no", "female vocals throughout"),
        judgment("q02", 2, 1, "yes", "instrumental, no vocals"),
    ]
    assert profile_dataset(ds).flagged == []
