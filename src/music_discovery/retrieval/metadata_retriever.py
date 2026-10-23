"""Metadata retrieval over the local catalog (base.md §7.1).

Searches titles, artists, album titles, genres and tags (the FMA-only MVP fields, ADR-0005)
and matches era preferences against the release year. A matched title word is *lexical*
evidence only: "flute" in a title does not mean a flute is audible.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import Track
from music_discovery.domain.protocols import LexicalIndex
from music_discovery.domain.schemas import FieldMatch, SearchSpecification

FIELD_KIND: dict[str, str] = {
    "title": "lexical",
    "artist": "lexical",
    "album": "lexical",
    "genres": "tag",
    "tags": "tag",
}
DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "title": 1.0,
    "artist": 1.0,
    "album": 0.5,
    "genres": 2.0,
    "tags": 1.5,
}
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "i",
        "in",
        "is",
        "it",
        "like",
        "me",
        "music",
        "my",
        "of",
        "on",
        "or",
        "play",
        "please",
        "some",
        "something",
        "song",
        "songs",
        "sound",
        "sounds",
        "that",
        "the",
        "this",
        "to",
        "track",
        "tracks",
        "want",
        "with",
    }
)
_WORD = re.compile(r"[a-z0-9]+")
_ERA = re.compile(r"^(?:(?P<century>1[89]|20)?(?P<decade>\d)0)'?s$")

TermExpander = Callable[[str], Sequence[str]]
"""Synonym hook; the composition root passes the agents lexicon's `expand` (identity if unset)."""


def metadata_document(track: Track, album_title: str | None) -> dict[str, str]:
    """The searchable text of a track, by field."""
    return {
        "title": track.title,
        "artist": " ".join(a.name for a in track.artists),
        "album": album_title or "",
        "genres": " | ".join(track.genres),
        "tags": " | ".join(track.tags),
    }


def era_range(value: str) -> tuple[int, int] | None:
    """Year range of an era: '1980s' and '80s' -> (1980, 1989), '00s' -> (2000, 2009),
    '1995' -> (1995, 1995); None if the value is not an era."""
    text = value.strip().casefold()
    if text.isdigit() and len(text) == 4:
        year = int(text)
        return year, year
    match = _ERA.match(text)
    if match is None:
        return None
    decade = int(match["decade"])
    century = match["century"]
    # a bare decade ("80s") means the 1900s, except 00s-20s
    implied = 2000 if decade <= 2 else 1900
    century_start = implied if century is None else int(century) * 100
    start = century_start + decade * 10
    return start, start + 9


@dataclass(frozen=True)
class TrackFacts:
    """What metadata retrieval needs besides the text index."""

    year: int | None
    source: DataSource


@dataclass(frozen=True)
class MetadataHit:
    track_id: str
    raw_score: float
    """Lexical score plus era bonus; 0.0 means evaluated and nothing matched."""
    rank: int
    matched_fields: list[FieldMatch]


@dataclass(frozen=True)
class MetadataResult:
    hits: list[MetadataHit]
    terms: list[str] = field(default_factory=list)

    def score_of(self, track_id: str) -> float | None:
        return next((h.raw_score for h in self.hits if h.track_id == track_id), None)


@dataclass(frozen=True)
class MetadataConfig:
    era_bonus: float = 1.0
    query_word_min_length: int = 3


