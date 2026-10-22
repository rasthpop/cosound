import numpy as np

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.domain.schemas import ScoreBreakdown
from music_discovery.retrieval.candidate_merger import Candidate
from music_discovery.retrieval.diversity import TrackSimilarity, mmr, mmr_lambda
from music_discovery.retrieval.ranker import Scored
from tests.fakes import BruteForceVectorIndex, hashed_unit_vector

FMA = Provenance(source=DataSource.FMA)


def scored(tid: str, relevance: float) -> Scored:
    return Scored(Candidate(tid), ScoreBreakdown(semantic=relevance, final=relevance), relevance)


def unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


BASE = hashed_unit_vector("base", 16)
OTHER = hashed_unit_vector("other", 16)
VECTORS = {
    "orig": BASE,
    "double_upload": BASE.copy(),  # identical audio
    "near": unit(BASE + 0.15 * OTHER),  # similar, not identical
    "far": OTHER,
}
TRACKS = {
    t: Track(
        id=t,
        title=t,
        artists=[ArtistReference(artist_id="art_x", name="X")],
        release_id="rel_1",
        provenance=FMA,
    )
    for t in ("orig", "double_upload", "near", "far", "same_album_no_audio", "other_album_no_audio")
}
TRACKS["other_album_no_audio"] = TRACKS["other_album_no_audio"].model_copy(
    update={
        "artists": [ArtistReference(artist_id="art_y", name="Y")],
        "release_id": "rel_2",
        "genres": ["Jazz"],
    }
)
SIM = TrackSimilarity(TRACKS, BruteForceVectorIndex(VECTORS), duplicate_cosine=0.9999)


def run(items: list[Scored], k: int, lambda_: float) -> list[str]:
    return [
        s.candidate.track_id
        for s in mmr(
            items, k, lambda_=lambda_, similarity=SIM.similarity, is_duplicate=SIM.is_duplicate
        )
    ]


def test_lambda() -> None:
    assert mmr_lambda(0.0, 0.6) == 1.0
    assert mmr_lambda(0.5, 0.6) == 0.7


def test_lambda_one_is_relevance_order_minus_duplicates() -> None:
    items = [
        scored("orig", 0.9),
        scored("double_upload", 0.89),
        scored("near", 0.8),
        scored("far", 0.5),
    ]
    assert run(items, 4, 1.0) == ["orig", "near", "far"], "the double upload is never shown"


def test_first_pick_is_most_relevant_even_with_high_diversity() -> None:
    items = [scored("near", 0.9), scored("orig", 0.85), scored("far", 0.2)]
    assert run(items, 3, 0.1)[0] == "near"


def test_diversity_promotes_dissimilar_tracks() -> None:
    items = [scored("orig", 0.9), scored("near", 0.85), scored("far", 0.6)]
    assert run(items, 2, 1.0) == ["orig", "near"]
    assert run(items, 2, 0.5) == ["orig", "far"]


def test_same_album_is_not_a_duplicate() -> None:
    assert not SIM.is_duplicate("same_album_no_audio", "orig")
    assert SIM.similarity("same_album_no_audio", "orig") == 1.0, (
        "catalog overlap is high, but only penalized"
    )
    items = [scored("orig", 0.9), scored("same_album_no_audio", 0.8)]
    assert run(items, 2, 0.9) == ["orig", "same_album_no_audio"]


def test_catalog_similarity_fallback() -> None:
    assert SIM.similarity("same_album_no_audio", "other_album_no_audio") == 0.0
    assert SIM.is_duplicate("orig", "double_upload")
    assert not SIM.is_duplicate("orig", "near")


def test_deterministic_ties_and_k() -> None:
    items = [scored("far", 0.5), scored("orig", 0.5)]
    assert run(items, 1, 0.7) == ["far"], "ties keep the incoming (relevance, id) order"
    assert run([], 3, 0.7) == []
    assert len(run([scored("orig", 0.9), scored("far", 0.5), scored("near", 0.4)], 2, 0.7)) == 2
