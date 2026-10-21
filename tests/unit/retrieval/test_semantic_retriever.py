from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from music_discovery.domain.errors import ModelLoadError
from music_discovery.domain.protocols import Matrix
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.retrieval.semantic_retriever import SemanticConfig, SemanticRetriever
from tests.fakes import BruteForceVectorIndex, FakeEncoder, hashed_unit_vector

DIM = 32
QUERY = "Something chill with a flute"
EXPANSION = "chill music featuring flute"


def text_vec(text: str) -> np.ndarray:
    """The vector FakeEncoder produces for a text."""
    return hashed_unit_vector(f"text:{text}", DIM)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    v = (1 - t) * a + t * b
    return (v / np.linalg.norm(v)).astype(np.float32)


VECTORS = {
    "trk_exact": text_vec(QUERY),  # matches the original request
    "trk_expansion": text_vec(EXPANSION),  # matches only the expansion
    "trk_near": mix(text_vec(QUERY), hashed_unit_vector("other", DIM), 0.3),
    **{f"trk_rand_{i}": hashed_unit_vector(f"rand{i}", DIM) for i in range(20)},
}


def spec(**kw: object) -> SearchSpecification:
    return SearchSpecification.model_validate({"original_query": QUERY, **kw})


def retriever(config: SemanticConfig | None = None) -> SemanticRetriever:
    return SemanticRetriever(FakeEncoder(dim=DIM), BruteForceVectorIndex(VECTORS), config)


def test_ranks_by_cosine_with_the_request() -> None:
    result = retriever().retrieve(spec(), k=3)
    assert result.status == "available"
    assert result.model_id == "fake-clap-v1"
    assert [h.track_id for h in result.hits[:2]] == ["trk_exact", "trk_near"]
    top = result.hits[0]
    assert top.rank == 1
    assert top.raw_cosine == pytest.approx(1.0, abs=1e-5)
    assert top.best_query.kind == "original"
    assert [h.rank for h in result.hits] == [1, 2, 3]


def test_expansion_cannot_outweigh_original_by_default() -> None:
    result = retriever().retrieve(spec(semantic_prompts=[EXPANSION]))
    scores = {h.track_id: h for h in result.hits}
    assert scores["trk_exact"].score == pytest.approx(1.0, abs=1e-5)
    assert scores["trk_expansion"].score == pytest.approx(0.8, abs=1e-5)
    assert scores["trk_expansion"].raw_cosine == pytest.approx(1.0, abs=1e-5)
    assert scores["trk_expansion"].best_query.kind == "expansion"
    order = [h.track_id for h in result.hits]
    assert order.index("trk_exact") < order.index("trk_expansion")


def test_expansions_are_capped() -> None:
    prompts = [f"prompt {i}" for i in range(4)]
    result = retriever(SemanticConfig(max_expansions=2)).retrieve(spec(semantic_prompts=prompts))
    assert [q.kind for q in result.queries] == ["original", "expansion", "expansion"]


def test_reference_track_audio_steers_results() -> None:
    result = retriever().retrieve(
        spec(reference_track_ids=["trk_rand_7", "trk_without_audio"]), k=1
    )
    assert result.hits[0].track_id == "trk_rand_7"
    assert result.hits[0].best_query.kind == "reference"
    assert [q.reference_track_id for q in result.queries if q.kind == "reference"] == ["trk_rand_7"]


def test_tracks_without_embeddings_are_absent_not_zero() -> None:
    result = retriever().retrieve(spec(), k=100, restrict_to=["trk_exact", "trk_no_audio"])
    assert [h.track_id for h in result.hits] == ["trk_exact"]
    assert result.score_of("trk_no_audio") is None


def test_restrict_to_scores_exactly_the_pool() -> None:
    pool = ["trk_rand_1", "trk_rand_2", "trk_rand_3"]
    result = retriever().retrieve(spec(), restrict_to=pool)
    assert sorted(h.track_id for h in result.hits) == sorted(pool)


def test_unavailable_paths() -> None:
    for r in (
        SemanticRetriever(None, BruteForceVectorIndex(VECTORS)),
        SemanticRetriever(FakeEncoder(dim=DIM), None),
    ):
        result = r.retrieve(spec())
        assert result.status == "unavailable"
        assert result.hits == []
        assert result.reason == "semantic_unavailable"
        assert not r.available


def test_model_mismatch_is_unavailable() -> None:
    r = SemanticRetriever(FakeEncoder(dim=DIM, model_id="other"), BruteForceVectorIndex(VECTORS))
    result = r.retrieve(spec())
    assert (result.status, result.reason) == ("unavailable", "embedding_version_mismatch")


class BrokenEncoder(FakeEncoder):
    def encode_texts(self, texts: Sequence[str]) -> Matrix:
        raise ModelLoadError("checkpoint missing")


def test_encoder_failure_degrades_instead_of_raising() -> None:
    result = SemanticRetriever(BrokenEncoder(dim=DIM), BruteForceVectorIndex(VECTORS)).retrieve(
        spec()
    )
    assert (result.status, result.reason) == ("unavailable", "model_load_error")


def test_deterministic_ties() -> None:
    twins = {"trk_b": text_vec(QUERY), "trk_a": text_vec(QUERY)}
    result = SemanticRetriever(FakeEncoder(dim=DIM), BruteForceVectorIndex(twins)).retrieve(spec())
    assert [h.track_id for h in result.hits] == ["trk_a", "trk_b"]
