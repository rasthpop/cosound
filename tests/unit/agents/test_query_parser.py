from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from music_discovery.agents.lexicon_loader import DEFAULT_DIR, LexiconError, load_lexicon
from music_discovery.agents.query_parser import QueryParser
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    HardConstraint,
    SearchSpecification,
)

QUERIES = Path(__file__).parents[3] / "data" / "evaluation" / "queries.jsonl"
LEXICON = load_lexicon()
PARSER = QueryParser(LEXICON)
VOCALS_EXCLUDED = HardConstraint(
    attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
)


def parse(text: str) -> SearchSpecification:
    return PARSER.parse(text)


def values(spec: SearchSpecification, category: str) -> list[str]:
    return [p.value for p in spec.positive_preferences[category]]


def weight(spec: SearchSpecification, category: str, value: str) -> float:
    return next(p.weight for p in spec.positive_preferences[category] if p.value == value)


def negatives(spec: SearchSpecification) -> list[str]:
    return [p.value for p in spec.negative_preferences]


def constraint(attribute: str, operator: str, value: str | None = None) -> HardConstraint:
    return HardConstraint(
        attribute=ConstraintAttribute(attribute), operator=ConstraintOperator(operator), value=value
    )


def ranged(attribute: str, low: float | None, high: float | None) -> HardConstraint:
    return HardConstraint(
        attribute=ConstraintAttribute(attribute),
        operator=ConstraintOperator.RANGE,
        range=(low, high),
    )


# --- Done-when cases ------------------------------------------------------------------


def test_chill_with_a_flute_is_two_soft_preferences() -> None:
    spec = parse("Something chill with a flute")
    assert values(spec, "mood") == ["chill"]
    assert values(spec, "instrument") == ["flute"]
    assert spec.hard_constraints == []
    assert not spec.needs_clarification
    assert spec.interpreter == "deterministic"


def test_without_vocals_is_a_hard_exclusion() -> None:
    spec = parse("Calm acoustic music without vocals")
    assert spec.hard_constraints == [VOCALS_EXCLUDED]
    assert spec.vocal_preferences == "excluded"
    assert values(spec, "mood") == ["calm"]
    assert values(spec, "texture") == ["acoustic"]


def test_intensifiers_scale_weights() -> None:
    slightly = weight(parse("slightly dark music"), "mood", "dark")
    plain = weight(parse("dark music"), "mood", "dark")
    very = weight(parse("very dark music"), "mood", "dark")
    assert slightly < plain < very <= 1.0


@pytest.mark.parametrize(
    ("text", "negated", "kept"),
    [
        ("no vocals, with piano", [], ["piano"]),
        ("without drums but with bass", ["drums"], ["bass"]),
        ("dark music without vocals and a flute", [], ["flute"]),
        ("without heavy drums", ["heavy", "drums"], []),
        ("no drums or bass", ["drums", "bass"], []),
        ("not too dark, just mellow", ["dark"], ["mellow"]),
    ],
)
def test_negation_covers_the_next_phrase_only(
    text: str, negated: list[str], kept: list[str]
) -> None:
    spec = parse(text)
    assert negatives(spec) == negated
    positive = [v for prefs in spec.positive_preferences.values() for v in (p.value for p in prefs)]
    for value in kept:
        assert value in positive
    for value in negated:
        assert value not in positive


# --- Hard vs soft ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Instrumental electronic music, no vocals at all.", [VOCALS_EXCLUDED]),
        ("hip-hop beats without rapping", [VOCALS_EXCLUDED]),
        ("instrumental only", [VOCALS_EXCLUDED]),
        ("strictly instrumental", [VOCALS_EXCLUDED]),
        ("jazz with vocals only", [constraint("vocals", "required")]),
        ("only jazz", [constraint("genre", "required", "jazz")]),
        ("must have a flute", [constraint("instrument", "required", "flute")]),
        ("ambient without drums", [constraint("instrument", "excluded", "drums")]),
        ("no rock", [constraint("genre", "excluded", "rock")]),
        ("loud rock without any electronic sounds", []),
        ("instrumental hip-hop", []),
        ("less vocals please", []),
    ],
)
def test_hard_constraints_need_explicit_cues(text: str, expected: list[HardConstraint]) -> None:
    assert parse(text).hard_constraints == expected


