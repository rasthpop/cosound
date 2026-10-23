"""Run retrieval systems over evaluation queries and score them (base.md §12.5-12.6).

The three systems are the same `HybridRetriever` in different modes, restricted to the fixed
evaluation corpus. Specifications are Agent A's deterministic readings by default (P06.T11);
`specs_manual.jsonl` is still available as a baseline (`scripts/evaluate.py --specs manual`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from music_discovery.domain.enums import SearchOutcomeKind
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.evaluation.datasets import EvalDataset
from music_discovery.evaluation.metrics import (
    DEFAULT_K,
    DEFAULT_THRESHOLD,
    Mean,
    constraint_satisfaction,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from music_discovery.retrieval.hybrid_retriever import HybridResult, Mode

SplitName = Literal["dev", "test", "all"]
SYSTEMS: tuple[Mode, ...] = ("metadata_only", "semantic_only", "hybrid")


class Retriever(Protocol):
    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Sequence[str] | None = None,
    ) -> HybridResult: ...


@dataclass(frozen=True)
class QueryRun:
    query_id: str
    system: Mode
    outcome: str
    ranked: list[int]
    """FMA track ids, best first."""
    finals: list[float]
    degraded: list[str]
    skipped: str | None = None


def run_systems(
    dataset: EvalDataset,
    retriever: Retriever,
    *,
    systems: Sequence[Mode] = SYSTEMS,
    split: SplitName = "dev",
    depth: int = 10,
    specs: Mapping[str, SearchSpecification] | None = None,
) -> list[QueryRun]:
    """Run every system on every query of the split (depth >= k so MRR sees past the top k).

    `specs` (query id -> spec) replaces the manual specs of the dataset when given.
    """
    query_ids = dataset.split.of(split) if dataset.split else [q.query_id for q in dataset.queries]
    corpus = [m.track_id for m in dataset.manifest]
    to_fma = {m.track_id: m.fma_track_id for m in dataset.manifest}
    runs: list[QueryRun] = []
    for query_id in query_ids:
        if specs is not None:
            spec = specs.get(query_id)
        else:
            payload = dataset.specs.get(query_id)
            spec = None if payload is None else SearchSpecification.model_validate(payload)
        for system in systems:
            if spec is None:
                runs.append(QueryRun(query_id, system, "skipped", [], [], [], skipped="no_spec"))
                continue
            result = retriever.retrieve(spec, mode=system, limit=depth, corpus=corpus)
            candidates = result.outcome.candidates
            runs.append(
                QueryRun(
                    query_id=query_id,
                    system=system,
                    outcome=result.outcome.kind.value,
                    ranked=[to_fma[c.track_id] for c in candidates],
                    finals=[c.score.final for c in candidates],
                    degraded=list(result.outcome.degraded),
                )
            )
    return runs


@dataclass(frozen=True)
class QueryMetrics:
    query_id: str
    system: Mode
    outcome: str
    returned: int
    relevant_in_corpus: int
    judged_pairs: int
    unjudged_in_top_k: int
    precision: float | None
    recall: float | None
    ndcg: float | None
    reciprocal_rank: float | None
    constraint_satisfied: float | None
    constraint_unknown: float | None
    skipped: str | None


@dataclass
class SystemSummary:
    system: Mode
    precision: Mean
    recall: Mean
    ndcg: Mean
    mrr: Mean
    constraint_satisfied: Mean
    constraint_unknown: Mean
    queries: int
    no_relevant_queries: list[str] = field(default_factory=list)
    skipped_queries: list[str] = field(default_factory=list)
    no_confident_match: list[str] = field(default_factory=list)


def score_runs(
    dataset: EvalDataset,
    runs: Sequence[QueryRun],
    *,
    k: int = DEFAULT_K,
    threshold: int = DEFAULT_THRESHOLD,
) -> tuple[list[QueryMetrics], list[SystemSummary]]:
    rows: list[QueryMetrics] = []
    for run in runs:
        rel = dataset.relevance(run.query_id)
        relevant = sum(1 for r in rel.values() if r >= threshold)
        has_relevant = relevant > 0
        query = dataset.query(run.query_id)
        constrained = bool(query.expected_hard_constraints)
        statuses = [
            j.constraint_satisfied if (j := dataset.judgment(run.query_id, t)) else None
            for t in run.ranked
        ]
        rate = (
            constraint_satisfaction(statuses, k=k) if constrained and run.skipped is None else None
        )
        defined = run.skipped is None and bool(rel)
        rows.append(
            QueryMetrics(
                query_id=run.query_id,
                system=run.system,
                outcome=run.outcome,
                returned=len(run.ranked),
                relevant_in_corpus=relevant,
                judged_pairs=len(rel),
                unjudged_in_top_k=sum(1 for t in run.ranked[:k] if t not in rel),
                precision=precision_at_k(run.ranked, rel, k=k, threshold=threshold)
                if defined
                else None,
                recall=recall_at_k(run.ranked, rel, k=k, threshold=threshold) if defined else None,
                ndcg=ndcg_at_k(run.ranked, rel, k=k) if defined and has_relevant else None,
                reciprocal_rank=reciprocal_rank(run.ranked, rel, threshold=threshold)
                if defined
                else None,
                constraint_satisfied=rate.satisfied if rate else None,
                constraint_unknown=rate.unknown if rate else None,
                skipped=run.skipped,
            )
        )

    summaries: list[SystemSummary] = []
    for system in dict.fromkeys(r.system for r in runs):
        mine = [r for r in rows if r.system == system]
        scored = [r for r in mine if r.skipped is None and r.relevant_in_corpus > 0]
        summaries.append(
            SystemSummary(
                system=system,
                precision=mean([r.precision for r in scored]),
                recall=mean([r.recall for r in scored]),
                ndcg=mean([r.ndcg for r in scored]),
                mrr=mean([r.reciprocal_rank for r in scored]),
                constraint_satisfied=mean([r.constraint_satisfied for r in mine]),
                constraint_unknown=mean([r.constraint_unknown for r in mine]),
                queries=len(mine),
                no_relevant_queries=sorted(
                    r.query_id
                    for r in mine
                    if r.skipped is None and r.judged_pairs and r.relevant_in_corpus == 0
                ),
                skipped_queries=sorted(r.query_id for r in mine if r.skipped is not None),
                no_confident_match=sorted(
                    r.query_id
                    for r in mine
                    if r.outcome == SearchOutcomeKind.NO_CONFIDENT_MATCH.value
                ),
            )
        )
    return rows, summaries
