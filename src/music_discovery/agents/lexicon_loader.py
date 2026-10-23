"""The versioned lexicon behind the deterministic query parser (base.md §6).

Data lives in `agents/lexicon/*.yaml`: one file per attribute category (canonical term ->
phrases that mean it) plus `cues.yaml` (negation, hard-constraint and intensity cues). Every
phrase belongs to exactly one canonical term, so phrase spotting is never ambiguous. The
lexicon version is a hash of the files, so any edit changes it.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Category = Literal["mood", "instrument", "genre", "tempo", "energy", "texture", "era", "vocals"]
CATEGORIES: tuple[Category, ...] = (
    "mood",
    "instrument",
    "genre",
    "tempo",
    "energy",
    "texture",
    "era",
    "vocals",
)
DEFAULT_DIR = Path(__file__).parent / "lexicon"

_TOKEN = re.compile(r"'?\d+'?s\b|[a-z0-9]+|[,.;:!?]")
PUNCTUATION = frozenset(",.;:!?")
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_QUOTES = dict.fromkeys(map(ord, "\u2018\u2019\u02bc`"), "'")

Phrase = tuple[str, ...]


def tokenize(text: str) -> list[str]:
    """Casefold, strip accents, split on hyphens and spaces; punctuation marks are tokens."""
    text = unicodedata.normalize("NFKD", text.translate(_DASHES).translate(_QUOTES))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return _TOKEN.findall(text.replace("&", " and "))


def phrase(text: str) -> Phrase:
    return tuple(t for t in tokenize(text) if t not in PUNCTUATION)


class LexiconError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    category: Category
    canonical: str
    factor: float = 1.0
    """Fraction of the category weight this phrase carries ("woodwind" -> flute at 0.6)."""


@dataclass(frozen=True)
class Cues:
    negation: frozenset[Phrase]
    hard_negation: Mapping[str, frozenset[Phrase]]
    hard: frozenset[Phrase]
    emphasis: frozenset[Phrase]
    intensifiers: Mapping[Phrase, float]
    with_cues: frozenset[Phrase]
    with_boost: float
    negative_weight: float
    clause_breaks: frozenset[str]
    follow_up: frozenset[Phrase]
    range_upper: frozenset[Phrase]
    range_lower: frozenset[Phrase]
    range_between: frozenset[Phrase]
    duration_units: Mapping[str, int]
    tempo_units: frozenset[str]
    numbers: Mapping[Phrase, int]
    musical_words: frozenset[str]


@dataclass(frozen=True)
class Lexicon:
    version: str
    weights: Mapping[Category, float]
    entries: Mapping[Phrase, Entry]
    synonyms: Mapping[tuple[Category, str], Sequence[str]]
    """Full-weight phrases of each canonical term, canonical first (for synonym expansion)."""
    cues: Cues
    max_phrase_length: int = field(init=False)

    def __post_init__(self) -> None:
        cue_phrases = [
            *self.cues.negation,
            *self.cues.hard,
            *self.cues.emphasis,
            *self.cues.intensifiers,
            *self.cues.with_cues,
            *self.cues.range_upper,
            *self.cues.range_lower,
            *self.cues.numbers,
        ]
        longest = max(len(p) for p in [*self.entries, *cue_phrases])
        object.__setattr__(self, "max_phrase_length", longest)

    def lookup(self, text: str) -> Entry | None:
        return self.entries.get(phrase(text))

    def expand(self, term: str) -> list[str]:
        """The term plus the full-weight synonyms of its canonical term (metadata retrieval).

        Weak synonyms ("woodwind" for flute) are not expanded: they would widen lexical
        matching beyond what the user asked for. Synonyms containing every word of a shorter
        expansion ("chill out" next to "chill") are dropped too: a field they match is already
        matched by the shorter term, so they would only count the same evidence twice.
        """
        entry = self.lookup(term)
        if entry is None or entry.factor < 1.0:
            return [term]
        by_words: dict[frozenset[str], str] = {}
        for candidate in [term, *self.synonyms[(entry.category, entry.canonical)]]:
            by_words.setdefault(frozenset(phrase(candidate)), candidate)
        return [c for w, c in by_words.items() if not any(o < w for o in by_words)]


def _text(value: object) -> str:
    if not isinstance(value, str | int) or isinstance(value, bool):
        # YAML reads bare no/yes/on/off as booleans
        raise LexiconError(f"phrase {value!r} is not text; quote it in the YAML file")
    return str(value)


def _phrases(values: Sequence[object]) -> frozenset[Phrase]:
    return frozenset(phrase(_text(v)) for v in values)


def _load_category(
    category: Category, data: Mapping[str, Any], entries: dict[Phrase, Entry], source: str
) -> list[tuple[tuple[Category, str], list[str]]]:
    groups = []
    for canonical, synonyms in data["terms"].items():
        canonical = str(canonical)
        full = [canonical]
        for item in [canonical, *synonyms]:
            raw, factor = next(iter(item.items())) if isinstance(item, dict) else (item, 1.0)
            text = _text(raw)
            key = phrase(text)
            if not key:
                raise LexiconError(f"{source}: empty phrase under {canonical!r}")
            entry = Entry(category, canonical, float(factor))
            previous = entries.get(key)
            if previous is not None and previous != entry:
                raise LexiconError(
                    f"{source}: {' '.join(key)!r} already means "
                    f"{previous.category}:{previous.canonical}"
                )
            entries[key] = entry
            if factor >= 1.0 and text not in full:
                full.append(text)
        groups.append(((category, canonical), full))
    return groups


def _load_cues(data: Mapping[str, Any]) -> Cues:
    return Cues(
        negation=_phrases(data["negation"]),
        hard_negation={k: _phrases(v) for k, v in data["hard_negation"].items()},
        hard=_phrases(data["hard"]),
        emphasis=_phrases(data["emphasis"]),
        intensifiers={phrase(_text(k)): float(v) for k, v in data["intensifiers"].items()},
        with_cues=_phrases(data["with_cues"]),
        with_boost=float(data["with_boost"]),
        negative_weight=float(data["negative_weight"]),
        clause_breaks=frozenset(data["clause_breaks"]),
        follow_up=_phrases(data["follow_up"]),
        range_upper=_phrases(data["range"]["upper"]),
        range_lower=_phrases(data["range"]["lower"]),
        range_between=_phrases(data["range"]["between"]),
        duration_units={str(k): int(v) for k, v in data["units"]["duration"].items()},
        tempo_units=frozenset(data["units"]["tempo"]),
        numbers={phrase(_text(k)): int(v) for k, v in data["numbers"].items()},
        musical_words=frozenset(data["musical_words"]),
    )


def load_lexicon(directory: Path = DEFAULT_DIR) -> Lexicon:
    """Load and validate the lexicon; raises LexiconError on ambiguous or malformed data."""
    digest = hashlib.sha256()
    entries: dict[Phrase, Entry] = {}
    weights: dict[Category, float] = {}
    synonyms: dict[tuple[Category, str], list[str]] = {}
    for category in CATEGORIES:
        path = directory / f"{category}.yaml"
        raw = path.read_bytes()
        digest.update(path.name.encode() + b"\0" + raw)
        data = yaml.safe_load(raw)
        weights[category] = float(data.get("weight", 1.0))
        synonyms.update(_load_category(category, data, entries, path.name))
    cues_path = directory / "cues.yaml"
    raw = cues_path.read_bytes()
    digest.update(cues_path.name.encode() + b"\0" + raw)
    cues = _load_cues(yaml.safe_load(raw))
    canonicals: dict[str, Category] = {}
    for category, canonical in synonyms:
        if canonical in canonicals and canonicals[canonical] != category:
            raise LexiconError(
                f"canonical term {canonical!r} is in both {canonicals[canonical]} and {category}"
            )
        canonicals[canonical] = category
    return Lexicon(
        version=f"lex-{digest.hexdigest()[:12]}",
        weights=weights,
        entries=entries,
        synonyms=synonyms,
        cues=cues,
    )
