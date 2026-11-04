"""LLM query interpreter for Agent A (OpenRouter free models via `StructuredLLM`, ADR-0007).

The LLM reads the request first; the deterministic parser only runs when this returns no spec.
The model answers with a `SearchSpecificationDraft`, which is accepted only if it survives:

1. the adapter's schema validation (invalid JSON / schema violations -> error result);
2. a track-id check: any `reference_track_ids` not already in the session are hallucinated;
3. a hard-constraint check against the request text: the cue and the value must appear verbatim,
   and the cue must say so explicitly (a negation, "only", "must", or a number). "With a flute"
   appears verbatim too, but it stays soft. A hard vocals choice needs such a constraint;
4. value normalization: values map to canonical lexicon terms when they can. Others are kept only
   when the value and its `source_span` appear verbatim in the request, and noted in
   `uncertainties`, so no artist or title the model made up reaches the spec;
5. CLAP prompt checks: at most `MAX_SEMANTIC_PROMPTS`, short, no ruled-out value (audio search does
   not understand negation, so "avoids metal" pulls metal closer), and no capitalized name absent
   from the request. The name check is a heuristic: prompts only steer audio search and are never
   requirements;
6. `SearchSpecification` validation of the assembled spec.

A contradiction in the validated spec becomes a clarification question. Any other failure returns
a reason instead of a spec, and Agent A falls back to the parser.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from music_discovery.agents.lexicon_loader import (
    CATEGORIES,
    PUNCTUATION,
    Category,
    Lexicon,
    Phrase,
    phrase,
    tokenize,
)
from music_discovery.agents.query_parser import PREFERENCE_FIELDS
from music_discovery.domain.errors import AgentOutputError, ContradictoryConstraintsError
from music_discovery.domain.protocols import StructuredLLM
from music_discovery.domain.schemas import (
    MAX_SEMANTIC_PROMPTS,
    HardConstraint,
    SearchSpecification,
    VocalPreference,
    WeightedPreference,
)
from music_discovery.retrieval.prompt_builder import with_prompts

PROMPT_PATH = Path(__file__).parent / "prompts" / "query.md"
TASK = "query"
HARD_VOCALS: frozenset[VocalPreference] = frozenset({"required", "excluded"})
SOFT_CUES: frozenset[str] = frozenset({"less", "fewer"})
"""Negation in the lexicon's cue list that never makes a constraint hard."""
EXCLUSION_WORDS: frozenset[str] = frozenset(
    {
        "but",  # "anything but metal"
        "don",  # "don't": the tokenizer splits it into "don" + "t"
        "dont",
        "except",
        "excluding",
        "hate",
        "nothing",
        "none",
        "remove",
        "rid",  # "get rid of"
        "skip",
    }
)
"""Explicit exclusions the parser's cue list lacks; this wording is why the LLM reads first."""
REQUIREMENT_WORDS: frozenset[str] = frozenset({"need", "needs", "require", "required", "requires"})
MAX_PROMPT_WORDS = 15
MAX_QUESTION_CHARS = 200

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
    semantic_prompts: list[str]
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
        *,
        known_track_ids: Collection[str] = (),
    ) -> LLMInterpretation:
        """Only the query text is sent. No spec comes back when the answer is rejected."""
        result = self._llm.generate(
            task=TASK, system=self._system, user=query, schema=SearchSpecificationDraft
        )
        if result.parsed is None:
            return LLMInterpretation(None, f"llm_{result.error_code}", result.model_id)
        draft, model_id = result.parsed, result.model_id
        if set(draft.reference_track_ids) - set(known_track_ids):
            return LLMInterpretation(None, "hallucinated_track_ids", model_id)
        try:
            spec = self._assemble(query, draft, model_id)
        except _UnbackedConstraintError:
            return LLMInterpretation(None, "soft_to_hard_escalation", model_id)
        except ContradictoryConstraintsError as error:
            return LLMInterpretation(_contradiction(query, error, model_id), None, model_id)
        except (ValidationError, AgentOutputError):
            return LLMInterpretation(None, "inconsistent_output", model_id)
        return LLMInterpretation(spec, None, model_id)

    def _assemble(
        self, query: str, draft: SearchSpecificationDraft, model_id: str | None
    ) -> SearchSpecification:
        text = query.strip()
        if draft.needs_clarification:
            return _clarification(text, draft.clarification_question, model_id)
        tokens = _words(text)
        notes: list[str] = []
        positive: dict[Category, dict[str, WeightedPreference]] = {c: {} for c in PREFERENCE_FIELDS}
        for p in draft.preferences:
            mapped = self._resolve(p.value, p.source_span, tokens, notes)
            if mapped is None:
                continue
            category, value = mapped
            if category == "vocals":
                continue  # vocals are read from `draft.vocals` only
            _keep_strongest(positive[category or p.category], value, p.weight, p.source_span)
        negative: dict[str, WeightedPreference] = {}
        for n in draft.negative_preferences:
            mapped = self._resolve(n.value, n.source_span, tokens, notes)
            if mapped is not None and mapped[0] != "vocals":
                _keep_strongest(negative, mapped[1], n.weight, n.source_span)
        constraints = [self._backed(c, tokens) for c in draft.hard_constraints]
        for constraint, source in zip(constraints, draft.hard_constraints, strict=True):
            if constraint.operator == "excluded" and constraint.value is not None:
                # hard exclusions also rely on a negative preference for scoring
                weight = self._lexicon.cues.negative_weight
                _keep_strongest(negative, constraint.value, weight, source.cue)
        if set(negative) & {v for prefs in positive.values() for v in prefs}:
            raise AgentOutputError("a value is both preferred and negative")

        data: dict[str, object] = {
            PREFERENCE_FIELDS[c]: list(prefs.values()) for c, prefs in positive.items()
        }
        data |= {
            "original_query": text,
            "negative_preferences": list(negative.values()),
            "vocal_preferences": _vocals(draft.vocals, constraints),
            "hard_constraints": list(dict.fromkeys(constraints)),
            "uncertainties": list(dict.fromkeys(notes)),
            "interpreter": "llm",
            "interpreter_model": model_id,
        }
        prompts = _clean_prompts(draft.semantic_prompts, tokens, notes, ruled_out=list(negative))
        data["uncertainties"] = list(dict.fromkeys(notes))
        spec = SearchSpecification.model_validate(data)
        if not prompts:
            return with_prompts(spec)
        return SearchSpecification.model_validate(data | {"semantic_prompts": prompts})

    def _resolve(
        self, value: str, span: str, tokens: Sequence[str], notes: list[str]
    ) -> tuple[Category | None, str] | None:
        """(lexicon category, canonical term), or (None, value) for the request's own words."""
        entry = self._lexicon.entries.get(phrase(value))
        if entry is not None:
            return entry.category, entry.canonical
        if _contains(tokens, _words(value)) and _contains(tokens, _words(span)):
            own = " ".join(value.split()).casefold()
            notes.append(f"'{own}' is not in the lexicon; kept as the request's own words")
            return None, own
        notes.append(f"'{value}' is not in the lexicon; left to the audio search")
        return None

    def _backed(self, c: DraftConstraint, tokens: Sequence[str]) -> HardConstraint:
        """The constraint in domain form; raises when the request does not state it explicitly."""
        cue = _words(c.cue)
        if not _contains(tokens, cue) or not self._explicit(c.operator, cue):
            raise _UnbackedConstraintError
        if c.operator == "range":
            return HardConstraint.model_validate(
                {"attribute": c.attribute, "operator": c.operator, "range": (c.low, c.high)}
            )
        if c.attribute == "vocals":
            if not self._mentions_vocals(tokens):
                raise _UnbackedConstraintError
            return HardConstraint.model_validate({"attribute": "vocals", "operator": c.operator})
        if not c.value:
            raise _UnbackedConstraintError
        return HardConstraint.model_validate(
            {
                "attribute": c.attribute,
                "operator": c.operator,
                "value": self._stated_value(c.value, tokens),
            }
        )

    def _explicit(self, operator: str, cue: Sequence[str]) -> bool:
        cues = self._lexicon.cues
        if operator == "range":
            numbers = {n for n in cues.numbers if n not in (("a",), ("an",))}
            return any(any(ch.isdigit() for ch in word) for word in cue) or any(
                _contains(cue, n) for n in numbers
            )
        hard = [*cues.hard, *cues.emphasis]
        if operator == "required":
            return any(_contains(cue, c) for c in hard) or bool(set(cue) & REQUIREMENT_WORDS)
        negations = [c for c in cues.negation if not set(c) & SOFT_CUES]
        return any(_contains(cue, c) for c in [*negations, *hard]) or bool(
            set(cue) & EXCLUSION_WORDS
        )

    def _mentions_vocals(self, tokens: Sequence[str]) -> bool:
        phrases = (p for p, e in self._lexicon.entries.items() if e.category == "vocals")
        return any(_contains(tokens, p) for p in phrases)

    def _stated_value(self, value: str, tokens: Sequence[str]) -> str:
        """Canonical term or casefolded words, only if the request says it or a synonym of it."""
        entry = self._lexicon.entries.get(phrase(value))
        if entry is None:
            if not _contains(tokens, _words(value)):
                raise _UnbackedConstraintError
            return " ".join(value.split()).casefold()
        phrases = (p for p, e in self._lexicon.entries.items() if e.canonical == entry.canonical)
        if not any(_contains(tokens, p) for p in phrases):
            raise _UnbackedConstraintError
        return entry.canonical


