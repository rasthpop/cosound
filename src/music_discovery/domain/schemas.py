"""Validated value objects exchanged between agents, retrieval and the application layer.

These are domain contracts, not the public HTTP DTOs (those live in `api/`).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Generic, Literal, Self, TypeVar

from pydantic import BaseModel, Field, JsonValue, model_validator

from music_discovery.domain.base import AwareDatetime, FrozenModel, NonEmptyStr, UnitInterval
from music_discovery.domain.enums import (
    ConstraintStatus,
    DataSource,
    FeedbackType,
    MatchStrength,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.errors import ContradictoryConstraintsError

MAX_SEMANTIC_PROMPTS = 4


class WeightedPreference(FrozenModel):
    """A soft preference. It shapes ranking; it never excludes a track by itself."""

    value: NonEmptyStr
    weight: UnitInterval
    source_span: str | None = None
    """The query text that produced this preference, kept for explanations."""


class ConstraintAttribute(StrEnum):
    VOCALS = "vocals"
    INSTRUMENT = "instrument"
    GENRE = "genre"
    ERA = "era"
    TEMPO = "tempo"
    DURATION = "duration"


class ConstraintOperator(StrEnum):
    REQUIRED = "required"
    EXCLUDED = "excluded"
    RANGE = "range"


CATEGORICAL_ATTRIBUTES = frozenset(
    {ConstraintAttribute.VOCALS, ConstraintAttribute.INSTRUMENT, ConstraintAttribute.GENRE}
)
RANGE_ATTRIBUTES = frozenset(
    {ConstraintAttribute.ERA, ConstraintAttribute.TEMPO, ConstraintAttribute.DURATION}
)

Bound = float | None


class HardConstraint(FrozenModel):
    """An explicit requirement ("instrumental only", "before 1990").

    Enforced independently of the weighted score, and only where reliable evidence exists.
    """

    attribute: ConstraintAttribute
    operator: ConstraintOperator
    value: NonEmptyStr | None = None
    range: tuple[Bound, Bound] | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if self.attribute in RANGE_ATTRIBUTES:
            if self.operator is not ConstraintOperator.RANGE:
                raise ValueError(f"{self.attribute} constraints must use the range operator")
            if self.value is not None or self.range is None:
                raise ValueError("range constraints take `range`, not `value`")
            low, high = self.range
            if low is None and high is None:
                raise ValueError("a range needs at least one bound")
            if low is not None and high is not None and low > high:
                raise ValueError("range lower bound is above the upper bound")
            if any(b is not None and b < 0 for b in self.range):
                raise ValueError("range bounds must be non-negative")
        else:
            if self.operator is ConstraintOperator.RANGE:
                raise ValueError(f"{self.attribute} constraints are required/excluded, not ranges")
            if self.range is not None:
                raise ValueError("categorical constraints take `value`, not `range`")
            if self.attribute is ConstraintAttribute.VOCALS and self.value is not None:
                raise ValueError("vocals constraints have no value")
            if self.attribute is not ConstraintAttribute.VOCALS and self.value is None:
                raise ValueError(f"{self.attribute} constraints need a value")
        return self

    @property
    def key(self) -> tuple[ConstraintAttribute, str | None]:
        return (self.attribute, self.value.casefold() if self.value else None)


VocalPreference = Literal["required", "preferred", "avoided", "excluded", "unspecified"]
Interpreter = Literal["deterministic", "llm"]
Weighted = list[WeightedPreference]


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            dupes.add(value)
        seen.add(key)
    return dupes


class SearchSpecification(FrozenModel):
    """Agent A's machine-readable interpretation of a request (base.md §5.3).

    Soft preferences and hard constraints are kept separate. The original query is preserved
    across every refinement.
    """

    spec_version: Annotated[int, Field(ge=1)] = 1
    original_query: NonEmptyStr
    mood_preferences: Weighted = []
    instrument_preferences: Weighted = []
    genre_preferences: Weighted = []
    tempo_preferences: Weighted = []
    energy_preferences: Weighted = []
    texture_preferences: Weighted = []
    era_preferences: Weighted = []
    vocal_preferences: VocalPreference = "unspecified"
    hard_constraints: list[HardConstraint] = []
    negative_preferences: Weighted = []
    reference_track_ids: list[NonEmptyStr] = []
    negative_reference_track_ids: list[NonEmptyStr] = []
    excluded_track_ids: list[NonEmptyStr] = []
    semantic_prompts: Annotated[list[NonEmptyStr], Field(max_length=MAX_SEMANTIC_PROMPTS)] = []
    """Controlled alternate retrieval queries. Never additional requirements."""
    diversity: UnitInterval = 0.5
    needs_clarification: bool = False
    clarification_question: NonEmptyStr | None = None
    uncertainties: list[NonEmptyStr] = []
    interpreter: Interpreter = "deterministic"
    interpreter_model: NonEmptyStr | None = None
    """OpenRouter model id that answered, when `interpreter == "llm"`."""

    @property
    def positive_preferences(self) -> dict[str, Weighted]:
        return {
            "mood": self.mood_preferences,
            "instrument": self.instrument_preferences,
            "genre": self.genre_preferences,
            "tempo": self.tempo_preferences,
            "energy": self.energy_preferences,
            "texture": self.texture_preferences,
            "era": self.era_preferences,
        }

    def constraints_for(self, attribute: ConstraintAttribute) -> list[HardConstraint]:
        return [c for c in self.hard_constraints if c.attribute is attribute]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        self._check_preferences()
        self._check_track_lists()
        self._check_prompts_and_flags()
        self._check_constraints()
        return self

    def _check_preferences(self) -> None:
        for category, prefs in self.positive_preferences.items():
            if dupes := _duplicates(p.value for p in prefs):
                raise ValueError(f"duplicate {category} preferences: {sorted(dupes)}")
        if dupes := _duplicates(p.value for p in self.negative_preferences):
            raise ValueError(f"duplicate negative preferences: {sorted(dupes)}")
        negative = {p.value.casefold() for p in self.negative_preferences}
        for category, prefs in self.positive_preferences.items():
            both = sorted(p.value for p in prefs if p.value.casefold() in negative)
            if both:
                raise ValueError(f"{category} values both preferred and negative: {both}")

    def _check_track_lists(self) -> None:
        lists = {
            "reference_track_ids": self.reference_track_ids,
            "negative_reference_track_ids": self.negative_reference_track_ids,
            "excluded_track_ids": self.excluded_track_ids,
        }
        for name, ids in lists.items():
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate ids in {name}")
        refs = set(self.reference_track_ids)
        if overlap := refs & set(self.negative_reference_track_ids):
            raise ValueError(f"tracks both liked and disliked: {sorted(overlap)}")
        if overlap := refs & set(self.excluded_track_ids):
            raise ValueError(f"reference tracks cannot be excluded: {sorted(overlap)}")

    def _check_prompts_and_flags(self) -> None:
        if _duplicates(self.semantic_prompts):
            raise ValueError("duplicate semantic prompts")
        if self.needs_clarification and self.clarification_question is None:
            raise ValueError("needs_clarification requires a clarification_question")
        if not self.needs_clarification and self.clarification_question is not None:
            raise ValueError("clarification_question is only set when needs_clarification")
        if self.interpreter == "deterministic" and self.interpreter_model is not None:
            raise ValueError("interpreter_model is only set for the llm interpreter")

    def _check_constraints(self) -> None:
        categorical = [
            c for c in self.hard_constraints if c.operator is not ConstraintOperator.RANGE
        ]
        ops: dict[tuple[ConstraintAttribute, str | None], ConstraintOperator] = {}
        for c in categorical:
            previous = ops.get(c.key)
            if previous is not None and previous is not c.operator:
                subject = str(c.attribute) if c.value is None else f"{c.attribute} {c.value!r}"
                raise ContradictoryConstraintsError(
                    f"{subject} is both required and excluded",
                    details={"attribute": str(c.attribute), "value": c.value},
                )
            ops[c.key] = c.operator
        keys = [c.key for c in categorical]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate hard constraints")
        for attribute in RANGE_ATTRIBUTES:
            if len(self.constraints_for(attribute)) > 1:
                raise ValueError(f"use a single range constraint for {attribute}")

        self._check_vocals()
        self._check_constraints_against_preferences()

    def _check_vocals(self) -> None:
        vocal_ops = {c.operator for c in self.constraints_for(ConstraintAttribute.VOCALS)}
        pref = self.vocal_preferences
        if ConstraintOperator.EXCLUDED in vocal_ops and pref in ("required", "preferred"):
            raise ContradictoryConstraintsError(
                f"vocals are excluded but vocal preference is {pref!r}",
                details={"attribute": "vocals"},
            )
        if ConstraintOperator.REQUIRED in vocal_ops and pref in ("avoided", "excluded"):
            raise ContradictoryConstraintsError(
                f"vocals are required but vocal preference is {pref!r}",
                details={"attribute": "vocals"},
            )
        if pref == "excluded" and ConstraintOperator.EXCLUDED not in vocal_ops:
            raise ValueError("vocal_preferences='excluded' must be backed by a hard constraint")
        if pref == "required" and ConstraintOperator.REQUIRED not in vocal_ops:
            raise ValueError("vocal_preferences='required' must be backed by a hard constraint")

    def _check_constraints_against_preferences(self) -> None:
        negative = {p.value.casefold() for p in self.negative_preferences}
        positive_by_attr = {
            ConstraintAttribute.INSTRUMENT: {
                p.value.casefold() for p in self.instrument_preferences
            },
            ConstraintAttribute.GENRE: {p.value.casefold() for p in self.genre_preferences},
        }
        for c in self.hard_constraints:
            if c.attribute not in positive_by_attr or c.value is None:
                continue
            value = c.value.casefold()
            if c.operator is ConstraintOperator.REQUIRED and value in negative:
                raise ContradictoryConstraintsError(
                    f"{c.attribute} {c.value!r} is required but also a negative preference",
                    details={"attribute": str(c.attribute), "value": c.value},
                )
            if c.operator is ConstraintOperator.EXCLUDED and value in positive_by_attr[c.attribute]:
                raise ContradictoryConstraintsError(
                    f"{c.attribute} {c.value!r} is excluded but also preferred",
                    details={"attribute": str(c.attribute), "value": c.value},
                )


# --- Feedback -------------------------------------------------------------------

TRACK_EVENTS = frozenset(
    {
        FeedbackType.MORE_LIKE_THIS,
        FeedbackType.LESS_LIKE_THIS,
        FeedbackType.NOT_RELEVANT,
        FeedbackType.WRONG_INSTRUMENT,
        FeedbackType.SELECT_TRACK,
    }
)
ATTRIBUTE_EVENTS = frozenset(
    {
        FeedbackType.WRONG_INSTRUMENT,
        FeedbackType.MORE_OF_ATTRIBUTE,
        FeedbackType.LESS_OF_ATTRIBUTE,
    }
)


class FeedbackEvent(FrozenModel):
    """A user's reaction to a result (base.md §8). Feedback never modifies the catalog."""

    event_id: NonEmptyStr
    search_session_id: NonEmptyStr
    query_id: NonEmptyStr
    track_id: NonEmptyStr | None = None
    event_type: FeedbackType
    attribute: NonEmptyStr | None = None
    value: bool | float | str | None = None
    free_text: NonEmptyStr | None = None
    timestamp: AwareDatetime

    @model_validator(mode="after")
    def _required_fields(self) -> Self:
        if self.event_type in TRACK_EVENTS and self.track_id is None:
            raise ValueError(f"{self.event_type} needs a track_id")
        if self.event_type in ATTRIBUTE_EVENTS and self.attribute is None:
            raise ValueError(f"{self.event_type} needs an attribute")
        return self


