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
        "needs_clarification": False,
        "clarification_question": None,
    }
    return SearchSpecificationDraft.model_validate(data | overrides)


def interpret(
    response: SearchSpecificationDraft | str, query: str = CHILL_FLUTE, known: tuple[str, ...] = ()
) -> tuple[SearchSpecification | None, str | None, FakeStructuredLLM]:
    llm = FakeStructuredLLM([response], model_id=MODEL)
    outcome = LLMQueryInterpreter(llm, LEXICON).interpret(
        query, PARSER.parse(query), known_track_ids=known
    )
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
    assert load_prompt().version == "query-v1"


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


def test_agent_skips_llm_when_parser_needs_clarification() -> None:
    llm = FakeStructuredLLM([draft()], model_id=MODEL)
    query_agent = QueryAgent(LEXICON, LLMQueryInterpreter(llm, LEXICON))
    spec = query_agent.interpret("no vocals with female vocals")
    assert spec.needs_clarification
    assert llm.calls == []


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
