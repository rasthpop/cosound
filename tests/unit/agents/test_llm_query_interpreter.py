from __future__ import annotations

from datetime import UTC, datetime

import pytest

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.llm_query_interpreter import (
    DraftConstraint,
    DraftNegative,
    DraftPreference,
    LLMQueryInterpreter,
    SearchSpecificationDraft,
    load_prompt,
)
from music_discovery.agents.query_parser import QueryParser
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.schemas import SearchSpecification
from tests.fakes import FakeStructuredLLM

LEXICON = load_lexicon()
PARSER = QueryParser(LEXICON)
MODEL = "vendor/model:free"
CHILL_FLUTE = "Something chill with a flute."


def draft(**overrides: object) -> SearchSpecificationDraft:
    data: dict[str, object] = {
        "preferences": [
            DraftPreference(category="mood", value="chill", weight=0.7, source_span="chill"),
            DraftPreference(category="instrument", value="flute", weight=0.9, source_span="flute"),
        ],
        "negative_preferences": [],
        "vocals": "unspecified",
        "hard_constraints": [],
        "reference_track_ids": [],
        "semantic_prompts": [],
        "needs_clarification": False,
        "clarification_question": None,
    }
    return SearchSpecificationDraft.model_validate(data | overrides)


def interpret(
    response: SearchSpecificationDraft | str, query: str = CHILL_FLUTE, known: tuple[str, ...] = ()
) -> tuple[SearchSpecification | None, str | None, FakeStructuredLLM]:
    llm = FakeStructuredLLM([response], model_id=MODEL)
    outcome = LLMQueryInterpreter(llm, LEXICON).interpret(query, known_track_ids=known)
    return outcome.spec, outcome.fallback_reason, llm


def agent(*responses: SearchSpecificationDraft | str) -> QueryAgent:
    llm = FakeStructuredLLM(list(responses), model_id=MODEL)
    return QueryAgent(LEXICON, LLMQueryInterpreter(llm, LEXICON))


# --- accepted ---------------------------------------------------------------------------


def test_valid_output_is_accepted_and_recorded() -> None:
    spec, reason, _ = interpret(draft())
    assert reason is None
    assert spec is not None
    assert spec.interpreter == "llm"
    assert spec.interpreter_model == MODEL
    assert [(p.value, p.weight) for p in spec.instrument_preferences] == [("flute", 0.9)]
    assert spec.hard_constraints == []
    assert spec.semantic_prompts, "prompts are rebuilt from the accepted spec"


def test_synonyms_are_normalized_to_lexicon_terms_and_categories() -> None:
    prefs = [
        DraftPreference(category="mood", value="Laid-back", weight=0.7, source_span="laid back"),
        DraftPreference(category="genre", value="flutes", weight=0.8, source_span="flutes"),
    ]
    spec, reason, _ = interpret(draft(preferences=prefs))
    assert reason is None
    assert spec is not None
    assert [p.value for p in spec.mood_preferences] == ["relaxed"]
    assert [p.value for p in spec.instrument_preferences] == ["flute"]
    assert spec.genre_preferences == []


def test_unknown_values_are_dropped_with_a_note() -> None:
    prefs = [DraftPreference(category="genre", value="Aphex Twin", weight=0.9, source_span="x")]
    spec, reason, _ = interpret(draft(preferences=prefs))
    assert reason is None
    assert spec is not None
    assert spec.genre_preferences == []
    assert any("Aphex Twin" in note for note in spec.uncertainties)


def test_backed_hard_constraint_is_accepted() -> None:
    query = "Calm acoustic music without vocals"
    response = draft(
        preferences=[
            DraftPreference(category="mood", value="calm", weight=0.7, source_span="calm")
        ],
        vocals="excluded",
        hard_constraints=[
            DraftConstraint(
                attribute="vocals",
                operator="excluded",
                value=None,
                low=None,
                high=None,
                cue="without",
            )
        ],
    )
    spec, reason, _ = interpret(response, query)
    assert reason is None
    assert spec is not None
    assert spec.vocal_preferences == "excluded"
    assert spec.hard_constraints == PARSER.parse(query).hard_constraints


