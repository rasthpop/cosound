"""Nearest tracks in the original embedding space (base.md §13.5).

Neighbors are CLAP cosine neighbors from the `VectorIndex`, never distances between 2D map
coordinates: UMAP closeness does not guarantee similarity (base.md §11.4). This service takes
no spatial repository at all.

A track without an embedding gets no audio neighbors. With a relationship repository it gets
a catalog fallback, labeled `metric="catalog_relationship"`: shared artist, release or label
are catalog context, not evidence that the tracks sound alike.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from music_discovery.domain.enums import RelationshipType
from music_discovery.domain.protocols import RelationshipRepository, VectorIndex

MAX_K = 50

NeighborMetric = Literal["clap_cosine", "catalog_relationship"]
NoNeighborReason = Literal["no_audio_embedding", "semantic_unavailable"]

FALLBACK_PRIORITY = (
    RelationshipType.SAME_RELEASE,
    RelationshipType.SAME_MASTER,
    RelationshipType.SAME_ARTIST,
    RelationshipType.SAME_LABEL,
    RelationshipType.SHARED_STYLE,
)
"""Order of catalog fallback neighbors: the most specific shared context first."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Neighbor(_Model):
    track_id: str
    score: float | None
    """Cosine for `clap_cosine`; the stored relationship weight (often None) otherwise."""
    relationship_types: list[RelationshipType] = []


class NeighborResult(_Model):
    track_id: str
    metric: NeighborMetric
    model_id: str | None = None
    neighbors: list[Neighbor] = Field(default_factory=list)
    reason: NoNeighborReason | None = None
    """Why audio neighbors are missing; None when `metric == "clap_cosine"`."""


class NeighborService:
    def __init__(
        self,
        index: VectorIndex | None,
        relationships: RelationshipRepository | None = None,
    ) -> None:
        self._index = index
        self._relationships = relationships

    def neighbors(self, track_id: str, k: int = 10) -> NeighborResult:
        if k < 1:
            raise ValueError("k must be at least 1")
        k = min(k, MAX_K)
        if self._index is None:
            return self._fallback(track_id, k, "semantic_unavailable")
        query = self._index.get(track_id)
        if query is None:
            return self._fallback(track_id, k, "no_audio_embedding")
        hits = [(t, s) for t, s in self._index.search(query, k + 1) if t != track_id][:k]
        return NeighborResult(
            track_id=track_id,
            metric="clap_cosine",
            model_id=self._index.model_id,
            neighbors=[Neighbor(track_id=t, score=s) for t, s in hits],
        )

    def _fallback(self, track_id: str, k: int, reason: NoNeighborReason) -> NeighborResult:
        by_target: dict[str, list[RelationshipType]] = {}
        weights: dict[str, float] = {}
        if self._relationships is not None:
            for rel in self._relationships.for_track(track_id, FALLBACK_PRIORITY):
                target = rel.target_track_id
                by_target.setdefault(target, []).append(rel.relationship_type)
                if rel.weight is not None:
                    weights[target] = max(weights.get(target, rel.weight), rel.weight)
        ranked = sorted(
            by_target,
            key=lambda t: (min(FALLBACK_PRIORITY.index(r) for r in by_target[t]), t),
        )
        neighbors = [
            Neighbor(
                track_id=t,
                score=weights.get(t),
                relationship_types=sorted(by_target[t], key=FALLBACK_PRIORITY.index),
            )
            for t in ranked[:k]
        ]
        return NeighborResult(
            track_id=track_id, metric="catalog_relationship", neighbors=neighbors, reason=reason
        )
