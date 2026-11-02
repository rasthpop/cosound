"""Data understanding for the evaluation inputs (CRISP-DM step 2, `docs/adr/0006-crisp-dm.md`).

Describes what the evaluation data can and cannot support before anyone reads metrics from it:
corpus listening status, queries per split, judgment coverage against the documented minimum,
the relevance distribution, queries without a relevant track, constraint judgments, and rows
whose constraint value contradicts the judge's own listening note.

The contradiction check is a heuristic for a person to review. It never changes a judgment.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from music_discovery.domain.schemas import ConstraintAttribute, ConstraintOperator
from music_discovery.evaluation.datasets import EvalDataset, EvalQuery

#: A listening note that says vocals are audible.
_VOCALS_HEARD = re.compile(
    r"\b(vocals? (are |is )?(present|on)|female vocals?|male vocals?|singing|sung|rapp(ing|ed))\b",
    re.I,
)
#: A listening note that says they are not.
_VOCALS_ABSENT = re.compile(
    r"\b(no vocals?|without vocals?|vocals? (are |is )?not present|instrumental)\b", re.I
)


@dataclass(frozen=True)
class FlaggedJudgment:
    query_id: str
    fma_track_id: int
    constraint_satisfied: str
    basis: str
    problem: str


@dataclass
class EvalProfile:
    corpus_tracks: int = 0
    listening_status: dict[str, int] = field(default_factory=dict)
    queries: int = 0
    families: int = 0
    by_split: dict[str, list[str]] = field(default_factory=dict)
    judged_pairs: int = 0
    total_pairs: int = 0
    judged_per_query: dict[str, int] = field(default_factory=dict)
    fully_judged: list[str] = field(default_factory=list)
    relevance_distribution: dict[int, int] = field(default_factory=dict)
    relevant_per_query: dict[str, int] = field(default_factory=dict)
    """Tracks with relevance ≥ threshold, for fully judged queries only."""
    without_relevant: list[str] = field(default_factory=list)
    constraint_queries: list[str] = field(default_factory=list)
    constraint_judgments: dict[str, int] = field(default_factory=dict)
    flagged: list[FlaggedJudgment] = field(default_factory=list)
    minimum: dict[str, list[str]] = field(default_factory=dict)
    """`judging_minimum.json`: required queries per split; empty when there is none."""
    missing_from_minimum: list[str] = field(default_factory=list)
    """Queries the minimum requires that are not fully judged."""


def _excludes_vocals(query: EvalQuery) -> bool:
    return any(
        c.attribute is ConstraintAttribute.VOCALS and c.operator is ConstraintOperator.EXCLUDED
        for c in query.expected_hard_constraints
    )


def _flag(query: EvalQuery, satisfied: str | None, basis: str) -> str | None:
    """Why a vocals-constraint judgment looks inconsistent with its note; None if it doesn't."""
    if not _excludes_vocals(query) or satisfied not in ("yes", "no"):
        return None
    heard = bool(_VOCALS_HEARD.search(basis)) and not _VOCALS_ABSENT.search(basis)
    absent = bool(_VOCALS_ABSENT.search(basis)) and not _VOCALS_HEARD.search(basis)
    if satisfied == "yes" and heard:
        return "marked as satisfying 'no vocals', but the note says vocals are heard"
    if satisfied == "no" and absent:
        return "marked as violating 'no vocals', but the note says there are none"
    return None


def profile_dataset(
    dataset: EvalDataset,
    *,
    relevance_threshold: int = 2,
    minimum: dict[str, list[str]] | None = None,
) -> EvalProfile:
    corpus = len(dataset.manifest)
    judged = Counter(j.query_id for j in dataset.judgments)
    fully = sorted(q.query_id for q in dataset.queries if judged[q.query_id] >= corpus > 0)
    relevant = {
        qid: sum(r >= relevance_threshold for r in dataset.relevance(qid).values()) for qid in fully
    }
    constraint_queries = sorted(q.query_id for q in dataset.queries if q.expected_hard_constraints)
    flagged = []
    for j in dataset.judgments:
        problem = _flag(dataset.query(j.query_id), j.constraint_satisfied, j.basis)
        if problem:
            flagged.append(
                FlaggedJudgment(
                    j.query_id, j.fma_track_id, j.constraint_satisfied or "", j.basis, problem
                )
            )
    minimum = minimum or {}
    required = [qid for split in ("dev", "test") for qid in minimum.get(split, [])]
    return EvalProfile(
        corpus_tracks=corpus,
        listening_status=dict(Counter(m.listening_status for m in dataset.manifest)),
        queries=len(dataset.queries),
        families=len({q.family for q in dataset.queries}),
        by_split={}
        if dataset.split is None
        else {"dev": list(dataset.split.dev), "test": list(dataset.split.test)},
        judged_pairs=len(dataset.judgments),
        total_pairs=corpus * len(dataset.queries),
        judged_per_query={q.query_id: judged[q.query_id] for q in dataset.queries},
        fully_judged=fully,
        relevance_distribution=dict(
            sorted(Counter(int(j.overall_relevance) for j in dataset.judgments).items())
        ),
        relevant_per_query=relevant,
        without_relevant=sorted(qid for qid, n in relevant.items() if n == 0),
        constraint_queries=constraint_queries,
        constraint_judgments=dict(
            Counter(
                j.constraint_satisfied or "(blank)"
                for j in dataset.judgments
                if j.query_id in constraint_queries
            )
        ),
        flagged=sorted(flagged, key=lambda f: (f.query_id, f.fma_track_id)),
        minimum={k: list(v) for k, v in minimum.items() if k in ("dev", "test")},
        missing_from_minimum=sorted(set(required) - set(fully)),
    )