def test_only_the_query_text_is_sent() -> None:
    _, _, llm = interpret(draft())
    [call] = llm.calls
    assert call.user == CHILL_FLUTE
    assert call.task == "query"
    assert "flute" in call.system, "lexicon vocabulary is part of the system prompt"
    assert "{{vocabulary}}" not in call.system


def test_prompt_is_versioned() -> None:
    assert load_prompt().version == "query-v2"


# --- rejected ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["invalid_output", "rate_limited", "timeout", "circuit_open"])
def test_adapter_errors_are_rejected_with_reason(code: str) -> None:
    spec, reason, _ = interpret(code)
    assert spec is None
    assert reason == f"llm_{code}"


def test_hallucinated_track_ids_are_rejected() -> None:
    spec, reason, _ = interpret(draft(reference_track_ids=["trk_made_up"]))
    assert spec is None
    assert reason == "hallucinated_track_ids"


def test_track_ids_from_the_session_are_allowed() -> None:
    spec, reason, _ = interpret(draft(reference_track_ids=["trk_a"]), known=("trk_a",))
    assert reason is None
    assert spec is not None
    assert spec.reference_track_ids == [], "references are carried by Agent A, not the LLM"


def test_soft_to_hard_escalation_is_rejected() -> None:
    flute_required = DraftConstraint(
        attribute="instrument", operator="required", value="flute", low=None, high=None, cue="with"
    )
    spec, reason, _ = interpret(draft(hard_constraints=[flute_required]))
    assert spec is None
    assert reason == "soft_to_hard_escalation"


def test_soft_vocals_escalated_to_excluded_is_rejected() -> None:
    spec, reason, _ = interpret(draft(vocals="excluded"), "Relaxed piano, mostly instrumental")
    assert spec is None
    assert reason == "soft_to_hard_escalation"


def test_value_both_preferred_and_negative_is_rejected() -> None:
    negatives = [DraftNegative(value="chill", weight=0.6, source_span="chill")]
    spec, reason, _ = interpret(draft(negative_preferences=negatives))
    assert spec is None
    assert reason == "inconsistent_output"


def test_preferring_a_hard_excluded_instrument_is_rejected() -> None:
    query = "Ambient music without drums"
    prefs = [DraftPreference(category="instrument", value="drums", weight=0.7, source_span="drums")]
    drums = DraftConstraint(
        attribute="instrument",
        operator="excluded",
        value="drum",
        low=None,
        high=None,
        cue="without",
    )
    spec, reason, _ = interpret(draft(preferences=prefs, hard_constraints=[drums]), query)
    assert spec is None
    assert reason == "inconsistent_output"


# --- Agent A integration ----------------------------------------------------------------


def test_agent_uses_llm_reading_when_accepted() -> None:
    result = agent(draft()).interpret_traced(CHILL_FLUTE)
    assert result.llm_fallback_reason is None
    assert result.spec.interpreter == "llm"


def test_agent_falls_back_to_parser_with_reason() -> None:
    result = agent("invalid_output").interpret_traced(CHILL_FLUTE)
    assert result.llm_fallback_reason == "llm_invalid_output"
    assert result.spec == PARSER.parse(CHILL_FLUTE)
    assert result.spec.interpreter == "deterministic"


def test_llm_reads_first_even_when_the_parser_would_ask_to_clarify() -> None:
    query = "no vocals with female vocals"
    llm = FakeStructuredLLM(
        [draft(needs_clarification=True, clarification_question="With or without vocals?")],
        model_id=MODEL,
    )
    spec = QueryAgent(LEXICON, LLMQueryInterpreter(llm, LEXICON)).interpret(query)
    assert len(llm.calls) == 1
    assert spec.needs_clarification
    assert spec.clarification_question == "With or without vocals?"
    assert spec.interpreter == "llm"


def test_parser_does_not_run_when_the_llm_answer_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: object) -> None:
        raise AssertionError("the parser is the fallback only")

    monkeypatch.setattr(QueryParser, "parse", fail)
    assert agent(draft()).interpret(CHILL_FLUTE).interpreter == "llm"


def test_empty_query_raises_without_a_call() -> None:
    llm = FakeStructuredLLM([draft()], model_id=MODEL)
    with pytest.raises(ValueError, match="empty"):
        QueryAgent(LEXICON, LLMQueryInterpreter(llm, LEXICON)).interpret("   ")
    assert llm.calls == []


