"""Catalog-relationship signal (base.md §7.5, §10.3).

Scores tracks by their catalog edges (same artist, same album; label and master once Discogs
data exists) to the reference tracks a user marked MORE_LIKE_THIS. This is discovery context,
never evidence that two tracks sound alike. It contributes only when its weight is above 0.
"""

from __future__ import annotations

from collections.abc import Collection

from music_discovery.domain.protocols import RelationshipRepository
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.retrieval.candidate_merger import RankedScore

DEFAULT_EDGE_WEIGHT = 1.0
"""Edges without a weight (same artist, same album) count fully."""


class RelationshipRetriever:
    def __init__(self, relationships: RelationshipRepository) -> None:
        self._relationships = relationships

    def _scores(self, spec: SearchSpecification) -> dict[str, float]:
        anchors = set(spec.reference_track_ids)
        scores: dict[str, float] = {}
        for anchor in sorted(anchors):
            for edge in self._relationships.for_track(anchor):
                if edge.target_track_id in anchors:
                    continue
                weight = edge.weight if edge.weight is not None else DEFAULT_EDGE_WEIGHT
                scores[edge.target_track_id] = max(scores.get(edge.target_track_id, 0.0), weight)
        return scores

    def available_for(self, spec: SearchSpecification) -> bool:
        """The signal exists only when the user gave reference tracks."""
        return bool(spec.reference_track_ids)

    def retrieve(
        self, spec: SearchSpecification, k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[RankedScore]:
        allowed = None if restrict_to is None else set(restrict_to)
        scored = [
            (t, s)
            for t, s in self._scores(spec).items()
            if s > 0 and (allowed is None or t in allowed)
        ]
        scored.sort(key=lambda p: (-p[1], p[0]))
        return [RankedScore(t, s, i) for i, (t, s) in enumerate(scored[:k], start=1)]

    def score(self, spec: SearchSpecification, track_ids: Collection[str]) -> dict[str, float]:
        """Exact score for each track: 0.0 when it has no edge to a reference track."""
        scores = self._scores(spec)
        return {t: scores.get(t, 0.0) for t in track_ids}
