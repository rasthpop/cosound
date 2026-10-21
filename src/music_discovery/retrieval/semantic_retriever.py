"""Text-to-audio retrieval with CLAP (base.md §7.2, §9.4).

Queries: the original request, up to N controlled expansions (alternate phrasings, never extra
requirements) and, after MORE_LIKE_THIS feedback, the audio vectors of reference tracks.
A track's score is the weighted maximum over queries, so an expansion only wins when it matches
clearly better than the original request does. Tracks without an audio embedding are absent
from the result. They are never scored 0, which would read as "evaluated and irrelevant".
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from music_discovery.domain.errors import MusicDiscoveryError
from music_discovery.domain.protocols import TextEncoder, Vector, VectorIndex
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.domain.vectors import l2_normalize

log = logging.getLogger(__name__)

QueryKind = Literal["original", "expansion", "reference"]


@dataclass(frozen=True)
class SemanticConfig:
    top_k: int = 100
    max_expansions: int = 4
    original_weight: float = 1.0
    expansion_weight: float = 0.8
    reference_weight: float = 1.0
    per_query_pool: int = 200
    """Candidates gathered per query before exact rescoring of their union."""


@dataclass(frozen=True)
class SemanticQuery:
    kind: QueryKind
    text: str | None
    """Prompt text, or None for a reference-track audio query."""
    reference_track_id: str | None
    weight: float


@dataclass(frozen=True)
class SemanticHit:
    track_id: str
    rank: int
    score: float
    """Weighted score used for ordering (weight * cosine of the best query)."""
    raw_cosine: float
    """Unweighted cosine with the best query, in [-1, 1]. A similarity, not a probability."""
    best_query: SemanticQuery


@dataclass(frozen=True)
class SemanticResult:
    status: Literal["available", "unavailable"]
    model_id: str | None
    hits: list[SemanticHit] = field(default_factory=list)
    queries: list[SemanticQuery] = field(default_factory=list)
    reason: str | None = None

    def score_of(self, track_id: str) -> float | None:
        return next((h.score for h in self.hits if h.track_id == track_id), None)


class SemanticRetriever:
    def __init__(
        self,
        text_encoder: TextEncoder | None,
        index: VectorIndex | None,
        config: SemanticConfig | None = None,
    ) -> None:
        self._encoder = text_encoder
        self._index = index
        self._config = config or SemanticConfig()

    @property
    def available(self) -> bool:
        return self._encoder is not None and self._index is not None

    def retrieve(
        self,
        spec: SearchSpecification,
        k: int | None = None,
        *,
        restrict_to: Collection[str] | None = None,
    ) -> SemanticResult:
        """Top-k tracks for the request; `restrict_to` scores exactly the given pool."""
        if self._encoder is None or self._index is None:
            return SemanticResult(
                status="unavailable", model_id=None, reason="semantic_unavailable"
            )
        encoder, index = self._encoder, self._index
        if encoder.model_id != index.model_id:
            return SemanticResult(
                status="unavailable",
                model_id=index.model_id,
                reason="embedding_version_mismatch",
            )
        cfg = self._config
        queries, vectors = self._queries(spec, encoder, index)
        if isinstance(vectors, str):
            return SemanticResult(status="unavailable", model_id=index.model_id, reason=vectors)

        pool: set[str] = set()
        for vector in vectors:
            pool.update(
                t for t, _ in index.search(vector, cfg.per_query_pool, restrict_to=restrict_to)
            )
        if restrict_to is not None:
            pool.update(t for t in restrict_to if t in index)

        scored: list[tuple[float, float, str, SemanticQuery]] = []
        query_matrix = np.stack(vectors)
        weights = np.array([q.weight for q in queries], dtype=np.float32)
        for track_id in pool:
            track_vector = index.get(track_id)
            if track_vector is None:
                continue
            cosines = np.clip(query_matrix @ track_vector, -1.0, 1.0)
            weighted = weights * cosines
            best = int(np.argmax(weighted))
            scored.append((float(weighted[best]), float(cosines[best]), track_id, queries[best]))

        scored.sort(key=lambda item: (-item[0], item[2]))
        limit = cfg.top_k if k is None else k
        hits = [
            SemanticHit(track_id=t, rank=i, score=s, raw_cosine=c, best_query=q)
            for i, (s, c, t, q) in enumerate(scored[:limit], start=1)
        ]
        return SemanticResult(
            status="available", model_id=index.model_id, hits=hits, queries=queries
        )

    def _queries(
        self, spec: SearchSpecification, encoder: TextEncoder, index: VectorIndex
    ) -> tuple[list[SemanticQuery], list[Vector] | str]:
        cfg = self._config
        texts = [spec.original_query, *spec.semantic_prompts[: cfg.max_expansions]]
        queries = [SemanticQuery("original", spec.original_query, None, cfg.original_weight)]
        queries += [SemanticQuery("expansion", t, None, cfg.expansion_weight) for t in texts[1:]]
        try:
            text_vectors = list(l2_normalize(encoder.encode_texts(texts)))
        except MusicDiscoveryError as exc:
            log.warning("text encoding failed: %s", exc)
            return queries, exc.code
        vectors: list[Vector] = text_vectors
        for reference in spec.reference_track_ids:
            reference_vector = index.get(reference)
            if reference_vector is None:
                continue  # a reference without audio cannot steer audio similarity
            queries.append(SemanticQuery("reference", None, reference, cfg.reference_weight))
            vectors.append(reference_vector)
        return queries, vectors
