from __future__ import annotations

from datetime import UTC, datetime

import pytest

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_rules import RuleContext, apply_rule
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.domain.enums import (
    DataSource,
    FeedbackType,
    NextAction,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.errors import (
    QueryNotInSession,
    SessionNotFound,
    TrackNotFound,
    TrackNotInResults,
)
from music_discovery.domain.models import Provenance, SearchSession, SearchTurnRecord, Track
from music_discovery.domain.schemas import (
    FeedbackEvent,
    FieldMatch,
    RankedCandidate,
    RetrievalTrace,
    ScoreBreakdown,
    SearchOutcome,
    SearchSpecification,
)
from music_discovery.retrieval.hybrid_retriever import HybridResult
from tests.fakes import InMemoryTrackRepository

LEXICON = load_lexicon()
CTX = RuleContext(lexicon=LEXICON)
QUERY = QueryAgent(LEXICON)
NOW = datetime(2026, 10, 23, tzinfo=UTC)
CHILL_FLUTE = QUERY.interpret("Something chill with a flute.")
NO_VOCALS = QUERY.interpret("Calm acoustic music without vocals")


def event(event_type: FeedbackType, **kw: object) -> FeedbackEvent:
    data: dict[str, object] = {
        "event_id": f"evt_{event_type.lower()}",
        "search_session_id": "ses_1",
        "query_id": "qry_1",
        "event_type": event_type,
        "timestamp": NOW,
    }
    return FeedbackEvent.model_validate(data | kw)


def apply(
    spec: SearchSpecification, event_type: FeedbackType, **kw: object
) -> tuple[SearchSpecification, str | None, str | None]:
    result = apply_rule(spec, event(event_type, **kw), CTX)
    return result.spec, result.note, result.rejected


def weights(spec: SearchSpecification, field: str) -> dict[str, float]:
    return {p.value: p.weight for p in getattr(spec, field)}


# --- one test per rule ------------------------------------------------------------------


def test_more_like_this_adds_reference() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.MORE_LIKE_THIS, track_id="trk_a")
    assert spec.reference_track_ids == ["trk_a"]
    assert spec.spec_version == CHILL_FLUTE.spec_version + 1
    assert note == "more like trk_a"


def test_more_like_this_undoes_dislike_and_exclusion() -> None:
    base = CHILL_FLUTE.model_copy(
        update={"negative_reference_track_ids": ["trk_a"], "excluded_track_ids": ["trk_a"]}
    )
    spec, _, _ = apply(base, FeedbackType.MORE_LIKE_THIS, track_id="trk_a")
    assert spec.negative_reference_track_ids == spec.excluded_track_ids == []


def test_less_like_this_adds_negative_reference() -> None:
    liked = CHILL_FLUTE.model_copy(update={"reference_track_ids": ["trk_a"]})
    spec, note, _ = apply(liked, FeedbackType.LESS_LIKE_THIS, track_id="trk_a")
    assert spec.negative_reference_track_ids == ["trk_a"]
    assert spec.reference_track_ids == []
    assert note == "less like trk_a"


def test_not_relevant_excludes_track() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.NOT_RELEVANT, track_id="trk_a")
    assert spec.excluded_track_ids == ["trk_a"]
    assert note == "removed trk_a"


def test_wrong_instrument_excludes_track_and_keeps_the_preference() -> None:
    spec, note, _ = apply(
        CHILL_FLUTE,
        FeedbackType.WRONG_INSTRUMENT,
        track_id="trk_a",
        attribute="instrument",
        value="flutes",
    )
    assert spec.excluded_track_ids == ["trk_a"]
    assert weights(spec, "instrument_preferences") == weights(CHILL_FLUTE, "instrument_preferences")
    assert "audio-only matches for flute are trusted less in this session" in spec.uncertainties
    assert spec.spec_version == CHILL_FLUTE.spec_version + 1
    assert note == "removed trk_a (wrong flute)"


def test_more_of_attribute_raises_existing_weight() -> None:
    before = weights(CHILL_FLUTE, "mood_preferences")["chill"]
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.MORE_OF_ATTRIBUTE, attribute="chill")
    assert weights(spec, "mood_preferences")["chill"] == pytest.approx(min(1, before + 0.2))
    assert note is not None
    assert note.startswith("more chill")


