"""The hybrid relevance engine (base.md §7): one code path for all three evaluation systems.

    metadata + semantic (+ relationship) -> merge -> back-fill -> hard constraints
    -> per-signal normalization -> weighted ranking -> MMR diversity -> ranked plate

Modes: `metadata_only` (never calls the text encoder), `semantic_only` (CLAP only) and
`hybrid`. No LLM is involved. If semantic retrieval is unavailable, hybrid mode degrades to
metadata and says so in `degraded`.
"""

from __future__ import annotations

import time
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from music_discovery.domain.enums import SearchOutcomeKind
from music_discovery.domain.protocols import TrackRepository, VectorIndex
from music_discovery.domain.schemas import (
    FieldMatch,
    RankedCandidate,
    RetrievalTrace,
    SearchOutcome,
    SearchSpecification,
    SourceScore,
)
from music_discovery.retrieval.candidate_merger import (
    SIGNAL_SOURCE,
    Candidate,
    RankedScore,
    backfill,
    merge,
    missing,
)
from music_discovery.retrieval.config import RetrievalConfig, Signal
from music_discovery.retrieval.constraints import apply_constraints, no_confident_match_reasons
from music_discovery.retrieval.diversity import TrackSimilarity, mmr, mmr_lambda
from music_discovery.retrieval.metadata_retriever import MetadataRetriever
from music_discovery.retrieval.normalization import normalize
from music_discovery.retrieval.ranker import rank
from music_discovery.retrieval.relationship_retriever import RelationshipRetriever
from music_discovery.retrieval.semantic_retriever import SemanticHit, SemanticRetriever

Mode = Literal["metadata_only", "semantic_only", "hybrid"]
MODE_SIGNALS: dict[Mode, tuple[Signal, ...]] = {
    "metadata_only": ("metadata",),
    "semantic_only": ("semantic",),
    "hybrid": ("semantic", "metadata", "relationship"),
}


@dataclass
class HybridResult:
    outcome: SearchOutcome
    trace: RetrievalTrace
    matched_fields: dict[str, list[FieldMatch]] = field(default_factory=dict)
    """Metadata evidence per returned track (for explanations)."""
    semantic_hits: dict[str, SemanticHit] = field(default_factory=dict)
    """Best CLAP match per returned track (prompt, raw cosine), when available."""