def test_soft_vocal_cues() -> None:
    assert parse("instrumental hip-hop").vocal_preferences == "avoided"
    assert parse("less vocals please").vocal_preferences == "avoided"
    assert parse("dreamy music with female vocals").vocal_preferences == "preferred"
    assert parse("not instrumental").vocal_preferences == "preferred"


def test_excluded_genre_is_also_a_negative_preference() -> None:
    spec = parse("no rock")
    assert negatives(spec) == ["rock"]
    soft = parse("loud rock without any electronic sounds")
    assert negatives(soft) == ["electronic"]
    assert values(soft, "genre") == ["rock"]


def test_only_on_a_mood_stays_soft_and_says_so() -> None:
    spec = parse("only calm")
    assert values(spec, "mood") == ["calm"]
    assert spec.hard_constraints == []
    assert any("cannot be a hard constraint" in u for u in spec.uncertainties)


# --- Ranges ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a calm piano piece under three minutes", ranged("duration", None, 180)),
        ("less than a minute", ranged("duration", None, 60)),
        ("over 5 minutes", ranged("duration", 300, None)),
        ("between 2 and 4 minutes", ranged("duration", 120, 240)),
        ("no longer than 3 minutes", ranged("duration", None, 180)),
        ("rock before 1990", ranged("era", None, 1989)),
        ("after 2000", ranged("era", 2001, None)),
        ("since 2000", ranged("era", 2000, None)),
        ("before the 90s", ranged("era", None, 1989)),
        ("from the 80s to the 90s", ranged("era", 1980, 1999)),
        ("between 1990 and 1995", ranged("era", 1990, 1995)),
        ("under 100 bpm", ranged("tempo", None, 100)),
        ("only 80s", ranged("era", 1980, 1989)),
    ],
)
def test_numeric_ranges_are_hard(text: str, expected: HardConstraint) -> None:
    spec = parse(text)
    assert spec.hard_constraints == [expected]
    assert negatives(spec) == [], "'no' / 'less' inside a range cue is not a negation"


def test_a_decade_alone_is_a_soft_era_preference() -> None:
    for text in ("music from the 80s", "1980s synth pop", "eighties synth", "'80s synth"):
        spec = parse(text)
        assert values(spec, "era") == ["1980s"], text
        assert spec.hard_constraints == [], text


def test_two_bounds_on_one_attribute_merge() -> None:
    spec = parse("over 2 minutes and under 5 minutes")
    assert spec.hard_constraints == [ranged("duration", 120, 300)]


# --- Clarification and uncertainty ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "no vocals with female vocals",
        "chill but not chill",
        "over 5 minutes but under 3 minutes",
        "only jazz, no jazz",
    ],
)
def test_contradictions_ask_instead_of_guessing(text: str) -> None:
    spec = parse(text)
    assert spec.needs_clarification
    assert spec.clarification_question is not None
    assert "rules out" in spec.clarification_question


def test_contradictory_parts_are_dropped_not_guessed() -> None:
    spec = parse("no vocals with female vocals")
    assert spec.vocal_preferences == "unspecified"
    assert spec.hard_constraints == []


@pytest.mark.parametrize(
    "text", ["something", "music please", "Music for a rainy afternoon.", "Something chill"]
)
def test_broad_requests_do_not_ask(text: str) -> None:
    assert not parse(text).needs_clarification


def test_no_words_at_all_asks() -> None:
    spec = parse("???")
    assert spec.needs_clarification
    assert spec.clarification_question


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty query"):
        parse("   ")


def test_unmapped_musical_words_are_uncertainties() -> None:
    spec = parse("Atmospheric music with a gradual build and soft piano")
    assert "unmapped musical term: 'gradual build'" in spec.uncertainties
    assert "unmapped musical term: 'soft'" in spec.uncertainties
    assert spec.original_query == "Atmospheric music with a gradual build and soft piano"


def test_vocal_type_is_an_uncertainty() -> None:
    spec = parse("Dreamy music with female vocals.")
    assert any("female vocals" in u for u in spec.uncertainties)