# --- Evidence ---------------------------------------------------------------------


class FieldMatch(FrozenModel):
    """A query term found in a catalog field. Lexical matches are not audio evidence."""

    field: NonEmptyStr
    term: NonEmptyStr
    source: DataSource
    kind: Literal["lexical", "tag"]


class TagMatch(FrozenModel):
    tag: NonEmptyStr
    source: DataSource


class SemanticEvidence(FrozenModel):
    """CLAP text-to-audio match. A similarity, never a probability or proof of an instrument."""

    prompt: NonEmptyStr
    raw_cosine: Annotated[float, Field(ge=-1.0, le=1.0)]
    normalized: UnitInterval | None = None
    rank: Annotated[int, Field(ge=1)]
    model_id: NonEmptyStr
    strength: MatchStrength
    query_kind: Literal["original", "expansion", "reference"] | None = None
    """Which query matched: the request text, a prompt expansion, or a liked track's audio."""


class AudioFeature(FrozenModel):
    name: NonEmptyStr
    value: float
    unit: str | None = None
    source: DataSource
    estimated: bool = True


class HumanLabel(FrozenModel):
    """A judgment made by listening (evaluation data only)."""

    attribute: NonEmptyStr
    value: JsonValue
    judge: NonEmptyStr
    basis: NonEmptyStr


