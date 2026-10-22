"""Retrieval metrics (base.md §12.6, retrieval-evaluation skill §3).

`rel(q, t)` is the 0-3 overall relevance; a track is relevant iff rel >= threshold (default 2).
Undefined values are `None`, never 0, and are left out of means (with n reported).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DEFAULT_K = 5
DEFAULT_THRESHOLD = 2


def precision_at_k(
    ranked: Sequence[int],
    rel: Mapping[int, int],
    *,
    k: int = DEFAULT_K,
    threshold: int = DEFAULT_THRESHOLD,
) -> float:
    """|relevant in top k| / k; the denominator stays k even if fewer results were returned."""
    hits = sum(1 for t in ranked[:k] if rel.get(t, 0) >= threshold)
    return hits / k


def recall_at_k(
    ranked: Sequence[int],
    rel: Mapping[int, int],
    *,
    k: int = DEFAULT_K,
    threshold: int = DEFAULT_THRESHOLD,
) -> float | None:
    relevant = {t for t, r in rel.items() if r >= threshold}
    if not relevant:
        return None
    return len(relevant & set(ranked[:k])) / len(relevant)


def dcg(gains: Sequence[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: Sequence[int], rel: Mapping[int, int], *, k: int = DEFAULT_K) -> float | None:
    """Linear gains; IDCG from the ideal ordering of *all* judged tracks; None if IDCG = 0."""
    ideal = dcg(sorted(rel.values(), reverse=True)[:k])
    if ideal == 0:
        return None
    return dcg([rel.get(t, 0) for t in ranked[:k]]) / ideal


def reciprocal_rank(
    ranked: Sequence[int], rel: Mapping[int, int], *, threshold: int = DEFAULT_THRESHOLD
) -> float | None:
    """1 / rank of the first relevant result; 0 if none returned; None if nothing is relevant."""
    if not any(r >= threshold for r in rel.values()):
        return None
    for position, track in enumerate(ranked, start=1):
        if rel.get(track, 0) >= threshold:
            return 1 / position
    return 0.0


@dataclass(frozen=True)
class ConstraintRate:
    satisfied: float
    unknown: float
    violated: float
    n: int


def constraint_satisfaction(
    statuses: Sequence[str | None], *, k: int = DEFAULT_K
) -> ConstraintRate | None:
    """Shares of the top-k results judged `yes` / `unknown` / `no` (missing judgment = unknown)."""
    top = list(statuses[:k])
    if not top:
        return None
    n = len(top)
    return ConstraintRate(
        satisfied=sum(s == "yes" for s in top) / n,
        unknown=sum(s in (None, "unknown") for s in top) / n,
        violated=sum(s == "no" for s in top) / n,
        n=n,
    )


@dataclass(frozen=True)
class Mean:
    value: float | None
    n: int


def mean(values: Sequence[float | None]) -> Mean:
    defined = [v for v in values if v is not None]
    return Mean(sum(defined) / len(defined) if defined else None, len(defined))