@pytest.mark.parametrize(
    "code", ["invalid_output", "truncated_output", "timeout", "rate_limited", "quota_exhausted"]
)
def test_each_failure_falls_back_to_the_parser_with_the_reason(code: str) -> None:
    result = agent(code).interpret_traced(CHILL_FLUTE)
    assert result.llm_fallback_reason == f"llm_{code}"
    assert result.spec == PARSER.parse(CHILL_FLUTE)


def test_agent_follow_up_keeps_llm_provenance() -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    first = PARSER.parse("Calm piano music")
    turn = SearchTurnRecord(
        query_id="q1", query_text="Calm piano music", spec=first, created_at=now
    )
    state = SearchSession(session_id="s", created_at=now).with_turn(turn)
    upbeat = draft(
        preferences=[
            DraftPreference(category="mood", value="upbeat", weight=0.8, source_span="upbeat")
        ]
    )
    spec = agent(upbeat).interpret("more upbeat", state)
    assert spec.interpreter == "llm"
    assert spec.interpreter_model == MODEL
    assert sorted(p.value for p in spec.mood_preferences) == ["calm", "upbeat"]


def test_agent_without_llm_is_deterministic() -> None:
    spec = QueryAgent(LEXICON).interpret(CHILL_FLUTE)
    assert spec.interpreter == "deterministic"
    assert spec.interpreter_model is None


# --- the LLM reads wording the parser cannot (ADR-0007) -----------------------------------


def hard(attribute: str, operator: str, cue: str, **extra: object) -> DraftConstraint:
    fields: dict[str, object] = {"value": None, "low": None, "high": None} | extra
    return DraftConstraint.model_validate(
        {"attribute": attribute, "operator": operator, "cue": cue} | fields
    )


def no_prefs(**overrides: object) -> SearchSpecificationDraft:
    return draft(preferences=[], **overrides)


@pytest.mark.parametrize(
    ("query", "constraint"),
    [
        ("Anything but metal.", hard("genre", "excluded", "Anything but", value="metal")),
        ("No rock please.", hard("genre", "excluded", "No", value="rock")),
        (
            "Moody sax, nothing with drums.",
            hard("instrument", "excluded", "nothing", value="drums"),
        ),
        ("Please skip the banjo.", hard("instrument", "excluded", "skip", value="banjo")),
        ("Only jazz, please.", hard("genre", "required", "only", value="jazz")),
        ("It needs a cello.", hard("instrument", "required", "needs", value="cello")),
    ],
)
def test_explicit_constraints_outside_the_parsers_cues_are_accepted(
    query: str, constraint: DraftConstraint
) -> None:
    spec, reason, _ = interpret(no_prefs(hard_constraints=[constraint]), query)
    assert reason is None
    assert spec is not None
    [got] = spec.hard_constraints
    assert (got.attribute, got.operator, got.value) == (
        constraint.attribute,
        constraint.operator,
        constraint.value,
    )
    assert spec.interpreter == "llm"


@pytest.mark.parametrize(
    ("query", "cue"),
    [
        ("Get rid of the vocals, just something mellow.", "Get rid of"),
        ("I don't want any singing, only soft guitar.", "don't want"),
        ("It must have no singing.", "no"),
    ],
)
def test_vocals_wording_the_parser_misreads_becomes_a_hard_exclusion(query: str, cue: str) -> None:
    response = no_prefs(vocals="excluded", hard_constraints=[hard("vocals", "excluded", cue)])
    spec, reason, _ = interpret(response, query)
    assert reason is None
    assert spec is not None
    assert spec.vocal_preferences == "excluded"
    assert [c.attribute for c in spec.hard_constraints] == ["vocals"]


def test_a_vocals_constraint_with_a_value_or_unspecified_choice_is_normalized() -> None:
    constraint = hard("vocals", "excluded", "without", value="vocals")
    spec, reason, _ = interpret(no_prefs(hard_constraints=[constraint]), "Piano without vocals")
    assert reason is None
    assert spec is not None
    assert spec.vocal_preferences == "excluded"
    assert spec.hard_constraints[0].value is None


