from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field

import pytest

from music_discovery.agents.agent_b_discovery import DiscoveryAgent
from music_discovery.domain.enums import DataSource, RetrievalSource, SearchOutcomeKind
from music_discovery.domain.schemas import (
    FieldMatch,
    RankedCandidate,
    RetrievalTrace,
    ScoreBreakdown,
    SearchOutcome,
    SearchSpecification,
    WeightedPreference,
)
from music_discovery.retrieval.hybrid_retriever import HybridResult, Mode

CHILL = SearchSpecification(
    original_query="something chill",
    mood_preferences=[WeightedPreference(value="chill", weight=0.7, source_span="chill")],
    semantic_prompts=["chill music"],
)


def candidate(rank: int) -> RankedCandidate:
    return RankedCandidate(
        track_id=f"trk_{rank:02d}",
        rank=rank,
        score=ScoreBreakdown(metadata=1 - rank / 100, final=1 - rank / 100),
        retrieval_sources=[RetrievalSource.METADATA],
    )


@dataclass
class FakeRetriever:
    outcome: SearchOutcome
    degraded: list[str] = field(default_factory=list)
    calls: list[tuple[SearchSpecification, Mode, int, Collection[str] | None]] = field(
        default_factory=list
    )

    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Collection[str] | None = None,
    ) -> HybridResult:
        self.calls.append((spec, mode, limit, corpus))
        ids = [c.track_id for c in self.outcome.candidates]
        return HybridResult(
            outcome=self.outcome,
            trace=RetrievalTrace(mode=mode, degraded=self.degraded, pool_size=len(ids)),
            matched_fields={
                t: [FieldMatch(field="genres", term="chill", source=DataSource.FMA, kind="tag")]
                for t in ids
            },
        )


def ok(n: int, degraded: list[str] | None = None) -> SearchOutcome:
    return SearchOutcome(
        kind=SearchOutcomeKind.OK,
        candidates=[candidate(i) for i in range(1, n + 1)],
        degraded=degraded or [],
    )


def test_calls_hybrid_mode_with_limit_and_corpus() -> None:
    retriever = FakeRetriever(ok(3))
    result = DiscoveryAgent(retriever, corpus=["trk_01", "trk_02"]).discover(CHILL, 3)
    [(spec, mode, limit, corpus)] = retriever.calls
    assert (spec, mode, limit, corpus) == (CHILL, "hybrid", 3, ["trk_01", "trk_02"])
    assert [c.track_id for c in result.outcome.candidates] == ["trk_01", "trk_02", "trk_03"]


def test_limit_is_honored_even_if_retriever_returns_more() -> None:
    result = DiscoveryAgent(FakeRetriever(ok(10))).discover(CHILL, 4)
    assert [c.rank for c in result.outcome.candidates] == [1, 2, 3, 4]
    assert set(result.matched_fields) == {"trk_01", "trk_02", "trk_03", "trk_04"}


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_limit_is_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        DiscoveryAgent(FakeRetriever(ok(1))).discover(CHILL, limit)


def test_degraded_flags_are_propagated() -> None:
    flags = ["semantic_unavailable:model_missing"]
    result = DiscoveryAgent(FakeRetriever(ok(2, flags), degraded=flags)).discover(CHILL, 5)
    assert result.outcome.degraded == flags
    assert result.trace.degraded == flags


def test_no_confident_match_is_propagated() -> None:
    outcome = SearchOutcome(
        kind=SearchOutcomeKind.NO_CONFIDENT_MATCH, reasons=["vocals excluded: 0 satisfied"]
    )
    result = DiscoveryAgent(FakeRetriever(outcome)).discover(CHILL, 5)
    assert result.outcome == outcome


def test_clarification_skips_retrieval() -> None:
    retriever = FakeRetriever(ok(3))
    spec = SearchSpecification(
        original_query="no vocals with vocals",
        needs_clarification=True,
        clarification_question="Which do you want?",
    )
    result = DiscoveryAgent(retriever).discover(spec, 5)
    assert result.outcome.kind is SearchOutcomeKind.NEEDS_CLARIFICATION
    assert result.outcome.clarification_question == "Which do you want?"
    assert retriever.calls == []


def test_missing_semantic_prompts_are_filled_in_deterministically() -> None:
    retriever = FakeRetriever(ok(1))
    bare = CHILL.model_copy(update={"semantic_prompts": []})
    DiscoveryAgent(retriever).discover(bare, 5)
    [(spec, *_)] = retriever.calls
    assert spec.semantic_prompts
    assert spec.mood_preferences == CHILL.mood_preferences


def test_output_is_deterministic() -> None:
    agent = DiscoveryAgent(FakeRetriever(ok(6)))
    assert agent.discover(CHILL, 5).outcome == agent.discover(CHILL, 5).outcome