class ConstraintResult(FrozenModel):
    constraint: HardConstraint
    status: ConstraintStatus
    evidence: list[NonEmptyStr] = []
    """What the decision was based on; empty when the status is unknown."""


class TrackEvidence(FrozenModel):
    """Everything known about why a track matched (base.md §8). Explanations use only this."""

    track_id: NonEmptyStr
    metadata_matches: list[FieldMatch] = []
    genre_matches: list[TagMatch] = []
    style_matches: list[TagMatch] = []
    semantic: SemanticEvidence | None = None
    retrieval_sources: list[RetrievalSource] = []
    known_audio_features: list[AudioFeature] = []
    human_labels: list[HumanLabel] = []
    constraint_results: list[ConstraintResult] = []
    uncertainty_flags: list[NonEmptyStr] = []


# --- Ranking ------------------------------------------------------------------------

Score = UnitInterval


class ScoreBreakdown(FrozenModel):
    """Normalized signals behind a ranking. `None` means "not computed", never "irrelevant"."""

    semantic: Score | None = None
    metadata: Score | None = None
    relationship: Score | None = None
    final: Score
    normalization: str | None = None
    weights_version: str | None = None

    @model_validator(mode="after")
    def _some_signal(self) -> Self:
        if self.semantic is None and self.metadata is None and self.relationship is None:
            raise ValueError("a score needs at least one available signal")
        return self


