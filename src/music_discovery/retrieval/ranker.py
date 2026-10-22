"""Transparent weighted ranking with explicit missing-modality handling (base.md §7.5).

    S(t, q) = sum_i w_i * s_i(t, q) / sum_{i available for t} w_i

Only signals that exist for the track count, so a track without audio is ranked on metadata
alone, not as if its audio had been found irrelevant. An optional coverage penalty
(gamma > 0) slightly prefers fully evidenced tracks. Feedback penalties and the "demote"
policy for unknown constraints are applied after the weighted sum. Weights come only from
`RetrievalConfig`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from music_discovery.domain.schemas import ScoreBreakdown
from music_discovery.retrieval.candidate_merger import Candidate
from music_discovery.retrieval.config import RetrievalConfig, Signal

SIGNALS: tuple[Signal, ...] = ("semantic", "metadata", "relationship")


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    breakdown: ScoreBreakdown
    relevance: float
    """Final score before diversity reranking (equals `breakdown.final`)."""


def rank(
    candidates: Sequence[Candidate],
    normalized: Mapping[Signal, Mapping[str, float | None]],
    config: RetrievalConfig,
    *,
    active: Collection[Signal],
    normalization: str,
    penalties: Mapping[str, float] | None = None,
    unknown_constraints: Mapping[str, int] | None = None,
) -> list[Scored]:
    """Score and order candidates. Candidates with no weighted signal at all are dropped."""
    weights = config.weights
    active_weights = {s: weights.of(s) for s in active if weights.of(s) > 0}
    total_weight = sum(active_weights.values())
    penalties = penalties or {}
    unknown_constraints = unknown_constraints or {}
    demote = config.constraints.unknown == "demote"

    scored: list[Scored] = []
    for candidate in candidates:
        values = {s: normalized.get(s, {}).get(candidate.track_id) for s in SIGNALS}
        present = {s: v for s, v in values.items() if v is not None}
        available = {s: w for s, w in active_weights.items() if s in present}
        if not available:
            continue
        weighted = sum(w * present[s] for s, w in available.items())
        base = weighted / sum(available.values())
        coverage = (sum(available.values()) / total_weight) ** config.coverage_penalty_gamma
        final = base * coverage - penalties.get(candidate.track_id, 0.0)
        if demote:
            final *= config.constraints.unknown_demotion ** unknown_constraints.get(
                candidate.track_id, 0
            )
        final = min(max(final, 0.0), 1.0)
        breakdown = ScoreBreakdown(
            semantic=values["semantic"],
            metadata=values["metadata"],
            relationship=values["relationship"] if weights.relationship > 0 else None,
            final=final,
            normalization=normalization,
            weights_version=config.weights_version,
        )
        scored.append(Scored(candidate=candidate, breakdown=breakdown, relevance=final))
    scored.sort(key=lambda s: (-s.relevance, s.candidate.track_id))
    return scored
