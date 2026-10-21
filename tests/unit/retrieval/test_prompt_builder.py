import pytest

from music_discovery.domain.schemas import SearchSpecification
from music_discovery.retrieval.prompt_builder import GLUE_WORDS, build_prompts, with_prompts


def spec(**kw: object) -> SearchSpecification:
    return SearchSpecification.model_validate({"original_query": "q", **kw})


def pref(value: str, weight: float = 0.8) -> dict[str, object]:
    return {"value": value, "weight": weight}


CHILL_FLUTE = spec(
    original_query="Something chill with a flute",
    mood_preferences=[pref("chill", 0.7)],
    instrument_preferences=[pref("flute", 1.0)],
)

CASES = [
    CHILL_FLUTE,
    spec(
        original_query="Dark electronic music with a heavy bassline",
        mood_preferences=[pref("dark")],
        genre_preferences=[pref("electronic")],
        instrument_preferences=[pref("bass")],
        energy_preferences=[pref("heavy", 0.6)],
    ),
    spec(
        original_query="Calm acoustic music without vocals",
        mood_preferences=[pref("calm")],
        texture_preferences=[pref("acoustic")],
        vocal_preferences="excluded",
        hard_constraints=[{"attribute": "vocals", "operator": "excluded"}],
        negative_preferences=[pref("drums", 0.5)],
    ),
    spec(
        original_query="Dreamy music with female vocals from the 80s",
        mood_preferences=[pref("dreamy")],
        genre_preferences=[pref("synth pop")],
        era_preferences=[pref("1980s")],
        vocal_preferences="preferred",
    ),
]


def test_chill_flute_prompts() -> None:
    prompts = build_prompts(CHILL_FLUTE)
    assert prompts == ["chill music featuring flute", "chill music with flute"]


@pytest.mark.parametrize("s", CASES)
def test_prompts_only_use_spec_values_and_glue(s: SearchSpecification) -> None:
    allowed = set(GLUE_WORDS)
    for prefs in s.positive_preferences.values():
        for p in prefs:
            allowed |= set(p.value.casefold().split())
    prompts = build_prompts(s)
    assert 1 <= len(prompts) <= 4
    assert len(set(prompts)) == len(prompts)
    for prompt in prompts:
        assert set(prompt.casefold().split()) <= allowed, prompt


def test_negative_preferences_never_appear() -> None:
    for prompt in build_prompts(CASES[2]):
        assert "drums" not in prompt
    assert any("instrumental" in p for p in build_prompts(CASES[2]))


def test_vocals_and_era() -> None:
    prompts = build_prompts(CASES[3])
    assert "synth pop music from the 1980s" in prompts
    assert any("with vocals" in p for p in prompts)
    assert not any("instrumental" in p for p in prompts)


def test_nothing_to_expand() -> None:
    assert build_prompts(spec(original_query="something")) == []
    assert build_prompts(spec(original_query="x", vocal_preferences="avoided")) == []


def test_deterministic_and_capped() -> None:
    assert build_prompts(CASES[1]) == build_prompts(CASES[1])
    assert len(build_prompts(CASES[1], max_prompts=2)) == 2


def test_with_prompts_returns_validated_copy() -> None:
    filled = with_prompts(CHILL_FLUTE)
    assert filled.semantic_prompts == build_prompts(CHILL_FLUTE)
    assert CHILL_FLUTE.semantic_prompts == [], "original spec untouched"