def test_more_of_attribute_adds_and_clears_negative() -> None:
    base = QUERY.interpret("chill music, less electronic")
    assert "electronic" in [p.value for p in base.negative_preferences]
    spec, _, _ = apply(base, FeedbackType.MORE_OF_ATTRIBUTE, attribute="electronic")
    assert "electronic" in weights(spec, "genre_preferences")
    assert "electronic" not in [p.value for p in spec.negative_preferences]


def test_more_of_attribute_by_category_and_value() -> None:
    spec, _, _ = apply(
        CHILL_FLUTE, FeedbackType.MORE_OF_ATTRIBUTE, attribute="genre", value="vaporwave"
    )
    assert "vaporwave" in weights(spec, "genre_preferences")


def test_less_of_attribute_lowers_then_negates() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.LESS_OF_ATTRIBUTE, attribute="chill")
    assert weights(spec, "mood_preferences")["chill"] == pytest.approx(0.5)
    assert note == "less chill (0.70 -> 0.50)"
    for _ in range(2):
        spec, _, _ = apply(spec, FeedbackType.LESS_OF_ATTRIBUTE, attribute="chill")
    assert "chill" not in weights(spec, "mood_preferences")
    assert "chill" in [p.value for p in spec.negative_preferences]


def test_less_of_absent_attribute_adds_soft_negative() -> None:
    spec, _, _ = apply(CHILL_FLUTE, FeedbackType.LESS_OF_ATTRIBUTE, attribute="acoustic")
    assert [(p.value, p.weight) for p in spec.negative_preferences] == [("acoustic", 0.6)]
    assert spec.hard_constraints == []


def test_select_track_changes_nothing() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.SELECT_TRACK, track_id="trk_a")
    assert spec is CHILL_FLUTE
    assert note is None


def test_unknown_attribute_is_rejected() -> None:
    spec, _, rejected = apply(CHILL_FLUTE, FeedbackType.MORE_OF_ATTRIBUTE, attribute="zxqv")
    assert spec is CHILL_FLUTE
    assert rejected == "unknown attribute 'zxqv'"


def test_feedback_cannot_contradict_a_hard_constraint() -> None:
    spec, _, rejected = apply(NO_VOCALS, FeedbackType.MORE_OF_ATTRIBUTE, attribute="vocals")
    assert spec is NO_VOCALS
    assert rejected == "vocals are excluded by your request"
    no_drums = QUERY.interpret("ambient without drums")
    _, _, rejected = apply(no_drums, FeedbackType.MORE_OF_ATTRIBUTE, attribute="drums")
    assert rejected == "drums is excluded by your request"


def test_vocal_feedback_is_soft() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.LESS_OF_ATTRIBUTE, attribute="vocals")
    assert spec.vocal_preferences == "avoided"
    assert spec.hard_constraints == []
    assert note == "vocals avoided"


def test_base_example_more_electronic_less_acoustic_keeps_flute_and_chill() -> None:
    spec, _, _ = apply(CHILL_FLUTE, FeedbackType.MORE_OF_ATTRIBUTE, attribute="electronic")
    spec, _, _ = apply(spec, FeedbackType.LESS_OF_ATTRIBUTE, attribute="acoustic")
    assert weights(spec, "genre_preferences")["electronic"] > 0
    assert [p.value for p in spec.negative_preferences] == ["acoustic"]
    assert weights(spec, "mood_preferences") == weights(CHILL_FLUTE, "mood_preferences")
    assert weights(spec, "instrument_preferences") == weights(CHILL_FLUTE, "instrument_preferences")
    assert spec.original_query == CHILL_FLUTE.original_query
    assert spec.hard_constraints == CHILL_FLUTE.hard_constraints
    assert any("electronic" in p for p in spec.semantic_prompts)


# --- Agent C: validation and decisions --------------------------------------------------


TRACK = Track(id="trk_a", provenance=Provenance(source=DataSource.FMA), title="A", genres=["Folk"])
MAP_ONLY = Track(id="trk_map", provenance=Provenance(source=DataSource.FMA), title="M")


def agent() -> FeedbackAgent:
    tracks = InMemoryTrackRepository()
    for t in (TRACK, MAP_ONLY):
        tracks.upsert(t)
    config = DescriptionConfig.load()
    return FeedbackAgent(
        LEXICON, tracks, EvidenceBuilder(config.semantic_bands), DescriptionService(config)
    )


