"""Agent A — query understanding: request text + session state -> SearchSpecification (base §6).

The deterministic parser reads the request; this agent adds the session context:

- a query that opens with a follow-up cue ("more upbeat", "but without vocals"), or that
  answers a pending clarification question, refines the previous spec instead of replacing it;
- the refinement extends the previous `original_query` with the follow-up's own words (so
  CLAP and lexical matching see both) and keeps the track references, exclusions and every
  hard constraint; what the new text states wins over earlier soft wording
  (a new "less electronic" removes an earlier "electronic" preference);
- a refinement that contradicts an earlier hard constraint ("no vocals", then "with vocals")
  is not resolved by guessing: the previous spec comes back with a clarification question.

Any other query starts a new search. With an `LLMQueryInterpreter`, the text is read by the
LLM first and by the deterministic parser on any failure (`spec.interpreter` records which);
the parser's reading also decides hard constraints and clarification on both paths.

Track ids only ever come from the previous spec (filled in by feedback), never from the query
text. The agent does not retrieve, embed or rank, and every spec it returns has passed
`SearchSpecification` validation.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from music_discovery.agents.lexicon_loader import PUNCTUATION, Lexicon, Phrase, tokenize
from music_discovery.agents.llm_query_interpreter import LLMQueryInterpreter
from music_discovery.agents.query_parser import QueryParser
from music_discovery.domain.errors import ContradictoryConstraintsError
from music_discovery.domain.models import SearchSession
from music_discovery.domain.schemas import (
    ConstraintOperator,
    HardConstraint,
    SearchSpecification,
    VocalPreference,
    WeightedPreference,
)
from music_discovery.retrieval.prompt_builder import with_prompts

PREFERENCE_FIELDS = (
    "mood_preferences",
    "instrument_preferences",
    "genre_preferences",
    "tempo_preferences",
    "energy_preferences",
    "texture_preferences",
    "era_preferences",
)
CARRIED_FIELDS = (
    "reference_track_ids",
    "negative_reference_track_ids",
    "excluded_track_ids",
    "diversity",
)
"""Set by feedback on earlier turns, never by query text."""
VOCALS_WANTED: frozenset[VocalPreference] = frozenset({"required", "preferred"})
VOCALS_UNWANTED: frozenset[VocalPreference] = frozenset({"avoided", "excluded"})
REFINEMENT_NOTE = "read as a refinement of the previous search"
NOTHING_NEW_NOTE = "nothing in the follow-up mapped to a known attribute; previous search kept"
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryInterpretation:
    spec: SearchSpecification
    llm_fallback_reason: str | None = None
    """Why the LLM reading was not used; None when it was used or no LLM is configured."""


class QueryAgent:
    def __init__(self, lexicon: Lexicon, llm: LLMQueryInterpreter | None = None) -> None:
        self._parser = QueryParser(lexicon)
        self._llm = llm
        self._follow_up = lexicon.cues.follow_up
        self._longest_cue = max((len(c) for c in self._follow_up), default=0)

    @property
    def lexicon_version(self) -> str:
        return self._parser.lexicon_version

    def interpret(self, query: str, state: SearchSession | None = None) -> SearchSpecification:
        """Raises ValueError for an empty query; contradictions become clarification specs."""
        return self.interpret_traced(query, state).spec

    def interpret_traced(
        self, query: str, state: SearchSession | None = None
    ) -> QueryInterpretation:
        previous = state.current_spec if state is not None else None
        parsed, reason = self._read(query, previous)
        if previous is None or not self.is_follow_up(query, previous):
            return QueryInterpretation(parsed, reason)
        return QueryInterpretation(_refine(previous, parsed), reason)

    def _read(
        self, query: str, previous: SearchSpecification | None
    ) -> tuple[SearchSpecification, str | None]:
        parsed = self._parser.parse(query)
        if self._llm is None or parsed.needs_clarification:
            return parsed, None
        known = previous.reference_track_ids if previous is not None else []
        outcome = self._llm.interpret(query, parsed, known_track_ids=known)
        if outcome.spec is None:
            log.info("llm query interpretation rejected: %s", outcome.fallback_reason)
            return parsed, outcome.fallback_reason
        return outcome.spec, None

    def is_follow_up(self, query: str, previous: SearchSpecification) -> bool:
        """A pending clarification is always answered; otherwise the opening words decide."""
        if previous.needs_clarification:
            return True
        words: Phrase = tuple(t for t in tokenize(query) if t not in PUNCTUATION)
        return any(
            words[:n] in self._follow_up for n in range(1, min(self._longest_cue, len(words)) + 1)
        )


def _refine(previous: SearchSpecification, parsed: SearchSpecification) -> SearchSpecification:
    version = previous.spec_version + 1
    if parsed.clarification_question is not None:
        return _clarify(previous, parsed, version, parsed.clarification_question)

    stated_positive = {p.value.casefold() for f in PREFERENCE_FIELDS for p in getattr(parsed, f)}
    stated_negative = {p.value.casefold() for p in parsed.negative_preferences}
    data: dict[str, object] = {
        f: _overlay(getattr(previous, f), getattr(parsed, f), drop=stated_negative)
        for f in PREFERENCE_FIELDS
    }
    data["negative_preferences"] = _overlay(
        previous.negative_preferences, parsed.negative_preferences, drop=stated_positive
    )
    data["vocal_preferences"] = _vocals(previous, parsed)
    data["hard_constraints"] = _constraints(previous.hard_constraints, parsed.hard_constraints)
    data |= {f: getattr(previous, f) for f in CARRIED_FIELDS}
    nothing_new = not stated_positive and not stated_negative and not parsed.hard_constraints
    nothing_new = nothing_new and parsed.vocal_preferences == "unspecified"
    data |= {
        "spec_version": version,
        "interpreter": parsed.interpreter,
        "interpreter_model": parsed.interpreter_model,
        "original_query": _extend(previous.original_query, parsed.original_query),
        "uncertainties": _notes(previous, parsed, nothing_new),
    }
    try:
        return with_prompts(SearchSpecification.model_validate(data))
    except ContradictoryConstraintsError as error:
        return _clarify(previous, parsed, version, _conflict_question(error))


def _extend(original: str, follow_up: str) -> str:
    """The user's own words only: the follow-up appended as a new sentence."""
    separator = " " if original[-1] in PUNCTUATION else ". "
    return f"{original}{separator}{follow_up}"


