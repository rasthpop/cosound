"""Merging retriever results into one candidate pool (base.md §7.4).

Each candidate keeps, per signal, its raw score, its rank and how the value was obtained:

- ``retrieved``: the retriever returned the track in its own top-k;
- ``backfilled``: the track came from another retriever and this signal was scored exactly
  for it afterwards (so ranking is not biased by one retriever's cutoff);
- ``not_available``: the signal cannot exist for this track (e.g. no audio embedding).
  Its value is ``None``, never 0, which would mean "evaluated and irrelevant".
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from music_discovery.domain.enums import RetrievalSource
from music_discovery.retrieval.config import Signal

SignalStatus = Literal["retrieved", "backfilled", "not_available"]
SIGNAL_SOURCE: dict[Signal, RetrievalSource] = {
    "semantic": RetrievalSource.SEMANTIC,
    "metadata": RetrievalSource.METADATA,
    "relationship": RetrievalSource.RELATIONSHIP,
}


@dataclass(frozen=True)
class RankedScore:
    track_id: str
    raw: float
    rank: int


@dataclass(frozen=True)
class SignalValue:
    raw: float | None
    rank: int | None
    status: SignalStatus


@dataclass
class Candidate:
    track_id: str
    signals: dict[Signal, SignalValue] = field(default_factory=dict)

    @property
    def retrieval_sources(self) -> list[RetrievalSource]:
        """Retrievers that returned this track in their own results (not back-filled)."""
        return [SIGNAL_SOURCE[s] for s, v in self.signals.items() if v.status == "retrieved"]

    def raw(self, signal: Signal) -> float | None:
        value = self.signals.get(signal)
        return None if value is None else value.raw

    @property
    def best_rank(self) -> int:
        ranks = [v.rank for v in self.signals.values() if v.status == "retrieved" and v.rank]
        return min(ranks) if ranks else 10**9


@dataclass(frozen=True)
class MergeResult:
    candidates: list[Candidate]
    pool_before_cap: int


def merge(retrieved: Mapping[Signal, Sequence[RankedScore]], *, pool_size: int) -> MergeResult:
    """Union by track id, keeping per-signal provenance; cap the pool by best source rank."""
    by_id: dict[str, Candidate] = {}
    for signal, scores in retrieved.items():
        for score in scores:
            candidate = by_id.setdefault(score.track_id, Candidate(score.track_id))
            candidate.signals[signal] = SignalValue(score.raw, score.rank, "retrieved")
    ordered = sorted(by_id.values(), key=lambda c: (c.best_rank, c.track_id))
    return MergeResult(candidates=ordered[:pool_size], pool_before_cap=len(ordered))


def missing(candidates: Sequence[Candidate], signal: Signal) -> list[str]:
    """Candidates that do not have this signal yet."""
    return [c.track_id for c in candidates if signal not in c.signals]


def backfill(
    candidates: Sequence[Candidate],
    signal: Signal,
    scores: Mapping[str, float],
    *,
    evaluated: Collection[str],
) -> None:
    """Fill `signal` for candidates in `evaluated`: exact score if present, else not_available."""
    for candidate in candidates:
        if signal in candidate.signals or candidate.track_id not in evaluated:
            continue
        raw = scores.get(candidate.track_id)
        candidate.signals[signal] = (
            SignalValue(raw, None, "backfilled")
            if raw is not None
            else SignalValue(None, None, "not_available")
        )
