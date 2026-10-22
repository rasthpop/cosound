from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from music_discovery.agents.agent_a_query import NOTHING_NEW_NOTE, REFINEMENT_NOTE, QueryAgent
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.domain.models import SearchSession, SearchTurnRecord
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    HardConstraint,
    SearchSpecification,
)

QUERIES = Path(__file__).parents[3] / "data" / "evaluation" / "queries.jsonl"
AGENT = QueryAgent(load_lexicon())
NOW = datetime(2026, 10, 22, tzinfo=UTC)
VOCALS_EXCLUDED = HardConstraint(
    attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
)


def session(*specs: SearchSpecification) -> SearchSession:
    state = SearchSession(session_id="ses_1", created_at=NOW)
    for i, spec in enumerate(specs):
        turn = SearchTurnRecord(
            query_id=f"qry_{i}", query_text=spec.original_query, spec=spec, created_at=NOW
        )
        state = state.with_turn(turn)
    return state


def after(*queries: str) -> SearchSpecification:
    """Interpret queries one after another in the same session."""
    state: SearchSession | None = None
    specs: list[SearchSpecification] = []
    for query in queries:
        specs.append(AGENT.interpret(query, state))
        state = session(*specs)
    return specs[-1]


def values(prefs: list[object]) -> list[str]:
    return sorted(p.value for p in prefs)  # type: ignore[attr-defined]


def revalidates(spec: SearchSpecification) -> None:
    assert SearchSpecification.model_validate(spec.model_dump(mode="json")) == spec


# --- The 20 evaluation queries ----------------------------------------------------------


