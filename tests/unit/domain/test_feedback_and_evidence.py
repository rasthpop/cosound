import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from music_discovery.domain.enums import (
    ConstraintStatus,
    DataSource,
    FeedbackType,
    MatchStrength,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.schemas import (
    AudioProbeResult,
    ConstraintResult,
    FeedbackEvent,
    FieldMatch,
    HardConstraint,
    LLMResult,
    RankedCandidate,
    RetrievalTrace,
    ScoreBreakdown,
    SearchOutcome,
    SearchSpecification,
    SemanticEvidence,
    SourceScore,
    TagMatch,
    TrackEvidence,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SPEC = SearchSpecification(original_query="Something chill with a flute")


def event(**overrides: Any) -> FeedbackEvent:
    values: dict[str, Any] = {
        "event_id": "evt_1",
        "search_session_id": "ses_1",
        "query_id": "qry_1",
        "track_id": "trk_1",
        "event_type": FeedbackType.MORE_LIKE_THIS,
        "timestamp": NOW,
    }
    values.update(overrides)
    return FeedbackEvent.model_validate(values)


# --- Feedback ---------------------------------------------------------------


def test_feedback_event_roundtrip_and_wire_values() -> None:
    e = event(event_type="MORE_OF_ATTRIBUTE", attribute="electronic", value=True)
    dumped = e.model_dump(mode="json")
    assert dumped["event_type"] == "MORE_OF_ATTRIBUTE"
    assert FeedbackEvent.model_validate(dumped) == e


@pytest.mark.parametrize(
    "overrides",
    [
        {"track_id": None},
        {"event_type": FeedbackType.WRONG_INSTRUMENT},
        {"event_type": FeedbackType.MORE_OF_ATTRIBUTE, "track_id": None},
        {"event_type": "LIKE"},
        {"timestamp": datetime(2026, 1, 1)},
    ],
)
def test_feedback_event_rejects_incomplete_events(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        event(**overrides)


def test_attribute_feedback_without_track_is_allowed() -> None:
    e = event(event_type=FeedbackType.LESS_OF_ATTRIBUTE, track_id=None, attribute="acoustic")
    assert e.track_id is None


# --- Scores: missing is never zero ------------------------------------------------


def test_missing_semantic_score_serializes_as_null() -> None:
    score = ScoreBreakdown(metadata=0.8, final=0.8)
    dumped = score.model_dump(mode="json")
    assert dumped["semantic"] is None
    assert dumped["relationship"] is None
    assert '"semantic":null' in score.model_dump_json()
    assert ScoreBreakdown.model_validate(dumped).semantic is None


def test_zero_semantic_score_stays_zero() -> None:
    score = ScoreBreakdown(semantic=0.0, metadata=0.5, final=0.25)
    assert score.model_dump(mode="json")["semantic"] == 0.0


def test_score_needs_at_least_one_signal_and_bounds() -> None:
    with pytest.raises(ValidationError):
        ScoreBreakdown(final=0.5)
    with pytest.raises(ValidationError):
        ScoreBreakdown(semantic=1.2, final=0.5)


def test_semantic_evidence_is_a_similarity() -> None:
    ev = SemanticEvidence(
        prompt="chill flute",
        raw_cosine=0.31,
        normalized=None,
        rank=1,
        model_id="clap",
        strength=MatchStrength.STRONG,
    )
    assert ev.model_dump(mode="json")["normalized"] is None
    with pytest.raises(ValidationError):
        SemanticEvidence(
            prompt="x", raw_cosine=1.5, rank=1, model_id="clap", strength=MatchStrength.WEAK
        )


# --- Candidates & outcomes ----------------------------------------------------------


def candidate(track_id: str = "trk_1", rank: int = 1, **overrides: Any) -> RankedCandidate:
    values: dict[str, Any] = {
        "track_id": track_id,
        "rank": rank,
        "score": ScoreBreakdown(semantic=0.9, final=0.9),
        "retrieval_sources": [RetrievalSource.SEMANTIC],
        "source_scores": {RetrievalSource.SEMANTIC: SourceScore(raw_score=0.31, rank=1)},
    }
    values.update(overrides)
    return RankedCandidate.model_validate(values)


def test_ranked_candidate_with_evidence_roundtrip() -> None:
    evidence = TrackEvidence(
        track_id="trk_1",
        metadata_matches=[
            FieldMatch(field="title", term="flute", source=DataSource.FMA, kind="lexical")
        ],
        genre_matches=[TagMatch(tag="Folk", source=DataSource.FMA)],
        retrieval_sources=[RetrievalSource.SEMANTIC],
        constraint_results=[
            ConstraintResult(
                constraint=HardConstraint(attribute="vocals", operator="excluded"),
                status=ConstraintStatus.UNKNOWN,
            )
        ],
        uncertainty_flags=["constraint_unknown:vocals"],
    )
    c = candidate(evidence=evidence)
    assert RankedCandidate.model_validate(json.loads(c.model_dump_json())) == c
    assert c.model_dump(mode="json")["evidence"]["semantic"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"retrieval_sources": []},
        {"source_scores": {RetrievalSource.METADATA: SourceScore(raw_score=1.0, rank=1)}},
        {"evidence": TrackEvidence(track_id="trk_other")},
        {"rank": 0},
    ],
)
def test_ranked_candidate_rejects_inconsistencies(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        candidate(**overrides)


def test_search_outcome_rules() -> None:
    ok = SearchOutcome(kind=SearchOutcomeKind.OK, candidates=[candidate(), candidate("trk_2", 2)])
    assert len(ok.candidates) == 2
    none = SearchOutcome(kind=SearchOutcomeKind.NO_CONFIDENT_MATCH, reasons=["vocals: excluded"])
    assert none.candidates == []
    with pytest.raises(ValidationError):
        SearchOutcome(kind=SearchOutcomeKind.NO_CONFIDENT_MATCH)
    with pytest.raises(ValidationError):
        SearchOutcome(
            kind=SearchOutcomeKind.NO_CONFIDENT_MATCH, candidates=[candidate()], reasons=["x"]
        )
    with pytest.raises(ValidationError):
        SearchOutcome(kind=SearchOutcomeKind.NEEDS_CLARIFICATION)
    with pytest.raises(ValidationError):
        SearchOutcome(kind=SearchOutcomeKind.OK, candidates=[candidate("trk_1", 2)])


def test_retrieval_trace_defaults() -> None:
    trace = RetrievalTrace(mode="hybrid", degraded=["semantic_unavailable"])
    assert trace.model_dump(mode="json")["model_id"] is None


# --- Adapter results -----------------------------------------------------------------


class Draft(BaseModel):
    mood: str


def test_llm_result_parsed_or_error() -> None:
    ok = LLMResult[Draft](parsed=Draft(mood="chill"), model_id="vendor/model:free")
    assert ok.parsed is not None
    failed = LLMResult[Draft](error_code="invalid_output", raw_text="not json")
    assert failed.parsed is None
    with pytest.raises(ValidationError):
        LLMResult[Draft]()
    with pytest.raises(ValidationError):
        LLMResult[Draft](parsed=Draft(mood="x"), error_code="rate_limited")


def test_audio_probe_result() -> None:
    assert AudioProbeResult(ok=True, duration_seconds=30.0, sample_rate=44100).ok
    with pytest.raises(ValidationError):
        AudioProbeResult(ok=False)
    with pytest.raises(ValidationError):
        AudioProbeResult(ok=True, error_code="decode_error")


# --- Session ------------------------------------------------------------------------


def turn(query_id: str = "qry_1", spec: SearchSpecification = SPEC) -> SearchTurnRecord:
    return SearchTurnRecord(
        query_id=query_id,
        query_text=spec.original_query,
        spec=spec,
        result_track_ids=["trk_1", "trk_2"],
        created_at=NOW,
    )


def test_session_turns_and_history() -> None:
    session = SearchSession(session_id="ses_1", created_at=NOW)
    assert session.current_spec is None
    refined = SPEC.model_copy(update={"spec_version": 2, "excluded_track_ids": ["trk_2"]})
    s1 = session.with_turn(turn())
    s2 = s1.with_feedback(event()).with_turn(turn("qry_2", refined))
    assert s2.version == 3
    assert s2.current_spec == refined
    assert s2.spec_history == [SPEC, refined]
    assert s2.original_query == SPEC.original_query
    assert s2.turn("qry_1") is not None
    assert session.version == 0, "updates must not mutate the previous version"
    assert SearchSession.model_validate(s2.model_dump(mode="json")) == s2


def test_session_rejects_foreign_feedback_and_duplicate_queries() -> None:
    s = SearchSession(session_id="ses_1", created_at=NOW).with_turn(turn())
    with pytest.raises(ValueError, match="different session"):
        s.with_feedback(event(search_session_id="ses_2"))
    with pytest.raises(ValueError, match="already in the session"):
        s.with_turn(turn())
