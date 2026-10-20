from typing import Any

import pytest
from pydantic import ValidationError

from music_discovery.domain.errors import ContradictoryConstraintsError
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    HardConstraint,
    SearchSpecification,
    WeightedPreference,
)

# The example from base.md §5.3, verbatim.
BASE_EXAMPLE: dict[str, Any] = {
    "original_query": "Something chill with a flute",
    "mood_preferences": [{"value": "chill", "weight": 0.7}],
    "instrument_preferences": [{"value": "flute", "weight": 1.0}],
    "genre_preferences": [],
    "tempo_preferences": [],
    "vocal_preferences": "unspecified",
    "hard_constraints": [],
    "negative_preferences": [],
    "reference_track_ids": [],
    "diversity": 0.5,
    "needs_clarification": False,
    "uncertainties": [],
}

NO_VOCALS = {"attribute": "vocals", "operator": "excluded"}


def spec(**overrides: Any) -> SearchSpecification:
    values = {**BASE_EXAMPLE, **overrides}
    return SearchSpecification.model_validate(values)


def test_base_example_validates() -> None:
    s = SearchSpecification.model_validate(BASE_EXAMPLE)
    assert s.original_query == "Something chill with a flute"
    assert s.instrument_preferences[0] == WeightedPreference(value="flute", weight=1.0)
    assert s.hard_constraints == []
    assert s.spec_version == 1
    assert s.interpreter == "deterministic"


def test_roundtrip() -> None:
    s = spec(
        hard_constraints=[
            NO_VOCALS,
            {"attribute": "era", "operator": "range", "range": [None, 1990]},
        ],
        vocal_preferences="excluded",
        semantic_prompts=["relaxed instrumental music featuring a flute melody"],
        negative_preferences=[{"value": "acoustic", "weight": 0.4}],
        reference_track_ids=["trk_a"],
        excluded_track_ids=["trk_b"],
    )
    assert SearchSpecification.model_validate(s.model_dump(mode="json")) == s


@pytest.mark.parametrize(
    "overrides",
    [
        {"original_query": "   "},
        {"mood_preferences": [{"value": "chill", "weight": 1.5}]},
        {"mood_preferences": [{"value": "chill", "weight": -0.1}]},
        {"diversity": 2},
        {
            "mood_preferences": [
                {"value": "chill", "weight": 0.7},
                {"value": "Chill", "weight": 0.2},
            ]
        },
        {"negative_preferences": [{"value": "flute", "weight": 0.5}]},
        {"semantic_prompts": ["a", "b", "c", "d", "e"]},
        {"semantic_prompts": ["same", "same"]},
        {"needs_clarification": True},
        {"clarification_question": "Which flute?"},
        {"interpreter_model": "vendor/model:free"},
        {"reference_track_ids": ["trk_a"], "negative_reference_track_ids": ["trk_a"]},
        {"reference_track_ids": ["trk_a"], "excluded_track_ids": ["trk_a"]},
        {"excluded_track_ids": ["trk_a", "trk_a"]},
        {"vocal_preferences": "excluded"},
        {"unknown_field": True},
    ],
)
def test_rejects_invalid_specs(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        spec(**overrides)


def test_clarification_and_llm_fields_when_consistent() -> None:
    s = spec(
        needs_clarification=True,
        clarification_question="Do you want vocals or not?",
        interpreter="llm",
        interpreter_model="vendor/model:free",
    )
    assert s.needs_clarification
    assert s.interpreter_model == "vendor/model:free"


@pytest.mark.parametrize(
    ("constraints", "extra"),
    [
        ([NO_VOCALS, {"attribute": "vocals", "operator": "required"}], {}),
        ([NO_VOCALS], {"vocal_preferences": "preferred"}),
        ([{"attribute": "vocals", "operator": "required"}], {"vocal_preferences": "avoided"}),
        (
            [
                {"attribute": "instrument", "operator": "required", "value": "flute"},
                {"attribute": "instrument", "operator": "excluded", "value": "Flute"},
            ],
            {},
        ),
        (
            [{"attribute": "instrument", "operator": "excluded", "value": "flute"}],
            {},
        ),
        (
            [{"attribute": "genre", "operator": "required", "value": "jazz"}],
            {"negative_preferences": [{"value": "jazz", "weight": 0.5}]},
        ),
    ],
)
def test_contradictions_raise_domain_error(
    constraints: list[dict[str, Any]], extra: dict[str, Any]
) -> None:
    with pytest.raises(ContradictoryConstraintsError) as info:
        spec(hard_constraints=constraints, **extra)
    assert info.value.code == "contradictory_constraints"


def test_instrumental_only_is_hard_while_soft_wording_is_not() -> None:
    hard = spec(hard_constraints=[NO_VOCALS], vocal_preferences="excluded")
    assert (
        hard.constraints_for(ConstraintAttribute.VOCALS)[0].operator is ConstraintOperator.EXCLUDED
    )
    soft = spec(vocal_preferences="avoided")
    assert soft.hard_constraints == []


@pytest.mark.parametrize(
    "constraint",
    [
        {"attribute": "era", "operator": "excluded", "value": "1990s"},
        {"attribute": "era", "operator": "range"},
        {"attribute": "era", "operator": "range", "range": [None, None]},
        {"attribute": "tempo", "operator": "range", "range": [140, 90]},
        {"attribute": "duration", "operator": "range", "range": [-1, 10]},
        {"attribute": "vocals", "operator": "excluded", "value": "female"},
        {"attribute": "instrument", "operator": "required"},
        {"attribute": "genre", "operator": "range", "range": [1, 2]},
        {"attribute": "genre", "operator": "required", "value": "jazz", "range": [1, 2]},
    ],
)
def test_malformed_constraints_rejected(constraint: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        HardConstraint.model_validate(constraint)


def test_duplicate_and_multiple_range_constraints_rejected() -> None:
    with pytest.raises(ValidationError):
        spec(hard_constraints=[NO_VOCALS, NO_VOCALS], vocal_preferences="excluded")
    with pytest.raises(ValidationError):
        spec(
            hard_constraints=[
                {"attribute": "era", "operator": "range", "range": [1970, None]},
                {"attribute": "era", "operator": "range", "range": [None, 1990]},
            ]
        )


def test_refinement_keeps_original_query() -> None:
    s = spec()
    refined = s.model_copy(update={"spec_version": 2})
    assert refined.original_query == s.original_query
    assert refined.spec_version == 2
