"""Property tests for Agent C's rule table (base §8, §18 M4)."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.feedback_rules import RuleContext, apply_rule
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.domain.enums import FeedbackType
from music_discovery.domain.schemas import FeedbackEvent, SearchSpecification

LEXICON = load_lexicon()
CTX = RuleContext(lexicon=LEXICON)
AGENT = QueryAgent(LEXICON)
NOW = datetime(2026, 10, 23, tzinfo=UTC)
QUERIES = [
    "Something chill with a flute.",
    "Calm acoustic music without vocals",
    "Dark electronic music with a heavy bassline, no drums",
    "Upbeat jazz from the 80s under four minutes",
    "only ambient, no rock at all",
]
SPECS = [AGENT.interpret(q) for q in QUERIES]
TRACKS = st.sampled_from(["trk_a", "trk_b", "trk_c", "trk_d"])
TERMS = st.sampled_from(
    ["chill", "electronic", "acoustic", "flute", "drums", "vocals", "dark", "rock", "jazz", "zzz"]
)
TRACK_TYPES = [
    FeedbackType.MORE_LIKE_THIS,
    FeedbackType.LESS_LIKE_THIS,
    FeedbackType.NOT_RELEVANT,
    FeedbackType.SELECT_TRACK,
]
ATTRIBUTE_TYPES = [FeedbackType.MORE_OF_ATTRIBUTE, FeedbackType.LESS_OF_ATTRIBUTE]


@st.composite
def events(draw: st.DrawFn) -> FeedbackEvent:
    kind = draw(st.sampled_from([*TRACK_TYPES, *ATTRIBUTE_TYPES, FeedbackType.WRONG_INSTRUMENT]))
    data: dict[str, object] = {
        "event_id": "evt",
        "search_session_id": "ses",
        "query_id": "qry",
        "event_type": kind,
        "timestamp": NOW,
    }
    if kind in (*TRACK_TYPES, FeedbackType.WRONG_INSTRUMENT):
        data["track_id"] = draw(TRACKS)
    if kind in ATTRIBUTE_TYPES:
        data["attribute"] = draw(TERMS)
    if kind is FeedbackType.WRONG_INSTRUMENT:
        data |= {"attribute": "instrument", "value": draw(st.sampled_from(["flute", "piano"]))}
    return FeedbackEvent.model_validate(data)


def run(spec: SearchSpecification, sequence: list[FeedbackEvent]) -> SearchSpecification:
    for e in sequence:
        spec = apply_rule(spec, e, CTX).spec
    return spec


@settings(max_examples=200, deadline=None)
@given(st.sampled_from(SPECS), st.lists(events(), max_size=12))
def test_original_query_and_hard_constraints_survive_any_feedback(
    spec: SearchSpecification, sequence: list[FeedbackEvent]
) -> None:
    final = run(spec, sequence)
    assert final.original_query == spec.original_query
    assert final.hard_constraints == spec.hard_constraints
    if spec.vocal_preferences in ("required", "excluded"):
        assert final.vocal_preferences == spec.vocal_preferences
    assert SearchSpecification.model_validate(final.model_dump(mode="json")) == final


@settings(max_examples=200, deadline=None)
@given(st.sampled_from(SPECS), st.lists(events(), max_size=8), events())
def test_track_set_rules_are_idempotent(
    spec: SearchSpecification, history: list[FeedbackEvent], e: FeedbackEvent
) -> None:
    if e.event_type not in (*TRACK_TYPES, FeedbackType.WRONG_INSTRUMENT):
        return
    once = apply_rule(run(spec, history), e, CTX).spec
    twice = apply_rule(once, e, CTX)
    assert twice.spec == once
    assert twice.note is None


@settings(max_examples=100, deadline=None)
@given(st.sampled_from(SPECS), st.lists(events(), max_size=12))
def test_spec_version_only_grows(spec: SearchSpecification, sequence: list[FeedbackEvent]) -> None:
    version = spec.spec_version
    for e in sequence:
        result = apply_rule(spec, e, CTX)
        assert result.spec.spec_version == version + (1 if result.note else 0)
        spec, version = result.spec, result.spec.spec_version


@settings(max_examples=100, deadline=None)
@given(st.lists(st.sampled_from(["more electronic", "less acoustic"]), min_size=1, max_size=6))
def test_chill_flute_preferences_survive_electronic_acoustic_feedback(steps: list[str]) -> None:
    spec = SPECS[0]
    for step in steps:
        direction, term = step.split()
        kind = (
            FeedbackType.MORE_OF_ATTRIBUTE
            if direction == "more"
            else FeedbackType.LESS_OF_ATTRIBUTE
        )
        e = FeedbackEvent(
            event_id="e",
            search_session_id="s",
            query_id="q",
            event_type=kind,
            attribute=term,
            timestamp=NOW,
        )
        spec = apply_rule(spec, e, CTX).spec
    assert {p.value for p in spec.mood_preferences} == {"chill"}
    assert {p.value for p in spec.instrument_preferences} == {"flute"}
