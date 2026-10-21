"""Fakes must satisfy the domain protocols.

The annotated assignments below are checked statically by `make type` (mypy over tests/fakes and
this file); the runtime test covers `runtime_checkable` presence checks and basic behavior.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import BaseModel

from music_discovery.domain import protocols as p
from music_discovery.domain.enums import DataSource, FeedbackType
from music_discovery.domain.errors import StaleSessionVersion
from music_discovery.domain.ids import IdPrefix
from music_discovery.domain.models import Provenance, SearchSession, Track
from music_discovery.domain.schemas import FeedbackEvent
from tests import fakes

NOW = datetime(2026, 1, 1, tzinfo=UTC)
encoder = fakes.FakeEncoder(dim=8)
vectors = {"trk_a": fakes.hashed_unit_vector("a", 8), "trk_b": fakes.hashed_unit_vector("b", 8)}

# Static conformance: mypy checks each assignment against the protocol.
clock: p.Clock = fakes.FrozenClock()
ids: p.IdGenerator = fakes.SequentialIdGenerator()
tracks: p.TrackRepository = fakes.InMemoryTrackRepository()
releases: p.ReleaseRepository = fakes.InMemoryReleaseRepository()
artists: p.ArtistRepository = fakes.InMemoryArtistRepository()
labels: p.LabelRepository = fakes.InMemoryLabelRepository()
audio: p.TrackAudioRepository = fakes.InMemoryTrackAudioRepository()
relationships: p.RelationshipRepository = fakes.InMemoryRelationshipRepository()
matches: p.MatchRepository = fakes.InMemoryMatchRepository()
import_runs: p.ImportRunRepository = fakes.InMemoryImportRunRepository()
sessions: p.SessionRepository = fakes.InMemorySessionRepository()
feedback: p.FeedbackRepository = fakes.InMemoryFeedbackRepository()
uow: p.UnitOfWork = fakes.InMemoryUnitOfWork()
text_encoder: p.TextEncoder = encoder
audio_encoder: p.AudioEncoder = encoder
store: p.EmbeddingStore = fakes.InMemoryEmbeddingStore(vectors)
index: p.VectorIndex = fakes.BruteForceVectorIndex(vectors)
lexical: p.LexicalIndex = fakes.FakeLexicalIndex({"trk_a": "flute"})
probe: p.AudioProbe = fakes.FakeAudioProbe()
llm: p.StructuredLLM = fakes.FakeStructuredLLM()
spatial: p.SpatialRepository = fakes.InMemorySpatialRepository({"trk_a": (0.0, 1.0)})

CONFORMING: list[tuple[Any, object]] = [
    (p.Clock, clock),
    (p.IdGenerator, ids),
    (p.TrackRepository, tracks),
    (p.ReleaseRepository, releases),
    (p.ArtistRepository, artists),
    (p.LabelRepository, labels),
    (p.TrackAudioRepository, audio),
    (p.RelationshipRepository, relationships),
    (p.MatchRepository, matches),
    (p.ImportRunRepository, import_runs),
    (p.SessionRepository, sessions),
    (p.FeedbackRepository, feedback),
    (p.UnitOfWork, uow),
    (p.TextEncoder, text_encoder),
    (p.AudioEncoder, audio_encoder),
    (p.EmbeddingStore, store),
    (p.VectorIndex, index),
    (p.LexicalIndex, lexical),
    (p.AudioProbe, probe),
    (p.StructuredLLM, llm),
    (p.SpatialRepository, spatial),
]


def test_every_protocol_has_a_conforming_fake() -> None:
    protocol_names = {
        name
        for name, obj in vars(p).items()
        if isinstance(obj, type)
        and getattr(obj, "_is_protocol", False)
        and obj.__module__ == p.__name__
    }
    covered = {protocol.__name__ for protocol, _ in CONFORMING}
    assert protocol_names == covered
    for protocol, instance in CONFORMING:
        assert isinstance(instance, protocol), protocol.__name__


def test_fake_encoder_is_deterministic_and_normalized() -> None:
    a = encoder.encode_texts(["chill flute", "heavy drums"])
    b = encoder.encode_texts(["chill flute", "heavy drums"])
    assert a.shape == (2, 8)
    assert a.dtype == np.float32
    np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(np.linalg.norm(a, axis=1), 1.0, rtol=1e-5)
    assert not np.allclose(a[0], a[1])
    assert encoder.encode_audio([Path("x/000002.mp3")]).shape == (1, 8)
    assert encoder.encode_texts([]).shape == (0, 8)


def test_vector_index_orders_by_cosine_and_restricts() -> None:
    query = vectors["trk_a"]
    results = index.search(query, k=2)
    assert results[0][0] == "trk_a"
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)
    assert index.search(query, k=5, restrict_to={"trk_b"}) == [results[1]]
    assert "trk_a" in index
    assert "trk_missing" not in index
    assert index.get("trk_missing") is None


def test_lexical_and_probe_and_spatial_fakes() -> None:
    assert lexical.search(["Flute"], k=3) == [("trk_a", 1.0)]
    assert lexical.search(["drums"], k=3) == []
    failing = fakes.FakeAudioProbe(failures={"bad.mp3": "decode_error"})
    assert failing.probe(Path("bad.mp3")).error_code == "decode_error"
    assert failing.probe(Path("good.mp3")).ok
    assert spatial.coordinates("trk_a") == (0.0, 1.0)
    assert spatial.coordinates("trk_b") is None


class Draft(BaseModel):
    mood: str


class Other(BaseModel):
    x: int


def test_fake_llm_replays_responses() -> None:
    fake = fakes.FakeStructuredLLM([Draft(mood="chill"), "rate_limited", Other(x=1)])
    ok = fake.generate(task="query", system="s", user="u", schema=Draft)
    assert ok.parsed == Draft(mood="chill")
    assert (
        fake.generate(task="query", system="s", user="u", schema=Draft).error_code == "rate_limited"
    )
    wrong = fake.generate(task="query", system="s", user="u", schema=Draft)
    assert wrong.error_code == "invalid_output"
    assert (
        fake.generate(task="query", system="s", user="u", schema=Draft).error_code == "unavailable"
    )
    assert [c.task for c in fake.calls] == ["query"] * 4


def test_fake_session_repository_enforces_versions() -> None:
    repo = fakes.InMemorySessionRepository()
    session = SearchSession(session_id="ses_1", created_at=NOW)
    repo.save(session, expected_version=None)
    with pytest.raises(StaleSessionVersion):
        repo.save(session, expected_version=None)
    updated = session.model_copy(update={"version": 1})
    repo.save(updated, expected_version=0)
    with pytest.raises(StaleSessionVersion):
        repo.save(updated.model_copy(update={"version": 2}), expected_version=0)


def test_fake_unit_of_work_rolls_back() -> None:
    repo = fakes.InMemoryTrackRepository()
    events = fakes.InMemoryFeedbackRepository()
    work = fakes.InMemoryUnitOfWork(repo, events)
    track = Track(id="trk_1", title="T", provenance=Provenance(source=DataSource.FMA))

    def write_then_fail() -> None:
        with work.transaction():
            repo.upsert(track)
            events.add(
                FeedbackEvent(
                    event_id="evt_1",
                    search_session_id="ses_1",
                    query_id="qry_1",
                    track_id="trk_1",
                    event_type=FeedbackType.SELECT_TRACK,
                    timestamp=NOW,
                )
            )
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        write_then_fail()
    assert repo.get("trk_1") is None
    assert events.for_session("ses_1") == []
    with work.transaction():
        repo.upsert(track)
    assert repo.get("trk_1") == track


def test_id_generator_and_clock_match_protocol_usage() -> None:
    gen = fakes.SequentialIdGenerator()
    assert gen.new(IdPrefix.SESSION) == "ses_000001"
    c = fakes.FrozenClock(NOW)
    c.sleep(2)
    assert (c.now() - NOW).total_seconds() == 2
