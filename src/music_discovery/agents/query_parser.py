"""Deterministic query parser: request text -> SearchSpecification (base.md §5.3, §6).

The fallback and evaluation baseline for Agent A. Four passes over the tokens:

1. numeric ranges ("under three minutes", "before 1990", "over 120 bpm") -> hard ranges;
2. longest-match phrase spotting over the lexicon and the cue lists;
3. a left-to-right walk that attaches cues to the attribute phrase they govern:
   - a negation cue covers the next attribute phrase of its clause only ("or"/"nor" extend
     it: "no drums or bass");
   - an intensifier scales the phrase it directly precedes ("slightly dark");
   - "with"/"featuring" raises the next instrument ("with a flute");
   - a hard cue ("only", "strictly", "must") right before or after a phrase makes it a
     requirement; emphasis after a negated phrase ("at all") makes the exclusion hard;
4. assembly: soft preferences, negative preferences, hard constraints and vocals, with
   contradictions turned into a clarification question instead of a guess.

Hard constraints come only from explicit cues: "Something chill with a flute" yields two soft
preferences and no constraint. Words that look musical but are not in the lexicon are listed
in `uncertainties`; CLAP still sees them through the original query.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from music_discovery.agents.lexicon_loader import (
    PUNCTUATION,
    Category,
    Entry,
    Lexicon,
    Phrase,
    tokenize,
)
from music_discovery.domain.schemas import (
    Bound,
    ConstraintAttribute,
    ConstraintOperator,
    HardConstraint,
    SearchSpecification,
    VocalPreference,
    WeightedPreference,
)
from music_discovery.retrieval.metadata_retriever import era_range
from music_discovery.retrieval.prompt_builder import with_prompts

PREFERENCE_FIELDS: dict[Category, str] = {
    "mood": "mood_preferences",
    "instrument": "instrument_preferences",
    "genre": "genre_preferences",
    "tempo": "tempo_preferences",
    "energy": "energy_preferences",
    "texture": "texture_preferences",
    "era": "era_preferences",
}
CONSTRAINT_ATTRIBUTES: dict[Category, ConstraintAttribute] = {
    "instrument": ConstraintAttribute.INSTRUMENT,
    "genre": ConstraintAttribute.GENRE,
    "vocals": ConstraintAttribute.VOCALS,
}
VOCAL_TYPES = frozenset({"female vocals", "male vocals", "rapping"})
NEGATION_GAP = 3
"""Filler words allowed between a negation cue and its phrase ("without any electronic")."""
WITH_GAP = 3
HARD_GAP = 2
EXTENDERS = frozenset({"or", "nor"})
NO_QUESTION = "What kind of music are you looking for?"


def _decade(token: str) -> tuple[int, int] | None:
    """Year range of a decade token ("80s", "1980s", "'90s"); None otherwise."""
    return era_range(token.lstrip("'")) if token.endswith("s") else None


@dataclass(frozen=True)
class _Item:
    kind: str
    """mention | negation | hard | emphasis | intensifier | with | break | word"""
    text: str
    start: int
    end: int
    entry: Entry | None = None
    factor: float = 1.0


@dataclass
class _Mention:
    entry: Entry
    span: str
    weight: float
    negated: bool = False
    hard: bool = False


@dataclass
class _Ranges:
    bounds: dict[ConstraintAttribute, tuple[Bound, Bound]] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)

    def add(self, attribute: ConstraintAttribute, low: Bound, high: Bound) -> None:
        old_low, old_high = self.bounds.get(attribute, (None, None))
        new_low = low if old_low is None else old_low if low is None else max(low, old_low)
        new_high = high if old_high is None else old_high if high is None else min(high, old_high)
        if new_low is not None and new_high is not None and new_low > new_high:
            self.conflicts.append(f"a {attribute} range")
            return
        self.bounds[attribute] = (new_low, new_high)


class QueryParser:
    def __init__(self, lexicon: Lexicon) -> None:
        self._lexicon = lexicon
        self._cues = lexicon.cues

    @property
    def lexicon_version(self) -> str:
        return self._lexicon.version

    def parse(self, query: str) -> SearchSpecification:
        text = query.strip()
        if not text:
            raise ValueError("empty query")
        tokens = tokenize(text)
        if not any(t not in PUNCTUATION for t in tokens):
            return SearchSpecification(
                original_query=text, needs_clarification=True, clarification_question=NO_QUESTION
            )
        used = [False] * len(tokens)
        ranges = _Ranges()
        self._ranges(tokens, used, ranges)
        items = self._spot(tokens, used)
        mentions = self._walk(items)
        uncertainties = self._unmapped(tokens, used)
        return self._assemble(text, mentions, ranges, uncertainties)

    # --- pass 1: numeric ranges -------------------------------------------------------

    def _match(self, tokens: Sequence[str], i: int, phrases: frozenset[Phrase]) -> int:
        """Length of the longest phrase of `phrases` starting at token i (0 if none)."""
        for n in range(min(self._lexicon.max_phrase_length, len(tokens) - i), 0, -1):
            if tuple(tokens[i : i + n]) in phrases:
                return n
        return 0

    def _number(self, tokens: Sequence[str], i: int) -> tuple[int, int] | None:
        """(value, tokens used) of a number written in digits or words."""
        if i < len(tokens) and tokens[i].isdigit():
            return int(tokens[i]), 1
        n = self._match(tokens, i, frozenset(self._cues.numbers))
        return (self._cues.numbers[tuple(tokens[i : i + n])], n) if n else None

    def _quantity(
        self, tokens: Sequence[str], i: int
    ) -> tuple[ConstraintAttribute, tuple[int, int], int] | None:
        """A bound after a range cue: (attribute, (low, high) of the value, tokens used)."""
        j = i + 1 if i < len(tokens) and tokens[i] == "the" else i
        if j < len(tokens) and (decade := _decade(tokens[j])):
            return ConstraintAttribute.ERA, decade, j + 1 - i
        number = self._number(tokens, j)
        if number is None:
            return None
        value, n = number
        unit = tokens[j + n] if j + n < len(tokens) else ""
        if unit in self._cues.duration_units:
            seconds = value * self._cues.duration_units[unit]
            return ConstraintAttribute.DURATION, (seconds, seconds), j + n + 1 - i
        if unit in self._cues.tempo_units:
            return ConstraintAttribute.TEMPO, (value, value), j + n + 1 - i
        if n == 1 and tokens[j].isdigit() and len(tokens[j]) == 4 and 1900 <= value <= 2099:
            return ConstraintAttribute.ERA, (value, value), j + 1 - i
        return None

    def _ranges(self, tokens: Sequence[str], used: list[bool], ranges: _Ranges) -> None:
        cues = self._cues
        i = 0
        while i < len(tokens):
            n = self._match(tokens, i, cues.range_between)
            if n and (taken := self._between(tokens, i + n, ranges)):
                used[i : i + n + taken] = [True] * (n + taken)
                i += n + taken
                continue
            for phrases, upper in ((cues.range_upper, True), (cues.range_lower, False)):
                n = self._match(tokens, i, phrases)
                quantity = self._quantity(tokens, i + n) if n else None
                if quantity is None:
                    continue
                attribute, (low, high), taken = quantity
                cue = tokens[i : i + n]
                exclusive = attribute is ConstraintAttribute.ERA and cue != ["since"]
                if upper:
                    ranges.add(attribute, None, low - 1 if exclusive else high)
                else:
                    ranges.add(attribute, high + 1 if exclusive else low, None)
                used[i : i + n + taken] = [True] * (n + taken)
                i += n + taken - 1
                break
            i += 1

    def _between(self, tokens: Sequence[str], i: int, ranges: _Ranges) -> int:
        """'between 2 and 4 minutes', 'from 1990 to 1995', 'from the 80s to the 90s'."""
        first = self._quantity(tokens, i) or self._bare(tokens, i)
        if first is None:
            return 0
        _, (low, _), taken = first
        k = i + taken
        if k >= len(tokens) or tokens[k] not in ("and", "to"):
            return 0
        second = self._quantity(tokens, k + 1)
        if second is None:
            return 0
        attribute, (_, high), taken2 = second
        if first[0] not in (attribute, None):
            return 0
        if attribute is ConstraintAttribute.DURATION and first[0] is None:
            low *= self._cues.duration_units.get(tokens[k + taken2], 1)
        ranges.add(attribute, low, high)
        return taken + 1 + taken2

    def _bare(
        self, tokens: Sequence[str], i: int
    ) -> tuple[ConstraintAttribute | None, tuple[int, int], int] | None:
        """A bare number whose unit comes after the second bound ('between 2 and 4 minutes')."""
        number = self._number(tokens, i)
        if number is None:
            return None
        value, n = number
        return None, (value, value), n

    # --- pass 2: phrase spotting ------------------------------------------------------

    def _spot(self, tokens: Sequence[str], used: list[bool]) -> list[_Item]:
        cues = self._cues
        cue_kinds: list[tuple[str, frozenset[Phrase]]] = [
            ("negation", cues.negation),
            ("hard", cues.hard),
            ("emphasis", cues.emphasis),
            ("intensifier", frozenset(cues.intensifiers)),
            ("with", cues.with_cues),
        ]
        items: list[_Item] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if used[i]:
                i += 1
                continue
            if token in PUNCTUATION or token in cues.clause_breaks:
                items.append(_Item("break", token, i, i + 1))
                i += 1
                continue
            best: _Item | None = None
            limit = min(self._lexicon.max_phrase_length, len(tokens) - i)
            for n in range(limit, 0, -1):
                window = tuple(tokens[i : i + n])
                if any(used[i : i + n]) or any(t in PUNCTUATION for t in window):
                    continue
                text = " ".join(window)
                entry = self._lexicon.entries.get(window)
                if entry is not None:
                    best = _Item("mention", text, i, i + n, entry=entry)
                    break
                kind = next((k for k, phrases in cue_kinds if window in phrases), None)
                if kind is not None:
                    factor = cues.intensifiers.get(window, 1.0)
                    best = _Item(kind, text, i, i + n, factor=factor)
                    break
            if best is None:
                best = self._fallback(token, i)
            items.append(best)
            if best.kind != "word":
                used[best.start : best.end] = [True] * (best.end - best.start)
            i = best.end
        return items

    def _fallback(self, token: str, i: int) -> _Item:
        """Decades ("80s", "1980s") and plurals of single-word entries; else a plain word."""
        decade = _decade(token)
        if decade is not None:
            return _Item("mention", token, i, i + 1, entry=Entry("era", f"{decade[0]}s"))
        if len(token) > 3 and token.endswith("s"):
            entry = self._lexicon.entries.get((token[:-1],))
            if entry is not None:
                return _Item("mention", token, i, i + 1, entry=entry)
        return _Item("word", token, i, i + 1)

    # --- pass 3: attach cues ----------------------------------------------------------

    def _walk(self, items: Sequence[_Item]) -> list[_Mention]:
        mentions: list[_Mention] = []
        negation: str | None = None
        negation_gap = 0
        last_negation: str | None = None
        hard_gap: int | None = None
        with_gap: int | None = None
        intensity: float | None = None
        intensity_text: list[str] = []
        for k, item in enumerate(items):
            if item.kind != "intensifier" and item.kind != "mention":
                intensity, intensity_text = None, []
            if item.kind == "break":
                negation, last_negation, hard_gap, with_gap = None, None, None, None
            elif item.kind == "negation":
                negation, negation_gap, last_negation = item.text, 0, None
            elif item.kind == "hard":
                hard_gap = 0
            elif item.kind == "with":
                with_gap = 0
            elif item.kind == "intensifier":
                intensity = (intensity or 1.0) * item.factor
                intensity_text.append(item.text)
            elif item.kind == "word":
                if item.text in EXTENDERS and last_negation is not None:
                    negation, negation_gap = last_negation, 0
                elif negation is not None:
                    negation_gap += 1
                    if negation_gap > NEGATION_GAP:
                        negation = None
                last_negation = None
                hard_gap = None if hard_gap is None or hard_gap >= HARD_GAP else hard_gap + 1
                with_gap = None if with_gap is None or with_gap >= WITH_GAP else with_gap + 1
            elif item.kind == "mention":
                assert item.entry is not None
                entry = item.entry
                # a phrase directly after a negated one shares its cue ("without heavy drums")
                adjacent = k > 0 and items[k - 1].kind == "mention"
                cue = negation or (last_negation if adjacent else None)
                boosted = with_gap is not None and entry.category == "instrument" and not cue
                if boosted:
                    with_gap = None
                hard = hard_gap is not None or self._hard_after(items, k)
                hard_gap = None
                span = " ".join([*([cue] if cue else []), *intensity_text, item.text])
                mention = _Mention(
                    entry,
                    span,
                    self._weight(entry, cue is not None, boosted, intensity),
                    negated=cue is not None,
                    hard=hard or (cue is not None and self._hard_negation(entry, cue, items, k)),
                )
                mentions.append(mention)
                last_negation, negation = cue, None
                intensity, intensity_text = None, []
        return mentions

    def _hard_after(self, items: Sequence[_Item], k: int) -> bool:
        """'instrumental only': a hard cue right after the phrase, ending the clause."""
        if k + 1 >= len(items) or items[k + 1].kind != "hard":
            return False
        return k + 2 >= len(items) or items[k + 2].kind == "break"

    def _hard_negation(self, entry: Entry, cue: str, items: Sequence[_Item], k: int) -> bool:
        attribute = CONSTRAINT_ATTRIBUTES.get(entry.category)
        if attribute is None:
            return False
        if tuple(cue.split()) in self._cues.hard_negation.get(entry.category, frozenset()):
            return True
        following = items[k + 1 : k + 3]
        return any(i.kind == "emphasis" for i in following)

    def _weight(self, entry: Entry, negated: bool, boosted: bool, intensity: float | None) -> float:
        cues = self._cues
        base = cues.negative_weight if negated else self._lexicon.weights[entry.category]
        weight = base * entry.factor * (intensity or 1.0)
        if boosted:
            weight *= cues.with_boost
        return round(min(max(weight, 0.0), 1.0), 2)

    # --- uncertainties ----------------------------------------------------------------

    def _unmapped(self, tokens: Sequence[str], used: Sequence[bool]) -> list[str]:
        """Runs of musical-looking words that no lexicon phrase or cue covered."""
        runs: list[list[str]] = []
        previous = -2
        for i, token in enumerate(tokens):
            if used[i] or token not in self._cues.musical_words:
                continue
            if i == previous + 1:
                runs[-1].append(token)
            else:
                runs.append([token])
            previous = i
        return [f"unmapped musical term: '{' '.join(run)}'" for run in runs]

    # --- pass 4: assembly -------------------------------------------------------------

    def _assemble(
        self,
        text: str,
        mentions: Sequence[_Mention],
        ranges: _Ranges,
        uncertainties: list[str],
    ) -> SearchSpecification:
        positive: dict[Category, dict[str, WeightedPreference]] = {c: {} for c in PREFERENCE_FIELDS}
        negative: dict[str, WeightedPreference] = {}
        constraints: dict[tuple[ConstraintAttribute, str], ConstraintOperator] = {}
        vocals = _Vocals()
        conflicts = list(ranges.conflicts)

        for m in mentions:
            category, canonical = m.entry.category, m.entry.canonical
            pref = WeightedPreference(value=canonical, weight=m.weight, source_span=m.span)
            if category == "vocals":
                vocals.add(m, uncertainties)
                continue
            target = negative if m.negated else positive[category]
            if canonical not in target or target[canonical].weight < m.weight:
                target[canonical] = pref
            attribute = CONSTRAINT_ATTRIBUTES.get(category)
            if m.hard and attribute is not None:
                operator = ConstraintOperator.EXCLUDED if m.negated else ConstraintOperator.REQUIRED
                if constraints.get((attribute, canonical), operator) is not operator:
                    conflicts.append(canonical)
                constraints[(attribute, canonical)] = operator
            elif m.hard and category == "era" and not m.negated:
                low, high = era_range(canonical) or (None, None)
                ranges.add(ConstraintAttribute.ERA, low, high)
            elif m.hard:
                uncertainties.append(
                    f"'{m.span}' kept as a soft preference: {category} cannot be a hard constraint"
                )

        for canonical in [c for c in negative if any(c in p for p in positive.values())]:
            conflicts.append(canonical)
            del negative[canonical]
            for prefs in positive.values():
                prefs.pop(canonical, None)
        constraints = {key: op for key, op in constraints.items() if key[1] not in conflicts}
        vocal_preference, vocal_operator = vocals.resolve(conflicts)

        hard: list[HardConstraint] = []
        if vocal_operator is not None:
            hard.append(
                HardConstraint(attribute=ConstraintAttribute.VOCALS, operator=vocal_operator)
            )
        hard += [
            HardConstraint(attribute=attribute, operator=operator, value=value)
            for (attribute, value), operator in constraints.items()
        ]
        hard += [
            HardConstraint(attribute=attribute, operator=ConstraintOperator.RANGE, range=bounds)
            for attribute, bounds in ranges.bounds.items()
        ]
        data: dict[str, object] = {
            PREFERENCE_FIELDS[c]: list(prefs.values()) for c, prefs in positive.items()
        }
        data |= {
            "original_query": text,
            "negative_preferences": list(negative.values()),
            "vocal_preferences": vocal_preference,
            "hard_constraints": hard,
            "uncertainties": list(dict.fromkeys(uncertainties)),
            "needs_clarification": bool(conflicts),
            "clarification_question": _question(conflicts) if conflicts else None,
        }
        return with_prompts(SearchSpecification.model_validate(data))


@dataclass
class _Vocals:
    wanted: bool = False
    avoided: bool = False
    required: bool = False
    excluded: bool = False

    def add(self, m: _Mention, uncertainties: list[str]) -> None:
        canonical = m.entry.canonical
        # "instrumental" means no vocals; "not instrumental" means vocals
        positive = m.negated if canonical == "instrumental" else not m.negated
        if positive:
            self.required |= m.hard
            self.wanted |= not m.hard
        else:
            self.excluded |= m.hard
            self.avoided |= not m.hard
        if canonical in VOCAL_TYPES:
            uncertainties.append(
                f"vocal type '{canonical}' cannot be filtered; read as vocals in general"
            )

    def resolve(self, conflicts: list[str]) -> tuple[VocalPreference, ConstraintOperator | None]:
        if (self.wanted or self.required) and (self.avoided or self.excluded):
            conflicts.append("vocals")
            return "unspecified", None
        if self.excluded:
            return "excluded", ConstraintOperator.EXCLUDED
        if self.required:
            return "required", ConstraintOperator.REQUIRED
        if self.avoided:
            return "avoided", None
        if self.wanted:
            return "preferred", None
        return "unspecified", None


def _question(conflicts: Sequence[str]) -> str:
    subjects = list(dict.fromkeys(conflicts))
    listed = " and ".join(subjects)
    return f"Your request both asks for and rules out {listed}. Which do you want?"