@pytest.mark.parametrize(
    ("query", "constraint", "expected"),
    [
        (
            "Short punk, two minutes tops.",
            hard("duration", "range", "two minutes tops", high=120),
            (None, 120.0),
        ),
        (
            "A long piece, at least 600 seconds.",
            hard("duration", "range", "600", low=600),
            (600.0, None),
        ),
        (
            "Must be from the 70s.",
            hard("era", "range", "70s", low=1970, high=1979),
            (1970.0, 1979.0),
        ),
    ],
)
def test_ranges_need_a_number_in_their_cue(
    query: str, constraint: DraftConstraint, expected: tuple[float | None, float | None]
) -> None:
    spec, reason, _ = interpret(no_prefs(hard_constraints=[constraint]), query)
    assert reason is None
    assert spec is not None
    assert spec.hard_constraints[0].range == expected


@pytest.mark.parametrize(
    ("query", "constraint"),
    [
        # the cue is invented
        ("Ambient music", hard("genre", "excluded", "without", value="metal")),
        ("Ambient without drums", hard("instrument", "excluded", "strictly no", value="drums")),
        # the cue is real but soft
        (CHILL_FLUTE, hard("instrument", "required", "with", value="flute")),
        ("Less rock please", hard("genre", "excluded", "Less", value="rock")),
        ("Maybe some harp", hard("instrument", "required", "Maybe", value="harp")),
        # the value is invented
        ("No rock please", hard("genre", "excluded", "No", value="metal")),
        ("No rock please", hard("instrument", "excluded", "No", value="Aphex Twin")),
        ("No rock please", hard("genre", "excluded", "No")),
        # negation about something else is not about vocals
        ("No rock please", hard("vocals", "excluded", "No")),
        # a long, unnumbered "range"
        ("A long ambient piece", hard("duration", "range", "long", low=600)),
    ],
)
def test_unbacked_constraints_are_rejected(query: str, constraint: DraftConstraint) -> None:
    spec, reason, _ = interpret(no_prefs(hard_constraints=[constraint]), query)
    assert spec is None
    assert reason == "soft_to_hard_escalation"


def test_a_hard_exclusion_also_gets_a_negative_preference() -> None:
    constraint = hard("genre", "excluded", "Anything but", value="metal")
    spec, _, _ = interpret(no_prefs(hard_constraints=[constraint]), "Anything but metal.")
    assert spec is not None
    assert [p.value for p in spec.negative_preferences] == ["metal"]


def test_a_range_with_impossible_bounds_is_inconsistent() -> None:
    constraint = hard("duration", "range", "2 minutes", low=300, high=100)
    spec, reason, _ = interpret(no_prefs(hard_constraints=[constraint]), "About 2 minutes")
    assert spec is None
    assert reason == "inconsistent_output"


def test_values_outside_the_lexicon_are_kept_when_the_request_says_them() -> None:
    query = "A gauzy harmonium drone"
    prefs = [DraftPreference(category="mood", value="Gauzy", weight=0.7, source_span="gauzy")]
    spec, reason, _ = interpret(draft(preferences=prefs), query)
    assert reason is None
    assert spec is not None
    assert [p.value for p in spec.mood_preferences] == ["gauzy"]
    assert any("gauzy" in note and "own words" in note for note in spec.uncertainties)


@pytest.mark.parametrize(("value", "span"), [("Aphex Twin", "gauzy"), ("gauzy", "made up span")])
def test_outside_values_need_both_value_and_span_in_the_request(value: str, span: str) -> None:
    prefs = [DraftPreference(category="mood", value=value, weight=0.7, source_span=span)]
    spec, reason, _ = interpret(draft(preferences=prefs), "A gauzy harmonium drone")
    assert reason is None
    assert spec is not None
    assert spec.mood_preferences == []
    assert any(value in note for note in spec.uncertainties)


# --- clarification ------------------------------------------------------------------------


def test_a_contradiction_in_the_validated_spec_becomes_a_clarification() -> None:
    query = "must have no vocals, must have vocals"
    both = [hard("vocals", "excluded", "must have no"), hard("vocals", "required", "must have")]
    spec, reason, _ = interpret(no_prefs(hard_constraints=both), query)
    assert reason is None
    assert spec is not None
    assert spec.needs_clarification
    assert "vocals" in (spec.clarification_question or "")
    assert spec.interpreter == "llm"


