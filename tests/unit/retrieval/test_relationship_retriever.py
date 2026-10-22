import pytest

from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.models import TrackRelationship
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.retrieval.candidate_merger import Candidate, SignalValue
from music_discovery.retrieval.config import RetrievalConfig, SignalWeights
from music_discovery.retrieval.ranker import rank
from music_discovery.retrieval.relationship_retriever import RelationshipRetriever
from tests.fakes import InMemoryRelationshipRepository


def edge(
    source: str, target: str, kind: RelationshipType, weight: float | None = None
) -> TrackRelationship:
    return TrackRelationship(
        source_track_id=source,
        target_track_id=target,
        relationship_type=kind,
        evidence_source=DataSource.FMA,
        weight=weight,
    )


@pytest.fixture
def retriever() -> RelationshipRetriever:
    repo = InMemoryRelationshipRepository()
    for e in [
        edge("ref", "same_artist", RelationshipType.SAME_ARTIST),
        edge("ref", "same_album", RelationshipType.SAME_RELEASE),
        edge("ref", "styled", RelationshipType.SHARED_STYLE, 0.4),
        edge("ref", "ref2", RelationshipType.SAME_ARTIST),
        edge("ref2", "styled", RelationshipType.SHARED_STYLE, 0.7),
    ]:
        repo.upsert(e)
    return RelationshipRetriever(repo)


def spec(*refs: str) -> SearchSpecification:
    return SearchSpecification(original_query="q", reference_track_ids=list(refs))


def test_no_references_no_signal(retriever: RelationshipRetriever) -> None:
    assert not retriever.available_for(spec())
    assert retriever.retrieve(spec(), 10) == []


def test_scores_neighbors_of_references(retriever: RelationshipRetriever) -> None:
    hits = retriever.retrieve(spec("ref", "ref2"), 10)
    assert [(h.track_id, h.raw) for h in hits] == [
        ("same_album", 1.0),
        ("same_artist", 1.0),
        ("styled", 0.7),
    ]
    assert "ref2" not in {h.track_id for h in hits}, "references are not their own neighbors"
    assert retriever.score(spec("ref"), ["styled", "stranger"]) == {"styled": 0.4, "stranger": 0.0}
    assert [h.track_id for h in retriever.retrieve(spec("ref"), 10, restrict_to=["styled"])] == [
        "styled"
    ]


def test_weight_zero_has_no_effect_and_positive_weight_boosts() -> None:
    norm = {
        "semantic": {"a": 0.6, "b": 0.6},
        "metadata": {"a": 0.6, "b": 0.6},
        "relationship": {"a": 1.0, "b": 0.0},
    }
    cands = [Candidate(t, {"semantic": SignalValue(0.6, 1, "retrieved")}) for t in "ab"]
    signals = {"semantic", "metadata", "relationship"}
    off = rank(cands, norm, RetrievalConfig(weights_version="w"), active=signals, normalization="n")
    assert off[0].relevance == off[1].relevance
    on_config = RetrievalConfig(
        weights_version="w", weights=SignalWeights(semantic=0.5, metadata=0.3, relationship=0.2)
    )
    on = {
        s.candidate.track_id: s.relevance
        for s in rank(cands, norm, on_config, active=signals, normalization="n")
    }
    assert on["a"] > on["b"]