class SourceScore(FrozenModel):
    raw_score: float
    rank: Annotated[int, Field(ge=1)]


class RankedCandidate(FrozenModel):
    track_id: NonEmptyStr
    rank: Annotated[int, Field(ge=1)]
    score: ScoreBreakdown
    retrieval_sources: list[RetrievalSource]
    source_scores: dict[RetrievalSource, SourceScore] = {}
    constraint_results: list[ConstraintResult] = []
    evidence: TrackEvidence | None = None

    @model_validator(mode="after")
    def _sources_consistent(self) -> Self:
        if not self.retrieval_sources:
            raise ValueError("a candidate must come from at least one retriever")
        if unknown := set(self.source_scores) - set(self.retrieval_sources):
            raise ValueError(f"scores for retrievers that did not return it: {sorted(unknown)}")
        if self.evidence is not None and self.evidence.track_id != self.track_id:
            raise ValueError("evidence belongs to a different track")
        return self


class RetrievalTrace(FrozenModel):
    """Diagnostic record of one retrieval run. Not sent wholesale to the frontend."""

    mode: Literal["metadata_only", "semantic_only", "hybrid"]
    model_id: str | None = None
    config_versions: dict[str, str] = {}
    pool_size: Annotated[int, Field(ge=0)] = 0
    stage_counts: dict[str, int] = {}
    normalization_fallbacks: list[str] = []
    degraded: list[str] = []
    timings_ms: dict[str, float] = {}


class SearchOutcome(FrozenModel):
    kind: SearchOutcomeKind
    candidates: list[RankedCandidate] = []
    reasons: list[NonEmptyStr] = []
    clarification_question: NonEmptyStr | None = None
    degraded: list[NonEmptyStr] = []

    @model_validator(mode="after")
    def _kind_consistent(self) -> Self:
        if self.kind is not SearchOutcomeKind.OK and self.candidates:
            raise ValueError(f"a {self.kind} outcome has no candidates")
        if self.kind is SearchOutcomeKind.NO_CONFIDENT_MATCH and not self.reasons:
            raise ValueError("no_confident_match must say which constraints failed")
        needs_question = self.kind is SearchOutcomeKind.NEEDS_CLARIFICATION
        if needs_question != (self.clarification_question is not None):
            raise ValueError("clarification_question is set exactly for needs_clarification")
        ranks = [c.rank for c in self.candidates]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("candidate ranks must be 1..n in order")
        return self


class Explanation(FrozenModel):
    track_id: NonEmptyStr
    description: NonEmptyStr | None = None
    """`None` when the evidence is too thin to say anything grounded."""
    match_reasons: list[NonEmptyStr] = []
    generator: Literal["template", "llm"] = "template"


# --- Adapter results -----------------------------------------------------------------


class AudioProbeResult(FrozenModel):
    ok: bool
    duration_seconds: Annotated[float, Field(ge=0.0)] | None = None
    sample_rate: Annotated[int, Field(gt=0)] | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def _error_when_not_ok(self) -> Self:
        if self.ok == (self.error_code is not None):
            raise ValueError("error_code is set exactly when the probe failed")
        return self


T = TypeVar("T", bound=BaseModel)


class LLMResult(FrozenModel, Generic[T]):
    """Outcome of one structured LLM call. `parsed` is None when the call failed validation."""

    parsed: T | None = None
    raw_text: str | None = None
    model_id: str | None = None
    latency_ms: Annotated[float, Field(ge=0.0)] | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def _parsed_or_error(self) -> Self:
        if (self.parsed is None) == (self.error_code is None):
            raise ValueError("exactly one of parsed and error_code is set")
        return self