class MetadataRetriever:
    def __init__(
        self,
        index: LexicalIndex,
        facts: Mapping[str, TrackFacts],
        *,
        expand: TermExpander | None = None,
        config: MetadataConfig | None = None,
    ) -> None:
        self._index = index
        self._facts = facts
        self._expand = expand or (lambda term: [term])
        self._config = config or MetadataConfig()

    def query_terms(self, spec: SearchSpecification) -> list[str]:
        """Positive preference values (plus synonyms) and content words of the request."""
        terms: list[str] = []
        for prefs in spec.positive_preferences.values():
            if prefs is spec.era_preferences:
                continue
            for pref in prefs:
                terms.extend(self._expand(pref.value))
        for word in _WORD.findall(spec.original_query.casefold()):
            if word not in STOPWORDS and len(word) >= self._config.query_word_min_length:
                terms.append(word)
        negatives = {p.value.casefold() for p in spec.negative_preferences}
        return [t for t in dict.fromkeys(terms) if t.casefold() not in negatives]

    def negative_terms(self, spec: SearchSpecification) -> list[str]:
        terms: list[str] = []
        for pref in spec.negative_preferences:
            terms.extend(self._expand(pref.value))
        return list(dict.fromkeys(terms))

    def retrieve(
        self, spec: SearchSpecification, k: int, *, restrict_to: Collection[str] | None = None
    ) -> MetadataResult:
        """Top-k tracks with a positive metadata score."""
        terms = self.query_terms(spec)
        scores = (
            dict(self._index.search(terms, max(k * 4, k), restrict_to=restrict_to)) if terms else {}
        )
        for track_id, bonus in self._era_bonuses(spec, restrict_to).items():
            scores[track_id] = scores.get(track_id, 0.0) + bonus
        ranked = sorted(((t, s) for t, s in scores.items() if s > 0), key=lambda p: (-p[1], p[0]))[
            :k
        ]
        return MetadataResult(hits=self._hits(spec, terms, ranked), terms=terms)

    def score(self, spec: SearchSpecification, track_ids: Collection[str]) -> MetadataResult:
        """Exact metadata score for every given track, including 0.0 for no match."""
        terms = self.query_terms(spec)
        pool = [t for t in track_ids if t in self._facts]
        lexical = (
            dict(self._index.search(terms, len(pool), restrict_to=pool)) if terms and pool else {}
        )
        bonuses = self._era_bonuses(spec, pool)
        scored = [(t, lexical.get(t, 0.0) + bonuses.get(t, 0.0)) for t in pool]
        scored.sort(key=lambda p: (-p[1], p[0]))
        return MetadataResult(hits=self._hits(spec, terms, scored), terms=terms)

    def negative_matches(
        self, spec: SearchSpecification, track_ids: Collection[str]
    ) -> dict[str, list[FieldMatch]]:
        """Negative-preference terms found in each track's metadata (for ranking penalties)."""
        terms = self.negative_terms(spec)
        if not terms:
            return {}
        out: dict[str, list[FieldMatch]] = {}
        for track_id in track_ids:
            matches = self._field_matches(track_id, terms)
            if matches:
                out[track_id] = matches
        return out

    def _era_bonuses(
        self, spec: SearchSpecification, restrict_to: Collection[str] | None
    ) -> dict[str, float]:
        ranges = [r for p in spec.era_preferences if (r := era_range(p.value)) is not None]
        if not ranges:
            return {}
        pool = self._facts.keys() if restrict_to is None else restrict_to
        bonuses: dict[str, float] = {}
        for track_id in pool:
            facts = self._facts.get(track_id)
            if facts is None or facts.year is None:
                continue
            if any(low <= facts.year <= high for low, high in ranges):
                bonuses[track_id] = self._config.era_bonus
        return bonuses

    def _field_matches(self, track_id: str, terms: Sequence[str]) -> list[FieldMatch]:
        facts = self._facts.get(track_id)
        source = facts.source if facts else DataSource.DERIVED
        return [
            FieldMatch(
                field=f,
                term=term,
                source=source,
                kind="tag" if FIELD_KIND.get(f) == "tag" else "lexical",
            )
            for f, term in self._index.matches(track_id, terms)
        ]

    def _hits(
        self, spec: SearchSpecification, terms: Sequence[str], ranked: Sequence[tuple[str, float]]
    ) -> list[MetadataHit]:
        ranges = [
            (p.value, r) for p in spec.era_preferences if (r := era_range(p.value)) is not None
        ]
        hits: list[MetadataHit] = []
        for rank, (track_id, score) in enumerate(ranked, start=1):
            matches = self._field_matches(track_id, terms) if score > 0 else []
            facts = self._facts.get(track_id)
            if facts is not None and facts.year is not None:
                for value, (low, high) in ranges:
                    if low <= facts.year <= high:
                        matches.append(
                            FieldMatch(field="year", term=value, source=facts.source, kind="tag")
                        )
            hits.append(
                MetadataHit(track_id=track_id, raw_score=score, rank=rank, matched_fields=matches)
            )
        return hits
