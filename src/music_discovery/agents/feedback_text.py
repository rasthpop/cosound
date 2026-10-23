"""Free-text feedback -> typed attribute events (base §8; Agent C).

"More electronic, less acoustic" becomes two events, MORE_OF_ATTRIBUTE electronic and
LESS_OF_ATTRIBUTE acoustic, which then go through the same rule table as button feedback.

Lexicon path (default and fallback): the text is split into clauses at punctuation and
"and"/"but"; in each clause the cue decides the direction ("more", "extra" -> more; "less",
"fewer", "not", "no", "without", "too" -> less; a bare attribute or a comparative such as
"darker" -> more) and every lexicon term in it becomes one event. Negation in feedback is
always soft: feedback never creates a hard constraint.

Optional LLM path (`task="feedback"`): the model returns (direction, attribute) pairs; every
attribute must resolve through the lexicon, otherwise the whole answer is rejected and the
lexicon path is used. Only the feedback text is sent. Nothing mappable -> rejected with a
reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from music_discovery.agents.feedback_rules import resolve_attribute
from music_discovery.agents.lexicon_loader import PUNCTUATION, Lexicon, tokenize
from music_discovery.agents.llm_query_interpreter import PROMPT_PATH as QUERY_PROMPT
from music_discovery.agents.llm_query_interpreter import load_prompt, vocabulary
from music_discovery.domain.enums import FeedbackType
from music_discovery.domain.protocols import StructuredLLM
from music_discovery.domain.schemas import FeedbackEvent

PROMPT_PATH = QUERY_PROMPT.parent / "feedback.md"
TASK = "feedback"
MORE_CUES = frozenset({"more", "extra", "plus", "increase", "add", "even"})
LESS_CUES = frozenset(
    {"less", "fewer", "not", "no", "without", "too", "reduce", "minus", "avoid", "lose"}
)
SPLITTERS = frozenset({"and", "but", "also", "though", *PUNCTUATION})
Direction = Literal["more", "less"]
EVENT_TYPE = {"more": FeedbackType.MORE_OF_ATTRIBUTE, "less": FeedbackType.LESS_OF_ATTRIBUTE}


class DraftAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: Direction
    attribute: str


class FeedbackDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjustments: list[DraftAdjustment]


@dataclass(frozen=True)
class FeedbackText:
    accepted: bool
    events: list[FeedbackEvent] = field(default_factory=list)
    reason: str | None = None
    interpreter: Literal["deterministic", "llm"] = "deterministic"
    llm_fallback_reason: str | None = None


class FeedbackTextNormalizer:
    def __init__(self, lexicon: Lexicon, llm: StructuredLLM | None = None) -> None:
        self._lexicon = lexicon
        self._llm = llm
        prompt = load_prompt(PROMPT_PATH)
        self.prompt_version = prompt.version
        self._system = prompt.text.replace("{{vocabulary}}", vocabulary(lexicon))

    def normalize(
        self,
        text: str,
        *,
        session_id: str,
        query_id: str,
        event_id: str,
        timestamp: datetime,
    ) -> FeedbackText:
        """Events get ids `{event_id}.{n}` and carry the original text as `free_text`."""
        if not text.strip():
            return FeedbackText(False, reason="empty feedback")
        llm_reason = None
        pairs: list[tuple[Direction, str]] | None = None
        interpreter: Literal["deterministic", "llm"] = "deterministic"
        if self._llm is not None:
            pairs, llm_reason = self._read_llm(text)
            interpreter = "llm" if pairs else "deterministic"
        if not pairs:
            pairs = self.read(text)
        if not pairs:
            return FeedbackText(
                False,
                reason="no known attribute in the feedback",
                llm_fallback_reason=llm_reason,
            )
        events = [
            FeedbackEvent(
                event_id=f"{event_id}.{n}",
                search_session_id=session_id,
                query_id=query_id,
                event_type=EVENT_TYPE[direction],
                attribute=attribute,
                free_text=text.strip(),
                timestamp=timestamp,
            )
            for n, (direction, attribute) in enumerate(pairs, start=1)
        ]
        return FeedbackText(True, events, None, interpreter, llm_reason)

    def read(self, text: str) -> list[tuple[Direction, str]]:
        """Lexicon reading: (direction, canonical term) per mentioned attribute, in order."""
        found: dict[str, Direction] = {}
        for clause in _clauses(tokenize(text)):
            direction: Direction = "more"
            if any(t in LESS_CUES for t in clause):
                direction = "less"
            for term in self._terms(clause):
                found[term] = direction
        return [(d, t) for t, d in found.items()]

    def _terms(self, tokens: Sequence[str]) -> list[str]:
        terms: list[str] = []
        i = 0
        while i < len(tokens):
            for n in range(min(self._lexicon.max_phrase_length, len(tokens) - i), 0, -1):
                entry = self._lexicon.entries.get(tuple(tokens[i : i + n]))
                if entry is not None:
                    terms.append(entry.canonical)
                    i += n
                    break
            else:
                i += 1
        return list(dict.fromkeys(terms))

    def _read_llm(self, text: str) -> tuple[list[tuple[Direction, str]] | None, str | None]:
        assert self._llm is not None
        result = self._llm.generate(
            task=TASK, system=self._system, user=text.strip(), schema=FeedbackDraft
        )
        if result.parsed is None:
            return None, f"llm_{result.error_code}"
        pairs: list[tuple[Direction, str]] = []
        for adjustment in result.parsed.adjustments:
            resolved = resolve_attribute(adjustment.attribute, None, self._lexicon)
            if resolved is None:
                return None, f"unknown attribute {adjustment.attribute!r}"
            pairs.append((adjustment.direction, resolved.value))
        if not pairs:
            return None, "llm_found_nothing"
        return list(dict.fromkeys(pairs)), None


def _clauses(tokens: Sequence[str]) -> list[list[str]]:
    clauses: list[list[str]] = [[]]
    for token in tokens:
        if token in SPLITTERS:
            clauses.append([])
        else:
            clauses[-1].append(token)
    return [c for c in clauses if c]
