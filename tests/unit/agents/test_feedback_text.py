from __future__ import annotations

from datetime import UTC, datetime

import pytest

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.feedback_rules import RuleContext, apply_rule
from music_discovery.agents.feedback_text import (
    DraftAdjustment,
    FeedbackDraft,
    FeedbackTextNormalizer,
)
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.domain.enums import FeedbackType
from tests.fakes import FakeStructuredLLM

LEXICON = load_lexicon()
NORMALIZER = FeedbackTextNormalizer(LEXICON)
NOW = datetime(2026, 10, 23, tzinfo=UTC)
MORE, LESS = FeedbackType.MORE_OF_ATTRIBUTE, FeedbackType.LESS_OF_ATTRIBUTE


def normalize(text: str, normalizer: FeedbackTextNormalizer = NORMALIZER):  # type: ignore[no-untyped-def]
    return normalizer.normalize(
        text, session_id="ses_1", query_id="qry_1", event_id="evt_9", timestamp=NOW
    )


def pairs(text: str) -> list[tuple[FeedbackType, str | None]]:
    return [(e.event_type, e.attribute) for e in normalize(text).events]


def test_compound_feedback_gives_two_events() -> None:
    result = normalize("More electronic, less acoustic")
    assert result.accepted
    assert [(e.event_type, e.attribute) for e in result.events] == [
        (MORE, "electronic"),
        (LESS, "acoustic"),
    ]
    assert [e.event_id for e in result.events] == ["evt_9.1", "evt_9.2"]
    assert all(e.free_text == "More electronic, less acoustic" for e in result.events)
    assert all(e.search_session_id == "ses_1" and e.query_id == "qry_1" for e in result.events)
    assert result.interpreter == "deterministic"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("darker please", [(MORE, "dark")]),
        ("too dark", [(LESS, "dark")]),
        ("not so electronic and more piano", [(LESS, "electronic"), (MORE, "piano")]),
        ("no drums", [(LESS, "drums")]),
        ("without vocals", [(LESS, "vocals")]),
        ("fewer guitars but keep it chill", [(LESS, "guitar"), (MORE, "chill")]),
    ],
)
def test_lexicon_mapping(text: str, expected: list[tuple[FeedbackType, str]]) -> None:
    assert pairs(text) == expected


@pytest.mark.parametrize("text", ["hmm, not sure", "I like the second one", "asdf qwer"])
def test_unmappable_text_is_rejected_with_reason(text: str) -> None:
    result = normalize(text)
    assert not result.accepted
    assert result.events == []
    assert result.reason == "no known attribute in the feedback"


def test_empty_text_is_rejected() -> None:
    result = normalize("   ")
    assert not result.accepted
    assert result.reason == "empty feedback"


def test_feedback_negation_is_never_a_hard_constraint() -> None:
    spec = QueryAgent(LEXICON).interpret("Something chill with a flute.")
    for event in normalize("no vocals, without drums").events:
        spec = apply_rule(spec, event, RuleContext(LEXICON)).spec
    assert spec.hard_constraints == []
    assert spec.vocal_preferences == "avoided"


def test_more_electronic_less_acoustic_end_to_end_keeps_flute_and_chill() -> None:
    spec = QueryAgent(LEXICON).interpret("Something chill with a flute.")
    for event in normalize("More electronic, less acoustic").events:
        spec = apply_rule(spec, event, RuleContext(LEXICON)).spec
    assert {p.value for p in spec.genre_preferences} == {"electronic"}
    assert {p.value for p in spec.negative_preferences} == {"acoustic"}
    assert {p.value for p in spec.mood_preferences} == {"chill"}
    assert {p.value for p in spec.instrument_preferences} == {"flute"}


# --- optional LLM path ------------------------------------------------------------------


def llm_normalizer(
    *responses: FeedbackDraft | str,
) -> tuple[FeedbackTextNormalizer, FakeStructuredLLM]:
    llm = FakeStructuredLLM(list(responses))
    return FeedbackTextNormalizer(LEXICON, llm), llm


def test_llm_output_is_validated_and_used() -> None:
    draft = FeedbackDraft(
        adjustments=[
            DraftAdjustment(direction="more", attribute="electronica"),
            DraftAdjustment(direction="less", attribute="acoustic"),
        ]
    )
    normalizer, llm = llm_normalizer(draft)
    result = normalize("Could it be a bit more electronica and less unplugged?", normalizer)
    assert result.interpreter == "llm"
    assert [(e.event_type, e.attribute) for e in result.events] == [
        (MORE, "electronic"),
        (LESS, "acoustic"),
    ]
    [call] = llm.calls
    assert call.user == "Could it be a bit more electronica and less unplugged?"
    assert call.task == "feedback"


def test_llm_unknown_attribute_falls_back_to_lexicon() -> None:
    draft = FeedbackDraft(adjustments=[DraftAdjustment(direction="more", attribute="Aphex Twin")])
    normalizer, _ = llm_normalizer(draft)
    result = normalize("More electronic, less acoustic", normalizer)
    assert result.interpreter == "deterministic"
    assert result.llm_fallback_reason == "unknown attribute 'Aphex Twin'"
    assert len(result.events) == 2


@pytest.mark.parametrize("code", ["invalid_output", "timeout"])
def test_llm_errors_fall_back_to_lexicon(code: str) -> None:
    normalizer, _ = llm_normalizer(code)
    result = normalize("more piano", normalizer)
    assert result.accepted
    assert result.interpreter == "deterministic"
    assert result.llm_fallback_reason == f"llm_{code}"