class _UnbackedConstraintError(Exception):
    """A hard constraint the request does not state explicitly."""


def _words(text: str) -> Phrase:
    return tuple(t for t in tokenize(text) if t not in PUNCTUATION)


def _contains(tokens: Sequence[str], words: Sequence[str]) -> bool:
    """`words` as a contiguous run of `tokens`. Empty never matches."""
    n = len(words)
    return n > 0 and any(
        tuple(tokens[i : i + n]) == tuple(words) for i in range(len(tokens) - n + 1)
    )


def _keep_strongest(
    target: dict[str, WeightedPreference], value: str, weight: float, span: str
) -> None:
    if value not in target or target[value].weight < weight:
        target[value] = WeightedPreference(value=value, weight=weight, source_span=span or None)


def _vocals(said: VocalPreference, constraints: Sequence[HardConstraint]) -> VocalPreference:
    """A hard choice needs its constraint; a stated constraint makes the choice hard."""
    hard: VocalPreference | None = None
    for c in constraints:
        if c.attribute == "vocals":
            hard = "excluded" if c.operator == "excluded" else "required"
    if hard is None:
        if said in HARD_VOCALS:
            raise _UnbackedConstraintError
        return said
    if said in ("preferred", "required") and hard == "excluded":
        return said  # both directions at once: validation reports the contradiction
    if said in ("avoided", "excluded") and hard == "required":
        return said
    return hard


