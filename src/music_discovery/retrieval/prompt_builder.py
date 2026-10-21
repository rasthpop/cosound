"""Deterministic CLAP prompt expansion (base.md §7.3).

Expansions are alternate phrasings of the request for text-to-audio retrieval, never extra
requirements. They use only values present in the `SearchSpecification` plus fixed glue words,
so they cannot introduce an attribute the user did not ask for. Negative preferences are
never included.
"""

from __future__ import annotations

from collections.abc import Sequence

from music_discovery.domain.schemas import (
    MAX_SEMANTIC_PROMPTS,
    SearchSpecification,
    WeightedPreference,
)

GLUE_WORDS = frozenset(
    {"music", "featuring", "with", "a", "and", "instrumental", "vocals", "from", "the"}
)
"""The only words a prompt may contain besides values taken from the spec."""


def _values(prefs: Sequence[WeightedPreference], limit: int) -> list[str]:
    ranked = sorted(prefs, key=lambda p: (-p.weight, p.value.casefold()))
    return [p.value for p in ranked[:limit]]


def _join(words: Sequence[str]) -> str:
    return " ".join(w for w in words if w).strip()


def _and(values: Sequence[str]) -> str:
    return " and ".join(values)


def build_prompts(
    spec: SearchSpecification, *, max_prompts: int = MAX_SEMANTIC_PROMPTS
) -> list[str]:
    """Up to `max_prompts` expansions, strongest attributes first; empty if nothing to expand."""
    moods = _values(spec.mood_preferences, 2)
    instruments = _values(spec.instrument_preferences, 2)
    genres = _values(spec.genre_preferences, 1)
    sound = (
        _values(spec.energy_preferences, 1)
        + _values(spec.tempo_preferences, 1)
        + _values(spec.texture_preferences, 1)
    )
    eras = _values(spec.era_preferences, 1)
    no_vocals = spec.vocal_preferences in ("excluded", "avoided")
    wants_vocals = spec.vocal_preferences in ("required", "preferred")

    genre = genres[0] if genres else ""
    describers = moods[:1] + sound[:1]
    featuring = f"featuring {_and(instruments)}" if instruments else ""

    candidates = [
        _join([*describers, genre, "music", featuring]),
        _join(
            [
                *moods[:1],
                "instrumental" if no_vocals else "",
                "music",
                f"with {instruments[0]}" if instruments else "",
            ]
        ),
        _join([*moods, *sound, genre, "music"]),
        _join([genre, "music", "from the", eras[0]]) if eras and genre else "",
        _join([*moods[:1], genre, "music", "with vocals"]) if wants_vocals else "",
    ]
    prompts: list[str] = []
    chosen: list[set[str]] = [set(spec.original_query.casefold().split())]
    for prompt in candidates:
        words = set(prompt.casefold().split())
        # skip empty or glue-only prompts ("instrumental music"), and prompts that say less
        # than one already chosen (e.g. "chill music" after "chill music featuring flute"),
        # which would dilute the request
        if not prompt or words <= GLUE_WORDS or any(words <= c for c in chosen):
            continue
        chosen.append(words)
        prompts.append(prompt)
        if len(prompts) >= max_prompts:
            break
    return prompts


def with_prompts(spec: SearchSpecification) -> SearchSpecification:
    """A validated copy of the spec with deterministic semantic prompts filled in."""
    data = spec.model_dump()
    data["semantic_prompts"] = build_prompts(spec)
    return SearchSpecification.model_validate(data)
