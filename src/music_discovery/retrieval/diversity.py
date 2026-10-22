"""Diversity-aware reranking with maximal marginal relevance (base.md §7.6).

    next = argmax_{t not chosen}  lambda * rel(t) - (1 - lambda) * max_{s chosen} sim(t, s)
    lambda = 1 - spec.diversity * config.diversity.scale

The first pick is always the most relevant track. Similarity is the audio cosine when both
tracks have embeddings, else the overlap of artist, album and genres. Duplicates (practically
identical audio, e.g. FMA double uploads, or the same Discogs master) of a chosen track are
dropped, so a plate never shows the same recording twice. Same album is *not* a duplicate:
in FMA an album holds different songs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np

from music_discovery.domain.models import Track
from music_discovery.domain.protocols import VectorIndex
from music_discovery.retrieval.ranker import Scored


def mmr_lambda(diversity: float, scale: float) -> float:
    return 1.0 - diversity * scale


class TrackSimilarity:
    def __init__(
        self, tracks: Mapping[str, Track], index: VectorIndex | None, *, duplicate_cosine: float
    ) -> None:
        self._tracks = tracks
        self._index = index
        self._duplicate_cosine = duplicate_cosine

    def _audio(self, a: str, b: str) -> float | None:
        if self._index is None:
            return None
        va, vb = self._index.get(a), self._index.get(b)
        if va is None or vb is None:
            return None
        return float(np.clip(np.dot(va, vb), -1.0, 1.0))

    def _catalog(self, a: str, b: str) -> float:
        ta, tb = self._tracks.get(a), self._tracks.get(b)
        if ta is None or tb is None:
            return 0.0

        def features(t: Track) -> set[str]:
            items = {f"artist:{x.artist_id}" for x in t.artists} | {
                f"genre:{g.casefold()}" for g in t.genres
            }
            if t.release_id:
                items.add(f"release:{t.release_id}")
            return items

        fa, fb = features(ta), features(tb)
        return len(fa & fb) / len(fa | fb) if fa | fb else 0.0

    def similarity(self, a: str, b: str) -> float:
        audio = self._audio(a, b)
        return audio if audio is not None else self._catalog(a, b)

    def is_duplicate(self, a: str, b: str) -> bool:
        audio = self._audio(a, b)
        if audio is not None and audio >= self._duplicate_cosine:
            return True
        ta, tb = self._tracks.get(a), self._tracks.get(b)
        return bool(
            ta and tb and ta.master_release_id and ta.master_release_id == tb.master_release_id
        )


def mmr(
    scored: Sequence[Scored],
    k: int,
    *,
    lambda_: float,
    similarity: Callable[[str, str], float],
    is_duplicate: Callable[[str, str], bool],
) -> list[Scored]:
    """Pick k items; `scored` must be ordered by relevance (ties broken by track id)."""
    remaining = list(scored)
    chosen: list[Scored] = []
    while remaining and len(chosen) < k:
        best_index = 0
        best_value = -float("inf")
        for i, item in enumerate(remaining):
            redundancy = max(
                (similarity(item.candidate.track_id, c.candidate.track_id) for c in chosen),
                default=0.0,
            )
            value = lambda_ * item.relevance - (1.0 - lambda_) * redundancy
            if value > best_value + 1e-12:  # strict: earlier (more relevant) items win ties
                best_index, best_value = i, value
        pick = remaining.pop(best_index)
        chosen.append(pick)
        pick_id = pick.candidate.track_id
        remaining = [r for r in remaining if not is_duplicate(r.candidate.track_id, pick_id)]
    return chosen
