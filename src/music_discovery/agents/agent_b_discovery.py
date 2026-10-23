"""Agent B — discovery: SearchSpecification -> ranked candidate set + trace (base §7).

A thin coordinator over the hybrid retriever, which alone decides relevance (dedup, hard
constraints and MMR diversity happen there). Agent B adds no scores, writes no descriptions
and uses no LLM. It:

- asks for clarification instead of retrieving when the spec says so;
- fills in deterministic semantic prompts when a spec arrives without them;
- passes `degraded` flags (e.g. `semantic_unavailable`) and NO_CONFIDENT_MATCH through as the
  retriever reported them;
- never returns more than `limit` candidates.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from music_discovery.domain.enums import SearchOutcomeKind
from music_discovery.domain.schemas import RetrievalTrace, SearchOutcome, SearchSpecification
from music_discovery.retrieval.hybrid_retriever import HybridResult, Mode
from music_discovery.retrieval.prompt_builder import build_prompts, with_prompts

MAX_LIMIT = 100


class Retriever(Protocol):
    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Collection[str] | None = None,
    ) -> HybridResult: ...


class DiscoveryAgent:
    def __init__(self, retriever: Retriever, *, corpus: Collection[str] | None = None) -> None:
        """`corpus` restricts every search to a fixed track set (evaluation, small indexes)."""
        self._retriever = retriever
        self._corpus = corpus

    def discover(self, spec: SearchSpecification, limit: int) -> HybridResult:
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        if spec.needs_clarification:
            outcome = SearchOutcome(
                kind=SearchOutcomeKind.NEEDS_CLARIFICATION,
                clarification_question=spec.clarification_question,
            )
            return HybridResult(outcome=outcome, trace=RetrievalTrace(mode="hybrid"))
        if not spec.semantic_prompts and build_prompts(spec):
            spec = with_prompts(spec)
        result = self._retriever.retrieve(spec, mode="hybrid", limit=limit, corpus=self._corpus)
        return _within_limit(result, limit)


def _within_limit(result: HybridResult, limit: int) -> HybridResult:
    candidates = result.outcome.candidates
    if len(candidates) <= limit:
        return result
    kept = candidates[:limit]
    ids = {c.track_id for c in kept}
    return HybridResult(
        outcome=result.outcome.model_copy(update={"candidates": kept}),
        trace=result.trace,
        matched_fields={t: m for t, m in result.matched_fields.items() if t in ids},
        semantic_hits={t: h for t, h in result.semantic_hits.items() if t in ids},
    )
