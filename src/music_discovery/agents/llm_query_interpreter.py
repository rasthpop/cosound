"""Optional LLM query interpreter for Agent A (OpenRouter free models via `StructuredLLM`).

The model returns a `SearchSpecificationDraft`. The draft is accepted only if it survives:

1. the adapter's schema validation (invalid JSON / schema violations -> error result);
2. a track-id check: any `reference_track_ids` not already in the session are hallucinated;
3. a constraint check: every hard constraint (and a hard vocals choice) must also be found by
   the deterministic parser, which only sets them on explicit cues; anything else is a soft
   preference escalated to a hard one;
4. lexicon normalization: values are mapped to canonical lexicon terms (in the lexicon's
   category); values outside the lexicon are dropped and noted, so no artist or title the
   model mentions reaches the spec;
5. `SearchSpecification` validation of the assembled spec.

Hard constraints and the clarification decision always come from the deterministic parse.
Any failure returns a reason instead of a spec, and Agent A falls back to the parser.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from music_discovery.agents.lexicon_loader import CATEGORIES, Category, Lexicon, phrase
from music_discovery.agents.query_parser import PREFERENCE_FIELDS
from music_discovery.domain.errors import AgentOutputError, ContradictoryConstraintsError
from music_discovery.domain.protocols import StructuredLLM
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    SearchSpecification,
    VocalPreference,
    WeightedPreference,
)
from music_discovery.retrieval.prompt_builder import with_prompts

PROMPT_PATH = Path(__file__).parent / "prompts" / "query.md"
TASK = "query"
HARD_VOCALS: frozenset[VocalPreference] = frozenset({"required", "excluded"})

Weight = Annotated[float, Field(ge=0.0, le=1.0)]
PreferenceCategory = Literal["mood", "instrument", "genre", "tempo", "energy", "texture", "era"]


class _Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftPreference(_Draft):
    category: PreferenceCategory
    value: str
    weight: Weight
    source_span: str


class DraftNegative(_Draft):
    value: str
    weight: Weight
    source_span: str


class DraftConstraint(_Draft):
    attribute: Literal["vocals", "instrument", "genre", "era", "tempo", "duration"]
    operator: Literal["required", "excluded", "range"]
    value: str | None
    low: float | None
    high: float | None
    cue: str


class SearchSpecificationDraft(_Draft):
    """What the model may say. Every field is required, so strict JSON schema mode applies."""

    preferences: list[DraftPreference]
    negative_preferences: list[DraftNegative]
    vocals: Literal["required", "preferred", "avoided", "excluded", "unspecified"]
    hard_constraints: list[DraftConstraint]
    reference_track_ids: list[str]
    needs_clarification: bool
    clarification_question: str | None


@dataclass(frozen=True)
class LLMInterpretation:
    spec: SearchSpecification | None
    fallback_reason: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


def load_prompt(path: Path = PROMPT_PATH) -> Prompt:
    """A prompt file: `---` front matter with `prompt_version`, then the prompt body."""
    raw = path.read_text()
    _, front, body = raw.split("---\n", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    return Prompt(version=meta["prompt_version"].strip(), text=body.strip())


class LLMQueryInterpreter:
    def __init__(
        self, llm: StructuredLLM, lexicon: Lexicon, *, prompt: Prompt | None = None
    ) -> None:
        self._llm = llm
        self._lexicon = lexicon
        self._prompt = prompt or load_prompt()
        self._system = self._prompt.text.replace("{{vocabulary}}", vocabulary(lexicon))

    @property
    def prompt_version(self) -> str:
        return self._prompt.version

    def interpret(
        self,
        query: str,
        baseline: SearchSpecification,
        *,
        known_track_ids: Collection[str] = (),
    ) -> LLMInterpretation:
        """`baseline` is the deterministic parse of the same text; only the text is sent."""
        result = self._llm.generate(
            task=TASK, system=self._system, user=query, schema=SearchSpecificationDraft
        )
        if result.parsed is None:
            return LLMInterpretation(None, f"llm_{result.error_code}", result.model_id)
        draft, model_id = result.parsed, result.model_id
        if set(draft.reference_track_ids) - set(known_track_ids):
            return LLMInterpretation(None, "hallucinated_track_ids", model_id)
        if not self._constraints_backed(draft, baseline):
            return LLMInterpretation(None, "soft_to_hard_escalation", model_id)
        try:
            spec = self._assemble(draft, baseline, model_id)
        except (ValidationError, ContradictoryConstraintsError, AgentOutputError):
            return LLMInterpretation(None, "inconsistent_output", model_id)
        return LLMInterpretation(spec, None, model_id)

    def _assemble(
        self, draft: SearchSpecificationDraft, baseline: SearchSpecification, model_id: str | None
    ) -> SearchSpecification:
        notes = list(baseline.uncertainties)
        positive: dict[Category, dict[str, WeightedPreference]] = {c: {} for c in PREFERENCE_FIELDS}
        for p in draft.preferences:
            mapped = self._canonical(p.value, notes)
            if mapped is None:
                continue
            category, canonical = mapped
            if category == "vocals":
                continue  # vocals are read from `draft.vocals` only
            _keep_strongest(positive[category], canonical, p.weight, p.source_span)
        negative: dict[str, WeightedPreference] = {}
        for n in draft.negative_preferences:
            mapped = self._canonical(n.value, notes)
            if mapped is not None and mapped[0] != "vocals":
                _keep_strongest(negative, mapped[1], n.weight, n.source_span)
        # the parser's negatives stay: hard exclusions rely on them for scoring
        for kept in baseline.negative_preferences:
            negative.setdefault(kept.value, kept)
        if set(negative) & {v for prefs in positive.values() for v in prefs}:
            raise AgentOutputError("a value is both preferred and negative")

        data: dict[str, object] = {
            PREFERENCE_FIELDS[c]: list(prefs.values()) for c, prefs in positive.items()
        }
        data |= {
            "original_query": baseline.original_query,
            "negative_preferences": list(negative.values()),
            "vocal_preferences": _vocals(draft, baseline),
            "hard_constraints": baseline.hard_constraints,
            "uncertainties": list(dict.fromkeys(notes)),
            "interpreter": "llm",
            "interpreter_model": model_id,
        }
        return with_prompts(SearchSpecification.model_validate(data))

    def _constraints_backed(
        self, draft: SearchSpecificationDraft, baseline: SearchSpecification
    ) -> bool:
        """Every hard choice in the draft is one the deterministic parser also made."""
        if draft.vocals in HARD_VOCALS and draft.vocals != baseline.vocal_preferences:
            return False
        known = {_key(c.attribute, c.operator, c.value) for c in baseline.hard_constraints}
        for c in draft.hard_constraints:
            value = c.value
            entry = self._lexicon.entries.get(phrase(value)) if value else None
            canonical = entry.canonical if entry is not None else value
            key = _key(ConstraintAttribute(c.attribute), ConstraintOperator(c.operator), canonical)
            if key not in known:
                return False
        return True

    def _canonical(self, value: str, notes: list[str]) -> tuple[Category, str] | None:
        entry = self._lexicon.entries.get(phrase(value))
        if entry is None:
            notes.append(f"'{value}' is not in the lexicon; left to the audio search")
            return None
        return entry.category, entry.canonical


def _keep_strongest(
    target: dict[str, WeightedPreference], value: str, weight: float, span: str
) -> None:
    if value not in target or target[value].weight < weight:
        target[value] = WeightedPreference(value=value, weight=weight, source_span=span or None)


def _vocals(draft: SearchSpecificationDraft, baseline: SearchSpecification) -> VocalPreference:
    if baseline.vocal_preferences in HARD_VOCALS:
        return baseline.vocal_preferences
    return draft.vocals


Key = tuple[ConstraintAttribute, ConstraintOperator, str | None]


def _key(attribute: ConstraintAttribute, operator: ConstraintOperator, value: str | None) -> Key:
    """Ranges match by attribute only: the parser's bounds are the ones kept."""
    if operator is ConstraintOperator.RANGE or not value:
        return attribute, operator, None
    return attribute, operator, value.casefold()


def vocabulary(lexicon: Lexicon) -> str:
    by_category: Mapping[str, list[str]] = {c: [] for c in CATEGORIES}
    for category, canonical in lexicon.synonyms:
        by_category[category].append(canonical)
    return "\n".join(
        f"- {category}: {', '.join(sorted(set(values)))}"
        for category, values in by_category.items()
        if values and category != "vocals"
    )