# --- Normalization --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "category", "value"),
    [
        ("laid-back grooves", "mood", "relaxed"),
        ("laid back", "mood", "relaxed"),
        ("LAID\u2013BACK", "mood", "relaxed"),
        ("hip hop", "genre", "hip-hop"),
        ("hiphop", "genre", "hip-hop"),
        ("drum & bass", "genre", "drum and bass"),
        ("heavy metal", "genre", "metal"),
        ("a heavy bassline", "instrument", "bass"),
        ("violins", "instrument", "violin"),
        ("Café jazz", "genre", "jazz"),
    ],
)
def test_synonyms_map_to_canonical_terms(text: str, category: str, value: str) -> None:
    assert value in values(parse(text), category)


def test_weak_synonyms_and_with_boost() -> None:
    woodwind = weight(parse("woodwind"), "instrument", "flute")
    flute = weight(parse("flute"), "instrument", "flute")
    with_flute = weight(parse("with a flute"), "instrument", "flute")
    assert woodwind < flute < with_flute == 1.0


def test_semantic_prompts_are_built_from_the_spec() -> None:
    spec = parse("Something chill with a flute")
    assert spec.semantic_prompts
    assert all("flute" in p or "chill" in p for p in spec.semantic_prompts)


# --- The 20 evaluation queries ----------------------------------------------------------


def _eval_queries() -> list[dict[str, object]]:
    return [json.loads(line) for line in QUERIES.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("query", _eval_queries(), ids=lambda q: str(q["query_id"]))
def test_evaluation_queries_match_expected_attributes(query: dict[str, object]) -> None:
    spec = parse(str(query["text"]))
    expected = query["expected_attributes"]
    assert isinstance(expected, dict)
    for category, wanted in expected.items():
        if category == "vocals":
            assert spec.vocal_preferences == wanted
        else:
            assert sorted(values(spec, category)) == sorted(wanted), category
    hard = [c.model_dump(mode="json", exclude_none=True) for c in spec.hard_constraints]
    assert hard == query["expected_hard_constraints"]
    assert not spec.needs_clarification


# --- Lexicon ----------------------------------------------------------------------------


def test_lexicon_version_is_a_content_hash(tmp_path: Path) -> None:
    copy = tmp_path / "lexicon"
    shutil.copytree(DEFAULT_DIR, copy)
    assert load_lexicon(copy).version == LEXICON.version
    with (copy / "mood.yaml").open("a") as f:
        f.write("  sleepy: [sleepy]\n")
    assert load_lexicon(copy).version != LEXICON.version


def test_ambiguous_phrase_is_rejected(tmp_path: Path) -> None:
    copy = tmp_path / "lexicon"
    shutil.copytree(DEFAULT_DIR, copy)
    with (copy / "texture.yaml").open("a") as f:
        f.write("  dusky: [dark]\n")
    with pytest.raises(LexiconError, match="'dark' already means mood:dark"):
        load_lexicon(copy)


def test_unquoted_yaml_boolean_is_rejected(tmp_path: Path) -> None:
    copy = tmp_path / "lexicon"
    shutil.copytree(DEFAULT_DIR, copy)
    cues = copy / "cues.yaml"
    cues.write_text(cues.read_text().replace('[without, "no",', "[without, no,", 1))
    with pytest.raises(LexiconError, match="quote it"):
        load_lexicon(copy)


def test_expand_returns_full_weight_synonyms() -> None:
    relaxed = LEXICON.expand("relaxed")
    assert relaxed[0] == "relaxed"
    assert "laid back" in relaxed
    assert "chill" not in relaxed
    assert LEXICON.expand("woodwind") == ["woodwind"], "weak synonyms are not expanded"
    assert LEXICON.expand("kazoo") == ["kazoo"]


def test_expand_never_counts_the_same_words_twice() -> None:
    # "chill out" and "pan flute" match only fields that "chill" / "flute" already match
    assert LEXICON.expand("chill") == ["chill", "chilled", "chillout"]
    assert "pan flute" not in LEXICON.expand("flute")
    assert LEXICON.expand("chill out") == ["chill", "chilled", "chillout"]
    laid_back = LEXICON.expand("laid-back")
    assert laid_back[0] == "laid-back"
    assert "laid back" not in laid_back, "same words as 'laid-back'"