def session(spec: SearchSpecification = CHILL_FLUTE) -> SearchSession:
    turn = SearchTurnRecord(
        query_id="qry_1",
        query_text=spec.original_query,
        spec=spec,
        result_track_ids=["trk_a", "trk_b"],
        created_at=NOW,
    )
    return SearchSession(session_id="ses_1", created_at=NOW).with_turn(turn)


def test_decision_for_a_refinement() -> None:
    decision = agent().apply_feedback(session(), event(FeedbackType.NOT_RELEVANT, track_id="trk_b"))
    assert decision.accepted
    assert decision.next_action is NextAction.REFINE_SEARCH
    assert decision.spec.excluded_track_ids == ["trk_b"]
    assert decision.change_notes == ["removed trk_b"]


def test_repeated_event_is_a_no_op() -> None:
    first = agent().apply_feedback(session(), event(FeedbackType.NOT_RELEVANT, track_id="trk_b"))
    again = agent().apply_feedback(
        session(first.spec), event(FeedbackType.NOT_RELEVANT, track_id="trk_b")
    )
    assert again.accepted
    assert again.spec == first.spec
    assert again.next_action is NextAction.NONE
    assert again.change_notes == []


def test_rejected_decision_keeps_spec() -> None:
    decision = agent().apply_feedback(
        session(NO_VOCALS), event(FeedbackType.MORE_OF_ATTRIBUTE, attribute="vocals")
    )
    assert not decision.accepted
    assert decision.spec == NO_VOCALS
    assert decision.next_action is NextAction.NONE
    assert decision.reason == "vocals are excluded by your request"


def test_select_track_shows_details_even_from_the_map() -> None:
    decision = agent().apply_feedback(
        session(), event(FeedbackType.SELECT_TRACK, track_id="trk_map")
    )
    assert decision.next_action is NextAction.SHOW_DETAILS
    assert decision.spec == CHILL_FLUTE


def test_select_track_of_unknown_track_raises() -> None:
    with pytest.raises(TrackNotFound):
        agent().apply_feedback(session(), event(FeedbackType.SELECT_TRACK, track_id="trk_ghost"))


def test_feedback_on_a_track_not_in_the_results_raises() -> None:
    with pytest.raises(TrackNotInResults):
        agent().apply_feedback(session(), event(FeedbackType.NOT_RELEVANT, track_id="trk_map"))


def test_feedback_on_an_unknown_query_raises() -> None:
    with pytest.raises(QueryNotInSession):
        agent().apply_feedback(
            session(), event(FeedbackType.NOT_RELEVANT, track_id="trk_a", query_id="qry_9")
        )


def test_feedback_for_another_session_raises() -> None:
    with pytest.raises(SessionNotFound):
        agent().apply_feedback(
            session(),
            event(FeedbackType.NOT_RELEVANT, track_id="trk_a", search_session_id="ses_2"),
        )


# --- Agent C: explanations --------------------------------------------------------------


def test_explain_delegates_to_descriptions_and_attaches_evidence() -> None:
    candidate = RankedCandidate(
        track_id="trk_a",
        rank=1,
        score=ScoreBreakdown(metadata=0.9, final=0.9),
        retrieval_sources=[RetrievalSource.METADATA],
    )
    folk = FieldMatch(field="genres", term="folk", source=DataSource.FMA, kind="tag")
    result = HybridResult(
        outcome=SearchOutcome(kind=SearchOutcomeKind.OK, candidates=[candidate]),
        trace=RetrievalTrace(mode="hybrid", degraded=["semantic_unavailable:model_missing"]),
        matched_fields={"trk_a": [folk]},
    )
    [explained] = agent().explain(result)
    assert explained.candidate.evidence is not None
    assert explained.candidate.evidence.uncertainty_flags == ["semantic_unavailable"]
    assert explained.explanation.description == (
        'Listed under "Folk" in FMA. Audio search was unavailable; matched on catalog metadata.'
    )
    assert explained.explanation.generator == "template"


def test_more_instrumental_means_fewer_vocals() -> None:
    spec, note, _ = apply(CHILL_FLUTE, FeedbackType.MORE_OF_ATTRIBUTE, attribute="instrumental")
    assert spec.vocal_preferences == "avoided"
    assert note == "vocals avoided"
    with_vocals = QUERY.interpret("chill songs with vocals only")
    _, _, rejected = apply(with_vocals, FeedbackType.MORE_OF_ATTRIBUTE, attribute="instrumental")
    assert rejected == "vocals are required by your request"