@pytest.mark.parametrize("question", [None, "   ", "x" * 201])
def test_a_clarification_needs_a_short_question(question: str | None) -> None:
    response = draft(needs_clarification=True, clarification_question=question)
    spec, reason, _ = interpret(response)
    assert spec is None
    assert reason == "inconsistent_output"


# --- CLAP prompts -------------------------------------------------------------------------


def test_the_llms_prompts_reach_the_spec_unchanged() -> None:
    prompts = ["slow rainy synth pads", "soft nocturnal ambient textures"]
    spec, _, _ = interpret(no_prefs(semantic_prompts=prompts), "Music for a rainy night drive")
    assert spec is not None
    assert spec.semantic_prompts == prompts


def test_without_llm_prompts_the_deterministic_ones_are_used() -> None:
    spec, _, _ = interpret(draft())
    assert spec is not None
    assert spec.semantic_prompts, "built from the accepted preferences"


def test_prompts_are_capped_deduplicated_and_tidied() -> None:
    many = ["one  sound", "ONE sound", "two", "three", "four", "five"]
    spec, _, _ = interpret(no_prefs(semantic_prompts=many))
    assert spec is not None
    assert spec.semantic_prompts == ["one sound", "two", "three", "four"]


def test_a_prompt_naming_someone_absent_from_the_request_is_left_out() -> None:
    prompts = ["Warm tape hiss", "music like Aphex Twin", "x " * 16, "warm tape music"]
    spec, _, _ = interpret(no_prefs(semantic_prompts=prompts))
    assert spec is not None
    assert spec.semantic_prompts == ["Warm tape hiss", "warm tape music"]
    assert any("Aphex Twin" in note for note in spec.uncertainties)


def test_a_prompt_mentioning_a_ruled_out_value_is_left_out() -> None:
    """Live answer, 2026-11-04: audio search reads "avoids metal" as closer to metal."""
    constraint = hard("genre", "excluded", "Anything but", value="metal")
    response = no_prefs(
        hard_constraints=[constraint],
        semantic_prompts=["music that avoids metal genre entirely", "gentle acoustic guitar"],
    )
    spec, reason, _ = interpret(response, "Anything but metal.")
    assert reason is None
    assert spec is not None
    assert spec.semantic_prompts == ["gentle acoustic guitar"]
    assert any("avoids metal" in note for note in spec.uncertainties)


def test_a_prompt_may_use_a_name_the_request_gave() -> None:
    spec, _, _ = interpret(no_prefs(semantic_prompts=["sounds like Bo Diddley"]), "Like Bo Diddley")
    assert spec is not None
    assert spec.semantic_prompts == ["sounds like Bo Diddley"]


# --- multi-turn --------------------------------------------------------------------------


def _session_with(spec: SearchSpecification) -> SearchSession:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    turn = SearchTurnRecord(
        query_id="q1", query_text=spec.original_query, spec=spec, created_at=now
    )
    return SearchSession(session_id="s", created_at=now).with_turn(turn)


def test_hard_constraints_survive_an_llm_follow_up() -> None:
    first = PARSER.parse("Calm piano without vocals")
    upbeat = no_prefs(semantic_prompts=["bright upbeat piano"])
    spec = agent(upbeat).interpret("more upbeat", _session_with(first))
    assert spec.hard_constraints == first.hard_constraints
    assert spec.vocal_preferences == "excluded"
    assert spec.interpreter == "llm"


def test_a_follow_up_uses_the_llms_new_prompts_first() -> None:
    first = PARSER.parse("Calm piano music")
    follow_up = no_prefs(semantic_prompts=["bright upbeat piano"])
    spec = agent(follow_up).interpret("more upbeat", _session_with(first))
    assert spec.semantic_prompts[0] == "bright upbeat piano"
    assert len(spec.semantic_prompts) >= 1


def test_a_follow_up_contradicting_a_hard_constraint_still_asks() -> None:
    first = PARSER.parse("Calm piano without vocals")
    conflict = no_prefs(
        vocals="required", hard_constraints=[hard("vocals", "required", "must have")]
    )
    spec = agent(conflict).interpret("but it must have vocals", _session_with(first))
    assert spec.needs_clarification
    assert spec.hard_constraints == first.hard_constraints