def _clean_prompts(
    prompts: Sequence[str], tokens: Sequence[str], notes: list[str], *, ruled_out: Sequence[str]
) -> list[str]:
    """Prompts safe to send to audio search; anything else is noted and left out."""
    kept: dict[str, str] = {}
    for prompt in prompts:
        text = " ".join(prompt.split())
        words = text.split()
        names = [w for w in words[1:] if w[:1].isupper() and not _contains(tokens, _words(w))]
        if not words:
            continue
        banned = any(_contains(_words(text), _words(value)) for value in ruled_out)
        if len(words) > MAX_PROMPT_WORDS or names or banned:
            notes.append(f"prompt left out of the audio search: '{text[:60]}'")
            continue
        kept.setdefault(text.casefold(), text)
    return list(kept.values())[:MAX_SEMANTIC_PROMPTS]


def _clarification(text: str, question: str | None, model_id: str | None) -> SearchSpecification:
    asked = (question or "").strip()
    if not asked or len(asked) > MAX_QUESTION_CHARS:
        raise AgentOutputError("a clarification needs a short question")
    return SearchSpecification(
        original_query=text,
        needs_clarification=True,
        clarification_question=asked,
        interpreter="llm",
        interpreter_model=model_id,
    )


def _contradiction(
    query: str, error: ContradictoryConstraintsError, model_id: str | None
) -> SearchSpecification:
    subject = error.details.get("value") or error.details.get("attribute") or "this"
    return _clarification(
        query.strip(),
        f"Your request both asks for and rules out {subject}. Which do you want?",
        model_id,
    )


def vocabulary(lexicon: Lexicon) -> str:
    by_category: Mapping[str, list[str]] = {c: [] for c in CATEGORIES}
    for category, canonical in lexicon.synonyms:
        by_category[category].append(canonical)
    return "\n".join(
        f"- {category}: {', '.join(sorted(set(values)))}"
        for category, values in by_category.items()
        if values and category != "vocals"
    )
