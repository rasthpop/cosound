"""HybridRetriever over a small catalog with the real BM25 and NumPy cosine indexes."""

from __future__ import annotations

import numpy as np
import pytest

from music_discovery.domain.enums import (
    ConstraintStatus,
    DataSource,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.infrastructure.lexical_index import BM25FieldIndex
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
from music_discovery.retrieval.config import RetrievalConfig
from music_discovery.retrieval.hybrid_retriever import HybridRetriever
from music_discovery.retrieval.metadata_retriever import (
    DEFAULT_FIELD_WEIGHTS,
    MetadataRetriever,
    TrackFacts,
    metadata_document,
)
from music_discovery.retrieval.semantic_retriever import SemanticRetriever
from tests.fakes import FakeEncoder, InMemoryTrackRepository, hashed_unit_vector

DIM = 32
QUERY = "calm flute melody"
FMA = Provenance(source=DataSource.FMA)


def text_vec(text: str) -> np.ndarray:
    return hashed_unit_vector(f"text:{text}", DIM)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    v = (1 - t) * a + t * b
    return (v / np.linalg.norm(v)).astype(np.float32)


def track(tid: str, title: str, genres: list[str], artist: str = "Someone") -> Track:
    return Track(
        id=tid,
        title=title,
        genres=genres,
        artists=[ArtistReference(artist_id=f"art_{artist}", name=artist)],
        provenance=FMA,
    )


NOISE = hashed_unit_vector("noise", DIM)
CATALOG = [
    track("sound_match", "Morning", ["Folk"]),  # sounds like the query, metadata says nothing
    track("double_upload", "Morning (again)", ["Folk"]),  # identical audio to sound_match
    track("both", "Flute Garden", ["Folk", "Instrumental"]),  # metadata + audio
    track("title_only", "Flute Riot", ["Punk"]),  # "flute" only in the title, sounds unrelated
    track("no_audio", "Calm Flute Tape", ["Folk"]),  # metadata only, no embedding
    *[track(f"filler_{i}", f"Filler {i}", ["Rock"]) for i in range(8)],
]
VECTORS = {
    "sound_match": text_vec(QUERY),
    "double_upload": text_vec(QUERY).copy(),
    "both": mix(text_vec(QUERY), NOISE, 0.35),
    "title_only": NOISE,
    **{f"filler_{i}": hashed_unit_vector(f"filler{i}", DIM) for i in range(8)},
}


class Setup:
    def __init__(self, *, semantic: bool = True) -> None:
        self.encoder = FakeEncoder(dim=DIM)
        self.index = NumpyCosineIndex(
            list(VECTORS), np.stack(list(VECTORS.values())), model_id=self.encoder.model_id
        )
        self.repo = InMemoryTrackRepository()
        for t in CATALOG:
            self.repo.upsert(t)
        docs = {t.id: metadata_document(t, None) for t in CATALOG}
        metadata = MetadataRetriever(
            BM25FieldIndex(docs, field_weights=DEFAULT_FIELD_WEIGHTS),
            {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in CATALOG},
        )
        self.retriever = HybridRetriever(
            RetrievalConfig(weights_version="w-test"),
            metadata=metadata,
            semantic=SemanticRetriever(self.encoder, self.index) if semantic else None,
            tracks=self.repo,
            index=self.index,
        )


def spec(**kw: object) -> SearchSpecification:
    return SearchSpecification.model_validate({"original_query": QUERY, "diversity": 0.0, **kw})


PAIR = {"sound_match", "double_upload"}  # identical audio; ties go to the lower id


def ids(result) -> list[str]:  # type: ignore[no-untyped-def]
    return [c.track_id for c in result.outcome.candidates]


def test_three_modes_run_on_the_same_catalog() -> None:
    setup = Setup()
    meta = setup.retriever.retrieve(spec(), mode="metadata_only", limit=5)
    assert setup.encoder.text_calls == [], "metadata_only never touches the encoder"
    assert set(ids(meta)) == {"both", "title_only", "no_audio"}
    sem = setup.retriever.retrieve(spec(), mode="semantic_only", limit=5)
    assert ids(sem)[0] in PAIR
    assert "no_audio" not in ids(sem), "no embedding, no semantic result"
    hybrid = setup.retriever.retrieve(spec(), mode="hybrid", limit=5)
    assert {"both", "no_audio"} <= set(ids(hybrid))
    assert len(PAIR & set(ids(hybrid))) == 1
    for result, mode in ((meta, "metadata_only"), (sem, "semantic_only"), (hybrid, "hybrid")):
        assert result.trace.mode == mode
        assert result.outcome.kind is SearchOutcomeKind.OK


def test_hybrid_backfills_and_keeps_missing_signals_null() -> None:
    result = Setup().retriever.retrieve(spec(), limit=10)
    by_id = {c.track_id: c for c in result.outcome.candidates}
    both = by_id["both"]
    assert set(both.retrieval_sources) == {RetrievalSource.METADATA, RetrievalSource.SEMANTIC}
    assert both.score.semantic is not None
    assert both.score.metadata is not None
    no_audio = by_id["no_audio"]
    assert no_audio.score.semantic is None, "missing audio is null, not zero"
    assert no_audio.score.metadata is not None
    (sound_id,) = PAIR & set(by_id)
    sound = by_id[sound_id]
    assert sound.retrieval_sources == [RetrievalSource.SEMANTIC]
    assert sound.score.metadata == 0.0, "back-filled metadata: evaluated, no match"
    assert result.trace.stage_counts["semantic_backfilled"] >= 1
    assert result.trace.config_versions == {"weights": "w-test"}
    assert sound_id in result.semantic_hits
    assert {m.field for m in result.matched_fields["both"]} >= {"title"}


def test_identical_audio_is_shown_once() -> None:
    plate = ids(Setup().retriever.retrieve(spec(), limit=10))
    assert ("sound_match" in plate) != ("double_upload" in plate)


def test_semantic_unavailable_degrades_to_metadata() -> None:
    result = Setup(semantic=False).retriever.retrieve(spec(), limit=5)
    assert result.outcome.degraded == ["semantic_unavailable"]
    assert result.trace.degraded == ["semantic_unavailable"]
    assert set(ids(result)) == {"both", "title_only", "no_audio"}
    assert all(c.score.semantic is None for c in result.outcome.candidates)


def test_hard_constraint_excludes_top_scoring_violator() -> None:
    constrained = spec(
        hard_constraints=[{"attribute": "genre", "operator": "excluded", "value": "folk"}]
    )
    result = Setup().retriever.retrieve(constrained, limit=10)
    plate = ids(result)
    assert "sound_match" not in plate
    assert "both" not in plate
    assert all(
        r.status is not ConstraintStatus.VIOLATED
        for c in result.outcome.candidates
        for r in c.constraint_results
    )


def test_no_confident_match_is_explicit() -> None:
    impossible = spec(
        hard_constraints=[{"attribute": "genre", "operator": "required", "value": "jazz"}]
    )
    result = Setup().retriever.retrieve(impossible, limit=5)
    assert result.outcome.kind is SearchOutcomeKind.NO_CONFIDENT_MATCH
    assert result.outcome.candidates == []
    assert result.outcome.reasons[0].startswith("genre jazz required: 0 satisfied")


def test_excluded_ids_and_corpus() -> None:
    setup = Setup()
    result = setup.retriever.retrieve(
        spec(excluded_track_ids=["sound_match", "double_upload"]), limit=10
    )
    assert not {"sound_match", "double_upload"} & set(ids(result))
    corpus = ["title_only", "filler_1", "no_audio"]
    assert set(ids(setup.retriever.retrieve(spec(), corpus=corpus, limit=10))) <= set(corpus)


def final_scores(result) -> dict[str, float]:  # type: ignore[no-untyped-def]
    return {c.track_id: c.score.final for c in result.outcome.candidates}


def test_negative_reference_lowers_similar_tracks() -> None:
    setup = Setup()
    base = final_scores(setup.retriever.retrieve(spec(), limit=10))
    penalized = final_scores(
        setup.retriever.retrieve(spec(negative_reference_track_ids=["sound_match"]), limit=10)
    )
    assert penalized["both"] < base["both"], "audio close to a disliked track is pushed down"
    assert penalized["no_audio"] == base["no_audio"], "no audio, no audio-based penalty"


def test_metadata_only_track_can_top_hybrid_unless_coverage_penalty() -> None:
    """Renormalization ranks a no-audio track on metadata alone; gamma > 0 tempers that (P05)."""
    setup = Setup()
    assert ids(setup.retriever.retrieve(spec(), limit=3))[0] == "no_audio"
    setup.retriever._config = setup.retriever._config.model_copy(
        update={"coverage_penalty_gamma": 2.0}
    )
    assert ids(setup.retriever.retrieve(spec(), limit=3))[0] != "no_audio"


def test_deterministic() -> None:
    setup = Setup()
    first = setup.retriever.retrieve(spec(diversity=0.5), limit=6)
    second = setup.retriever.retrieve(spec(diversity=0.5), limit=6)
    assert ids(first) == ids(second)
    assert [c.score for c in first.outcome.candidates] == [
        c.score for c in second.outcome.candidates
    ]
    assert [c.rank for c in first.outcome.candidates] == list(range(1, 7))


@pytest.mark.parametrize("limit", [1, 3])
def test_limit(limit: int) -> None:
    assert len(ids(Setup().retriever.retrieve(spec(), limit=limit))) == limit
