import numpy as np
import pytest

from music_discovery.domain.errors import EmbeddingVersionMismatch, InvalidEmbedding
from music_discovery.domain.protocols import VectorIndex
from music_discovery.domain.vectors import l2_normalize
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
from tests.fakes import InMemoryEmbeddingStore

RNG = np.random.default_rng(7)
IDS = [f"trk_{i:03d}" for i in range(200)]
MATRIX = l2_normalize(RNG.standard_normal((200, 16)))


@pytest.fixture
def index() -> NumpyCosineIndex:
    return NumpyCosineIndex(IDS, MATRIX, model_id="clap@x", embedding_version="ev-1")


def brute_force(query: np.ndarray, k: int, ids: list[str] = IDS) -> list[str]:
    q = l2_normalize(query)
    scored = sorted(
        ((float(MATRIX[IDS.index(i)] @ q), i) for i in ids), key=lambda p: (-p[0], p[1])
    )
    return [i for _, i in scored[:k]]


def test_conforms_to_protocol(index: NumpyCosineIndex) -> None:
    assert isinstance(index, VectorIndex)
    assert index.size == 200


@pytest.mark.parametrize("k", [1, 5, 50, 200, 500])
def test_top_k_matches_brute_force(index: NumpyCosineIndex, k: int) -> None:
    query = RNG.standard_normal(16)
    results = index.search(query, k)
    assert [r[0] for r in results] == brute_force(query, min(k, 200))
    scores = [r[1] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in scores)


def test_self_query_is_top_one(index: NumpyCosineIndex) -> None:
    track_id, score = index.search(MATRIX[42], 1)[0]
    assert track_id == IDS[42]
    assert score == pytest.approx(1.0, abs=1e-5)


def test_restrict_to(index: NumpyCosineIndex) -> None:
    pool = [*IDS[10:20], "trk_not_indexed"]
    query = RNG.standard_normal(16)
    results = index.search(query, 3, restrict_to=pool)
    assert [r[0] for r in results] == brute_force(query, 3, IDS[10:20])
    assert index.search(query, 3, restrict_to=["trk_not_indexed"]) == []


def test_missing_ids_are_absent_not_zero(index: NumpyCosineIndex) -> None:
    assert index.get("trk_missing") is None
    assert "trk_missing" not in index
    assert "trk_000" in index
    assert all(r[0] != "trk_missing" for r in index.search(RNG.standard_normal(16), 200))


def test_model_mismatch_and_bad_queries(index: NumpyCosineIndex) -> None:
    index.check_model("clap@x")
    with pytest.raises(EmbeddingVersionMismatch):
        index.check_model("clap@y")
    with pytest.raises(InvalidEmbedding):
        index.search(np.zeros(16), 3)
    with pytest.raises(InvalidEmbedding):
        index.search(np.ones(8), 3)
    assert index.search(RNG.standard_normal(16), 0) == []


def test_invalid_construction() -> None:
    with pytest.raises(InvalidEmbedding):
        NumpyCosineIndex(["a", "a"], MATRIX[:2], model_id="m")
    with pytest.raises(InvalidEmbedding):
        NumpyCosineIndex(["a"], MATRIX[:2], model_id="m")
    with pytest.raises(InvalidEmbedding):
        NumpyCosineIndex(["a"], np.ones((1, 16), np.float32), model_id="m")
    assert (
        NumpyCosineIndex([], np.zeros((0, 16), np.float32), model_id="m").search(MATRIX[0], 3) == []
    )


def test_from_store() -> None:
    store = InMemoryEmbeddingStore(
        {"a": MATRIX[0], "b": MATRIX[1]}, model_id="clap@x", embedding_version="ev-9"
    )
    index = NumpyCosineIndex.from_store(store)
    assert index.model_id == "clap@x"
    assert index.embedding_version == "ev-9"
    assert index.search(MATRIX[1], 1)[0][0] == "b"
