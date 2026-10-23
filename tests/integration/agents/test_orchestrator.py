"""A -> B -> C end to end on a small real index (BM25 + NumPy cosine, fake text encoder)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_b_discovery import DiscoveryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.orchestrator import Orchestrator, SearchTurn
from music_discovery.descriptions.claim_validator import (
    CitedSentence,
    DescriptionConfig,
    split_sentences,
    validate,
)
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.domain.enums import (
    ConstraintStatus,
    DataSource,
    FeedbackType,
    NextAction,
    SearchOutcomeKind,
)
from music_discovery.domain.errors import StaleSessionVersion
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.domain.schemas import FeedbackEvent
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
from tests.fakes import (
    FakeEncoder,
    FrozenClock,
    InMemoryFeedbackRepository,
    InMemorySessionRepository,
    InMemoryTrackRepository,
    SequentialIdGenerator,
    hashed_unit_vector,
)

REPO = Path(__file__).parents[3]
DIM = 32
QUERY = "calm flute melody"
FMA = Provenance(source=DataSource.FMA)
LEXICON = load_lexicon()
CONFIG = DescriptionConfig.load()
LIMIT = 6


def text_vec(text: str) -> np.ndarray:
    return hashed_unit_vector(f"text:{text}", DIM)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    v = (1 - t) * a + t * b
    return (v / np.linalg.norm(v)).astype(np.float32)


def track(tid: str, title: str, genres: list[str], year: int | None = None) -> Track:
    return Track(
        id=tid,
        title=title,
        genres=genres,
        year=year,
        artists=[ArtistReference(artist_id=f"art_{tid}", name=f"Artist {tid}")],
        provenance=FMA,
    )


NIGHT = hashed_unit_vector("night", DIM)
CATALOG = [
    track("trk_sound", "Morning", ["Folk"]),
    track("trk_both", "Flute Garden", ["Folk", "Instrumental"]),
    track("trk_title", "Flute Riot", ["Punk"]),
    track("trk_tape", "Calm Flute Tape", ["Folk"]),  # no embedding
    track("trk_night", "Night Train", ["Electronic"]),
    track("trk_bus", "Night Bus", ["Electronic"]),  # audio neighbour of trk_night
    *[track(f"trk_fill{i}", f"Filler {i}", ["Rock"]) for i in range(6)],
]
VECTORS = {
    "trk_sound": text_vec(QUERY),
    "trk_both": mix(text_vec(QUERY), hashed_unit_vector("noise", DIM), 0.35),
    "trk_title": hashed_unit_vector("noise", DIM),
    "trk_night": NIGHT,
    "trk_bus": mix(NIGHT, hashed_unit_vector("bus", DIM), 0.15),
    **{f"trk_fill{i}": hashed_unit_vector(f"filler{i}", DIM) for i in range(6)},
}


class World:
    def __init__(self, *, semantic: bool = True) -> None:
        self.tracks = InMemoryTrackRepository()
        for t in CATALOG:
            self.tracks.upsert(t)
        index = NumpyCosineIndex(
            list(VECTORS), np.stack(list(VECTORS.values())), model_id="fake-clap-v1"
        )
        docs = {t.id: metadata_document(t, None) for t in CATALOG}
        metadata = MetadataRetriever(
            BM25FieldIndex(docs, field_weights=DEFAULT_FIELD_WEIGHTS),
            {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in CATALOG},
            expand=LEXICON.expand,
        )
        retriever = HybridRetriever(
            RetrievalConfig.load(REPO / "config" / "retrieval.yaml"),
            metadata=metadata,
            semantic=SemanticRetriever(FakeEncoder(dim=DIM), index) if semantic else None,
            tracks=self.tracks,
            index=index,
        )
        self.sessions = InMemorySessionRepository()
        self.events = InMemoryFeedbackRepository()
        self.clock = FrozenClock(datetime(2026, 10, 23, tzinfo=UTC))
        self.orchestrator = Orchestrator(
            QueryAgent(LEXICON),
            DiscoveryAgent(retriever),
            FeedbackAgent(
                LEXICON,
                self.tracks,
                EvidenceBuilder(CONFIG.semantic_bands),
                DescriptionService(CONFIG),
            ),
            self.sessions,
            self.events,
            self.clock,
            SequentialIdGenerator(),
            FeedbackTextNormalizer(LEXICON),
        )

    def feedback(self, turn: SearchTurn, kind: FeedbackType, **kw: object) -> FeedbackEvent:
        assert turn.query_id is not None
        data: dict[str, object] = {
            "event_id": f"evt_{len(self.events.for_session(turn.session.session_id)) + 1}",
            "search_session_id": turn.session.session_id,
            "query_id": turn.query_id,
            "event_type": kind,
            "timestamp": self.clock.now(),
        }
        return FeedbackEvent.model_validate(data | kw)


def ids(turn: SearchTurn) -> list[str]:
    assert turn.outcome is not None
    return [c.track_id for c in turn.outcome.candidates]


def test_query_gives_a_plate_with_grounded_descriptions() -> None:
    world = World()
    turn = world.orchestrator.search(QUERY, None, LIMIT)
    assert turn.outcome is not None
    assert turn.outcome.kind is SearchOutcomeKind.OK
    assert len(ids(turn)) == LIMIT
    assert {"trk_sound", "trk_both"} <= set(ids(turn))
    assert len(turn.explanations) == LIMIT
    for candidate, explanation in zip(turn.outcome.candidates, turn.explanations, strict=True):
        assert explanation.track_id == candidate.track_id
        assert candidate.evidence is not None
        if explanation.description is None:
            continue
        claims = DescriptionService(CONFIG).claims(
            candidate.evidence, world.tracks.get(candidate.track_id)
        )
        by_text = {c.text: c.id for c in claims}
        sentences = split_sentences(explanation.description)
        cited = [CitedSentence(s, (by_text[s],)) for s in sentences]
        assert validate(cited, claims, candidate.evidence, CONFIG).ok
    tape = turn.explanations[ids(turn).index("trk_tape")] if "trk_tape" in ids(turn) else None
    if tape is not None:
        assert tape.description is not None
        assert "Audio analysis unavailable" in tape.description
    stored = world.sessions.get(turn.session.session_id)
    assert stored == turn.session
    assert stored is not None
    assert stored.turns[0].result_track_ids == ids(turn)


def test_not_relevant_track_is_gone_from_the_next_plate() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, LIMIT)
    top = ids(first)[0]
    second = world.orchestrator.refine(
        first.session, world.feedback(first, FeedbackType.NOT_RELEVANT, track_id=top), LIMIT
    )
    assert second.decision is not None
    assert second.decision.next_action is NextAction.REFINE_SEARCH
    assert top not in ids(second)
    assert second.change_summary == [f"removed {top}"]
    stored = world.sessions.get(first.session.session_id)
    assert stored is not None
    assert len(stored.turns) == 2
    assert stored.turns[1].triggered_by_event_id == "evt_1"
    assert [e.event_id for e in world.events.for_session(stored.session_id)] == ["evt_1"]


def test_more_like_this_raises_audio_neighbours() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, len(CATALOG))
    before = ids(first).index("trk_bus")
    second = world.orchestrator.refine(
        first.session,
        world.feedback(first, FeedbackType.MORE_LIKE_THIS, track_id="trk_night"),
        len(CATALOG),
    )
    assert second.spec.reference_track_ids == ["trk_night"]
    assert ids(second).index("trk_bus") < before


def test_constraints_are_preserved_over_three_turns() -> None:
    world = World()
    first = world.orchestrator.search("calm flute music without vocals", None, LIMIT)
    hard = first.spec.hard_constraints
    assert [str(c.attribute) for c in hard] == ["vocals"]
    second = world.orchestrator.refine_text(
        first.session, "more electronic, less acoustic", first.query_id or "", LIMIT
    )
    assert second.query_id is not None
    third = world.orchestrator.refine(
        second.session,
        world.feedback(second, FeedbackType.NOT_RELEVANT, track_id=ids(second)[0]),
        LIMIT,
    )
    for turn in (first, second, third):
        assert turn.spec.original_query == "calm flute music without vocals"
        assert turn.spec.hard_constraints == hard
        assert {p.value for p in turn.spec.instrument_preferences} == {"flute"}
        assert {p.value for p in turn.spec.mood_preferences} == {"calm"}
        assert turn.outcome is not None
        for candidate in turn.outcome.candidates:
            statuses = {r.status for r in candidate.constraint_results}
            assert ConstraintStatus.VIOLATED not in statuses
    assert "electronic" in {p.value for p in third.spec.genre_preferences}
    stored = world.sessions.get(first.session.session_id)
    assert stored is not None
    assert len(stored.turns) == 3
    assert len(stored.feedback_history) == 3, "two text events + one button event"


def test_follow_up_query_reports_what_changed() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, LIMIT)
    second = world.orchestrator.search("but without vocals", first.session, LIMIT)
    assert second.spec.original_query == f"{QUERY}. but without vocals"
    assert "vocals excluded" in second.change_summary
    assert "constraint: vocals excluded" in second.change_summary
    assert len(second.session.turns) == 2


def test_clarification_outcome() -> None:
    world = World()
    turn = world.orchestrator.search("no vocals with female vocals", None, LIMIT)
    assert turn.outcome is not None
    assert turn.outcome.kind is SearchOutcomeKind.NEEDS_CLARIFICATION
    assert turn.outcome.clarification_question
    assert turn.explanations == []


def test_degraded_semantic_still_searches() -> None:
    world = World(semantic=False)
    turn = world.orchestrator.search(QUERY, None, LIMIT)
    assert turn.outcome is not None
    assert turn.outcome.kind is SearchOutcomeKind.OK
    assert "semantic_unavailable" in turn.outcome.degraded
    assert ids(turn)
    assert all(
        e.description is None or "Audio search was unavailable" in e.description
        for e in turn.explanations
    )


def test_no_confident_match_outcome() -> None:
    world = World()
    turn = world.orchestrator.search("only jazz", None, LIMIT)
    assert turn.outcome is not None
    assert turn.outcome.kind is SearchOutcomeKind.NO_CONFIDENT_MATCH
    assert turn.outcome.reasons


def test_select_track_does_not_search_again() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, LIMIT)
    turn = world.orchestrator.refine(
        first.session, world.feedback(first, FeedbackType.SELECT_TRACK, track_id="trk_fill0"), LIMIT
    )
    assert turn.query_id is None
    assert turn.decision is not None
    assert turn.decision.next_action is NextAction.SHOW_DETAILS
    stored = world.sessions.get(first.session.session_id)
    assert stored is not None
    assert len(stored.turns) == 1
    assert len(stored.feedback_history) == 1


def test_unmappable_text_feedback_is_rejected_without_searching() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, LIMIT)
    turn = world.orchestrator.refine_text(
        first.session, "hmm not sure", first.query_id or "", LIMIT
    )
    assert turn.decision is not None
    assert not turn.decision.accepted
    assert turn.query_id is None


def test_stale_session_is_not_overwritten() -> None:
    world = World()
    first = world.orchestrator.search(QUERY, None, LIMIT)
    world.orchestrator.search("more upbeat", first.session, LIMIT)
    with pytest.raises(StaleSessionVersion):
        world.orchestrator.search("more dark", first.session, LIMIT)