def _overlay(
    old: Sequence[WeightedPreference], new: Sequence[WeightedPreference], *, drop: set[str]
) -> list[WeightedPreference]:
    """Earlier preferences, minus what the follow-up negates, with the follow-up's weights."""
    merged = {p.value.casefold(): p for p in old if p.value.casefold() not in drop}
    merged |= {p.value.casefold(): p for p in new}
    return list(merged.values())


def _vocals(previous: SearchSpecification, parsed: SearchSpecification) -> VocalPreference:
    """New wording wins, except that soft wording never weakens an earlier hard choice.

    A soft follow-up pointing the other way is returned as stated, so validation reports the
    contradiction with the earlier hard constraint instead of it being silently overridden.
    """
    new, old = parsed.vocal_preferences, previous.vocal_preferences
    if new == "unspecified":
        return old
    old_is_hard = old in ("required", "excluded")
    new_is_hard = new in ("required", "excluded")
    same_direction = (new in VOCALS_WANTED) == (old in VOCALS_WANTED)
    if old_is_hard and not new_is_hard and same_direction:
        return old
    return new


def _constraints(
    old: Sequence[HardConstraint], new: Sequence[HardConstraint]
) -> list[HardConstraint]:
    """All earlier constraints are kept; a newly stated range replaces the earlier one."""
    new_ranges = {c.attribute for c in new if c.operator is ConstraintOperator.RANGE}
    replaced = [
        c for c in old if c.operator is ConstraintOperator.RANGE and c.attribute in new_ranges
    ]
    kept = [c for c in old if c not in replaced]
    return list(dict.fromkeys([*kept, *new]))


def _notes(
    previous: SearchSpecification, parsed: SearchSpecification, nothing_new: bool
) -> list[str]:
    notes: Iterable[str] = [*previous.uncertainties, REFINEMENT_NOTE, *parsed.uncertainties]
    if nothing_new:
        notes = [*notes, NOTHING_NEW_NOTE]
    return list(dict.fromkeys(notes))


def _clarify(
    previous: SearchSpecification, parsed: SearchSpecification, version: int, question: str
) -> SearchSpecification:
    """The previous spec, unchanged apart from the question: nothing is guessed."""
    data = previous.model_dump()
    data |= {
        "spec_version": version,
        "needs_clarification": True,
        "clarification_question": question,
        "uncertainties": _notes(previous, parsed, nothing_new=False),
    }
    return SearchSpecification.model_validate(data)


def _conflict_question(error: ContradictoryConstraintsError) -> str:
    subject = error.details.get("value") or error.details.get("attribute") or "this"
    return (
        f"Your follow-up conflicts with an earlier requirement about {subject}. "
        "Should the earlier requirement still apply?"
    )
