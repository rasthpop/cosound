"""TrackEvidence from a ranked candidate, its retrieval signals and the catalog record (base §8).

Only facts the system actually has: metadata field matches (lexical or tag, with source),
the genre tags that matched, the best CLAP match with a strength band, hard-constraint
results, and uncertainty flags. Nothing is inferred: a tag is a tag, a CLAP match is a
similarity, and a missing signal is a flag, not a zero.

Strength bands come from the track's semantic rank and normalized score within the query
(`strong` = rank <= strong_max_rank and normalized >= tau_strong; `partial` = normalized >=
tau_partial; otherwise `weak`). The raw cosine is recorded but never shown. The same bands, plus
threshold-only bands for the normalized metadata and relationship scores (`score_bands` in the
config), are recorded per signal in `TrackEvidence.score_bands`; a missing signal has no band.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from music_discovery.descriptions.claim_validator import ScoreBandConfig, SemanticBands, SignalBands
from music_discovery.domain.enums import ConstraintStatus, MatchStrength
from music_discovery.domain.models import Track
from music_discovery.domain.schemas import (
    FieldMatch,
    RankedCandidate,
    ScoreBands,
    SemanticEvidence,
    TagMatch,
    TrackEvidence,
)

REFERENCE_PROMPT = "a track you liked"


@dataclass(frozen=True)
class SemanticSignal:
    """The best CLAP query for one track: its prompt (None for a reference-track query)."""

    prompt: str | None
    raw_cosine: float
    rank: int
    model_id: str
    kind: Literal["original", "expansion", "reference"] = "expansion"


def strength(rank: int, normalized: float | None, bands: SemanticBands) -> MatchStrength:
    if normalized is None:
        return MatchStrength.WEAK
    if rank <= bands.strong_max_rank and normalized >= bands.tau_strong:
        return MatchStrength.STRONG
    if normalized >= bands.tau_partial:
        return MatchStrength.PARTIAL
    return MatchStrength.WEAK


def signal_strength(normalized: float | None, bands: SignalBands | None) -> MatchStrength | None:
    if normalized is None or bands is None:
        return None
    if normalized >= bands.tau_strong:
        return MatchStrength.STRONG
    if normalized >= bands.tau_partial:
        return MatchStrength.PARTIAL
    return MatchStrength.WEAK


class EvidenceBuilder:
    def __init__(self, bands: SemanticBands, score_bands: ScoreBandConfig | None = None) -> None:
        self._bands = bands
        self._score_bands = score_bands or ScoreBandConfig()

    def build(
        self,
        candidate: RankedCandidate,
        track: Track | None,
        *,
        matched_fields: Sequence[FieldMatch] = (),
        semantic: SemanticSignal | None = None,
        degraded: Sequence[str] = (),
    ) -> TrackEvidence:
        flags: list[str] = []
        semantic_down = any(d.startswith("semantic_unavailable") for d in degraded)
        evidence_semantic = None
        if semantic is not None and candidate.score.semantic is not None:
            evidence_semantic = SemanticEvidence(
                prompt=semantic.prompt or REFERENCE_PROMPT,
                raw_cosine=semantic.raw_cosine,
                normalized=candidate.score.semantic,
                rank=semantic.rank,
                model_id=semantic.model_id,
                strength=strength(semantic.rank, candidate.score.semantic, self._bands),
                query_kind=semantic.kind,
            )
        elif semantic_down:
            flags.append("semantic_unavailable")
        elif candidate.score.semantic is None:
            flags.append("no_audio")
        for result in candidate.constraint_results:
            if result.status is ConstraintStatus.UNKNOWN:
                flags.append(f"constraint_unknown:{result.constraint.attribute}")
        return TrackEvidence(
            track_id=candidate.track_id,
            metadata_matches=_dedupe(m for m in matched_fields if m.field != "genres"),
            genre_matches=_genre_matches(matched_fields, track),
            semantic=evidence_semantic,
            retrieval_sources=candidate.retrieval_sources,
            constraint_results=candidate.constraint_results,
            uncertainty_flags=list(dict.fromkeys(flags)),
            score_bands=ScoreBands(
                semantic=None if evidence_semantic is None else evidence_semantic.strength,
                metadata=signal_strength(candidate.score.metadata, self._score_bands.metadata),
                relationship=signal_strength(
                    candidate.score.relationship, self._score_bands.relationship
                ),
            ),
        )


def _dedupe(matches: Iterable[FieldMatch]) -> list[FieldMatch]:
    seen: dict[tuple[str, str], FieldMatch] = {}
    for m in matches:
        seen.setdefault((m.field, m.term.casefold()), m)
    return list(seen.values())


def _genre_matches(matched: Sequence[FieldMatch], track: Track | None) -> list[TagMatch]:
    """The track's own genre tags that a query term matched, spelled as the catalog has them."""
    terms = [m for m in matched if m.field == "genres"]
    if not terms:
        return []
    genres = track.genres if track is not None else []
    found: dict[str, TagMatch] = {}
    for m in terms:
        words = set(m.term.casefold().replace("-", " ").split())
        tags = [g for g in genres if words <= set(g.casefold().replace("-", " ").split())]
        for tag in tags or [m.term]:
            found.setdefault(tag.casefold(), TagMatch(tag=tag, source=m.source))
    return list(found.values())