def _eval_queries() -> list[dict[str, object]]:
    return [json.loads(line) for line in QUERIES.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("query", _eval_queries(), ids=lambda q: str(q["query_id"]))
def test_evaluation_queries_yield_valid_actionable_specs(query: dict[str, object]) -> None:
    spec = AGENT.interpret(str(query["text"]), None)
    revalidates(spec)
    assert not spec.needs_clarification
    assert spec.original_query == str(query["text"]).strip()
    assert spec.interpreter == "deterministic"
    assert spec.reference_track_ids == spec.excluded_track_ids == []
    hard = [c.model_dump(mode="json", exclude_none=True) for c in spec.hard_constraints]
    assert hard == query["expected_hard_constraints"]


@pytest.mark.parametrize("query", _eval_queries(), ids=lambda q: str(q["query_id"]))
def test_evaluation_queries_start_a_new_search_in_a_session(query: dict[str, object]) -> None:
    earlier = session(AGENT.interpret("Dark electronic music with a heavy bassline.", None))
    spec = AGENT.interpret(str(query["text"]), earlier)
    assert spec == AGENT.interpret(str(query["text"]), None)


# --- Clarification ----------------------------------------------------------------------


@pytest.mark.parametrize("query", ["something", "music please", "Something new."])
def test_broad_queries_are_actionable(query: str) -> None:
    spec = AGENT.interpret(query, None)
    assert not spec.needs_clarification
    assert spec.original_query == query


def test_punctuation_only_asks_for_clarification() -> None:
    spec = AGENT.interpret("?!", None)
    assert spec.needs_clarification
    assert spec.clarification_question


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty query"):
        AGENT.interpret("   ", None)


def test_contradiction_asks_instead_of_guessing() -> None:
    spec = AGENT.interpret("no vocals with female vocals", None)
    assert spec.needs_clarification
    assert spec.clarification_question is not None
    assert "vocals" in spec.clarification_question
    assert spec.vocal_preferences == "unspecified"
    assert spec.hard_constraints == []


def test_answer_to_a_clarification_refines_without_a_cue() -> None:
    spec = after("calm piano, no vocals with vocals", "with vocals")
    assert not spec.needs_clarification
    assert spec.vocal_preferences == "preferred"
    assert values(spec.instrument_preferences) == ["piano"]
    assert spec.original_query == "calm piano, no vocals with vocals. with vocals"


# --- Follow-up queries ------------------------------------------------------------------


def test_follow_up_keeps_earlier_preferences_and_extends_original_query() -> None:
    spec = after("Something chill with a flute.", "more upbeat")
    assert spec.original_query == "Something chill with a flute. more upbeat"
    assert spec.spec_version == 2
    assert values(spec.mood_preferences) == ["chill", "upbeat"]
    assert values(spec.instrument_preferences) == ["flute"]
    assert spec.hard_constraints == []
    assert REFINEMENT_NOTE in spec.uncertainties
    assert any("upbeat" in p for p in spec.semantic_prompts)
    revalidates(spec)


def test_follow_up_negation_replaces_earlier_soft_preference() -> None:
    spec = after("Chill electronic music with a flute", "less electronic, more acoustic")
    assert values(spec.genre_preferences) == []
    assert values(spec.negative_preferences) == ["electronic"]
    assert values(spec.texture_preferences) == ["acoustic"]
    assert values(spec.mood_preferences) == ["chill"]
    assert values(spec.instrument_preferences) == ["flute"]


def test_follow_up_can_add_a_hard_constraint() -> None:
    spec = after("Something chill with a flute.", "but without vocals")
    assert spec.vocal_preferences == "excluded"
    assert spec.hard_constraints == [VOCALS_EXCLUDED]


def test_follow_up_keeps_earlier_hard_constraints() -> None:
    spec = after("Calm acoustic music without vocals", "more upbeat", "also with piano")
    assert spec.spec_version == 3
    assert spec.hard_constraints == [VOCALS_EXCLUDED]
    assert spec.vocal_preferences == "excluded"
    assert values(spec.instrument_preferences) == ["piano"]


def test_soft_wording_does_not_weaken_an_earlier_hard_choice() -> None:
    spec = after("Calm acoustic music without vocals", "and less vocals")
    assert spec.vocal_preferences == "excluded"


def test_follow_up_contradicting_a_hard_constraint_asks() -> None:
    first = AGENT.interpret("Calm acoustic music without vocals", None)
    spec = AGENT.interpret("but with vocals", session(first))
    assert spec.needs_clarification
    assert spec.clarification_question is not None
    assert "vocals" in spec.clarification_question
    assert spec.hard_constraints == first.hard_constraints
    assert spec.vocal_preferences == "excluded"
    assert spec.spec_version == 2
    assert spec.original_query == first.original_query, "rejected follow-up leaves the text"
    revalidates(spec)


def test_follow_up_preferring_a_hard_excluded_instrument_asks() -> None:
    spec = after("Ambient music without drums", "now with drums")
    assert spec.needs_clarification
    assert spec.clarification_question is not None
    assert "drums" in spec.clarification_question
    assert [c.value for c in spec.hard_constraints] == ["drums"]


def test_internally_contradictory_follow_up_asks_and_keeps_previous() -> None:
    first = AGENT.interpret("Something chill with a flute.", None)
    spec = AGENT.interpret("but no vocals with vocals", session(first))
    assert spec.needs_clarification
    assert values(spec.mood_preferences) == ["chill"]
    assert spec.vocal_preferences == "unspecified"


def test_original_query_accumulates_over_follow_ups() -> None:
    spec = after("Calm piano music", "more upbeat", "but without vocals")
    assert spec.original_query == "Calm piano music. more upbeat. but without vocals"


def test_new_range_replaces_earlier_range() -> None:
    spec = after("Calm piano music under three minutes", "but under five minutes")
    [duration] = spec.constraints_for(ConstraintAttribute.DURATION)
    assert duration.range == (None, 300)


def test_follow_up_with_nothing_mapped_keeps_previous_search() -> None:
    first = AGENT.interpret("Something chill with a flute.", None)
    spec = AGENT.interpret("same but faster", session(first))
    assert not spec.needs_clarification
    assert spec.mood_preferences == first.mood_preferences
    assert spec.instrument_preferences == first.instrument_preferences
    assert NOTHING_NEW_NOTE in spec.uncertainties


def test_track_ids_come_only_from_session_state() -> None:
    first = AGENT.interpret("Something chill with a flute.", None)
    with_feedback = first.model_copy(
        update={"reference_track_ids": ["trk_a"], "excluded_track_ids": ["trk_b"]}
    )
    spec = AGENT.interpret("more upbeat, like trk_c", session(with_feedback))
    assert spec.reference_track_ids == ["trk_a"]
    assert spec.excluded_track_ids == ["trk_b"]
    fresh = AGENT.interpret("tracks like trk_c by Aphex Twin", None)
    assert fresh.reference_track_ids == fresh.negative_reference_track_ids == []


def test_session_without_turns_is_a_new_search() -> None:
    spec = AGENT.interpret("more upbeat", session())
    assert spec.spec_version == 1
    assert spec.original_query == "more upbeat"
    assert REFINEMENT_NOTE not in spec.uncertainties