class HybridRetriever:
    def __init__(
        self,
        config: RetrievalConfig,
        *,
        metadata: MetadataRetriever,
        semantic: SemanticRetriever | None,
        tracks: TrackRepository,
        index: VectorIndex | None = None,
        relationships: RelationshipRetriever | None = None,
    ) -> None:
        self._config = config
        self._metadata = metadata
        self._semantic = semantic
        self._tracks = tracks
        self._index = index
        self._relationships = relationships

    def retrieve(
        self,
        spec: SearchSpecification,
        *,
        mode: Mode = "hybrid",
        limit: int = 8,
        corpus: Collection[str] | None = None,
    ) -> HybridResult:
        """Ranked plate for the spec. `corpus` restricts retrieval to a fixed track set."""
        cfg = self._config
        timings: dict[str, float] = {}
        counts: dict[str, int] = {}
        degraded: list[str] = []
        clock = time.perf_counter
        started = clock()

        excluded = set(spec.excluded_track_ids)
        restrict = None if corpus is None else [t for t in corpus if t not in excluded]
        active = [
            s for s in MODE_SIGNALS[mode] if s != "relationship" or self._relationship_on(spec)
        ]

        # 1. retrieval
        retrieved: dict[Signal, list[RankedScore]] = {}
        matched: dict[str, list[FieldMatch]] = {}
        semantic_hits: dict[str, SemanticHit] = {}
        semantic_ok = False
        model_id = None
        if "metadata" in active:
            result = self._metadata.retrieve(spec, cfg.metadata_top_k, restrict_to=restrict)
            retrieved["metadata"] = [
                RankedScore(h.track_id, h.raw_score, h.rank)
                for h in result.hits
                if h.track_id not in excluded
            ]
            matched.update({h.track_id: h.matched_fields for h in result.hits})
        if "semantic" in active:
            if self._semantic is None:
                degraded.append("semantic_unavailable")
            else:
                sem = self._semantic.retrieve(spec, cfg.semantic_top_k, restrict_to=restrict)
                model_id = sem.model_id
                if sem.status != "available":
                    degraded.append(f"semantic_unavailable:{sem.reason}")
                else:
                    semantic_ok = True
                    retrieved["semantic"] = [
                        RankedScore(h.track_id, h.score, h.rank)
                        for h in sem.hits
                        if h.track_id not in excluded
                    ]
                    semantic_hits.update({h.track_id: h for h in sem.hits})
        if "relationship" in active and self._relationships is not None:
            retrieved["relationship"] = [
                r
                for r in self._relationships.retrieve(spec, cfg.pool_size, restrict_to=restrict)
                if r.track_id not in excluded
            ]
        for signal, scores in retrieved.items():
            counts[f"{signal}_retrieved"] = len(scores)
        timings["retrieve_ms"] = (clock() - started) * 1000

        # 2. merge and back-fill exact scores for candidates found by only one retriever
        merged = merge(retrieved, pool_size=cfg.pool_size)
        pool = merged.candidates
        counts["pool_before_cap"] = merged.pool_before_cap
        counts["pool"] = len(pool)
        self._backfill(spec, pool, active, semantic_ok, matched, semantic_hits, counts)
        timings["merge_ms"] = (clock() - started) * 1000 - timings["retrieve_ms"]

        tracks = {t.id: t for t in self._tracks.get_many([c.track_id for c in pool])}

        # 3. hard constraints, enforced independently of the score
        outcome = apply_constraints(
            [c.track_id for c in pool], tracks, spec.hard_constraints, cfg.constraints
        )
        counts["after_constraints"] = len(outcome.kept)

        def trace(fallbacks: list[str] | None = None) -> RetrievalTrace:
            timings["total_ms"] = (clock() - started) * 1000
            return RetrievalTrace(
                mode=mode,
                model_id=model_id,
                config_versions={"weights": cfg.weights_version},
                pool_size=len(pool),
                stage_counts=counts,
                normalization_fallbacks=fallbacks or [],
                degraded=degraded,
                timings_ms=timings,
            )

        if spec.hard_constraints and pool and not outcome.kept:
            return HybridResult(
                outcome=SearchOutcome(
                    kind=SearchOutcomeKind.NO_CONFIDENT_MATCH,
                    reasons=no_confident_match_reasons(outcome, spec.hard_constraints),
                    degraded=degraded,
                ),
                trace=trace(),
            )
        kept_ids = set(outcome.kept)
        kept = [c for c in pool if c.track_id in kept_ids]

        # 4. per-signal normalization over the surviving pool
        normalized: dict[Signal, dict[str, float | None]] = {}
        notes: list[str] = []
        fallbacks: list[str] = []
        for signal in active:
            result_n = normalize(
                {c.track_id: c.raw(signal) for c in kept},
                cfg.normalization.strategy(signal),
                min_pool=cfg.normalization.min_pool,
                calibrated=cfg.normalization.calibrated.get(signal),
            )
            normalized[signal] = result_n.values
            notes.append(f"{signal}={result_n.strategy}")
            if result_n.fallback:
                fallbacks.append(f"{signal}:{result_n.fallback}")

        # 5. weighted ranking with feedback penalties, then diversity
        scored = rank(
            kept,
            normalized,
            cfg,
            active=active,
            normalization=";".join(notes),
            penalties=self._penalties(spec, [c.track_id for c in kept]),
            unknown_constraints={t: outcome.unknown_count(t) for t in kept_ids},
        )
        counts["ranked"] = len(scored)
        similarity = TrackSimilarity(
            tracks, self._index, duplicate_cosine=cfg.diversity.duplicate_cosine
        )
        plate = mmr(
            scored,
            limit,
            lambda_=mmr_lambda(spec.diversity, cfg.diversity.scale),
            similarity=similarity.similarity,
            is_duplicate=similarity.is_duplicate,
        )
        counts["returned"] = len(plate)

        candidates = [
            RankedCandidate(
                track_id=item.candidate.track_id,
                rank=i,
                score=item.breakdown,
                retrieval_sources=item.candidate.retrieval_sources,
                source_scores={
                    SIGNAL_SOURCE[s]: SourceScore(raw_score=v.raw, rank=v.rank)
                    for s, v in item.candidate.signals.items()
                    if v.status == "retrieved" and v.raw is not None and v.rank is not None
                },
                constraint_results=outcome.results.get(item.candidate.track_id, []),
            )
            for i, item in enumerate(plate, start=1)
        ]
        returned = {c.track_id for c in candidates}
        return HybridResult(
            outcome=SearchOutcome(
                kind=SearchOutcomeKind.OK, candidates=candidates, degraded=degraded
            ),
            trace=trace(fallbacks),
            matched_fields={t: m for t, m in matched.items() if t in returned and m},
            semantic_hits={t: h for t, h in semantic_hits.items() if t in returned},
        )

    def _relationship_on(self, spec: SearchSpecification) -> bool:
        return (
            self._relationships is not None
            and self._config.weights.relationship > 0
            and self._relationships.available_for(spec)
        )

    def _backfill(
        self,
        spec: SearchSpecification,
        pool: list[Candidate],
        active: list[Signal],
        semantic_ok: bool,
        matched: dict[str, list[FieldMatch]],
        semantic_hits: dict[str, SemanticHit],
        counts: dict[str, int],
    ) -> None:
        if "metadata" in active:
            ids = missing(pool, "metadata")
            if ids:
                result = self._metadata.score(spec, ids)
                backfill(
                    pool, "metadata", {h.track_id: h.raw_score for h in result.hits}, evaluated=ids
                )
                matched.update(
                    {h.track_id: h.matched_fields for h in result.hits if h.matched_fields}
                )
            counts["metadata_backfilled"] = len(ids)
        if "semantic" in active and semantic_ok and self._semantic is not None:
            ids = missing(pool, "semantic")
            if ids:
                result_s = self._semantic.retrieve(spec, len(ids), restrict_to=ids)
                backfill(
                    pool, "semantic", {h.track_id: h.score for h in result_s.hits}, evaluated=ids
                )
                semantic_hits.update({h.track_id: h for h in result_s.hits})
            counts["semantic_backfilled"] = len(ids)
        if "relationship" in active and self._relationships is not None:
            ids = missing(pool, "relationship")
            backfill(pool, "relationship", self._relationships.score(spec, ids), evaluated=ids)

    def _penalties(self, spec: SearchSpecification, track_ids: list[str]) -> dict[str, float]:
        """LESS_LIKE_THIS references (audio cosine) and negative-preference terms (metadata)."""
        penalties: dict[str, float] = {}
        weights = self._config.penalties
        if self._index is not None and spec.negative_reference_track_ids:
            refs = [
                v
                for r in spec.negative_reference_track_ids
                if (v := self._index.get(r)) is not None
            ]
            if refs:
                matrix = np.stack(refs)
                for track_id in track_ids:
                    vector = self._index.get(track_id)
                    if vector is not None:
                        similarity = float(np.max(matrix @ vector))
                        penalties[track_id] = weights.negative_reference * max(similarity, 0.0)
        for track_id in self._metadata.negative_matches(spec, track_ids):
            penalties[track_id] = penalties.get(track_id, 0.0) + weights.negative_preference
        return penalties
