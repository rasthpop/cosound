"""Exact cosine vector index (implements `domain.protocols.VectorIndex`).

The catalog is small (thousands of tracks), so exact search with NumPy is fast enough and
gives exact results. FAISS (`IndexFlatIP`) can replace this behind the same protocol later.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

import numpy as np

from music_discovery.domain.errors import EmbeddingVersionMismatch, InvalidEmbedding
from music_discovery.domain.protocols import EmbeddingStore, Matrix, Vector
from music_discovery.domain.vectors import is_unit_norm, l2_normalize


class NumpyCosineIndex:
    def __init__(
        self,
        track_ids: Sequence[str],
        matrix: Matrix,
        *,
        model_id: str,
        embedding_version: str | None = None,
    ) -> None:
        arr = np.asarray(matrix, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(track_ids):
            raise InvalidEmbedding(
                f"index needs (n, d) rows for {len(track_ids)} ids, got {arr.shape}"
            )
        if len(set(track_ids)) != len(track_ids):
            raise InvalidEmbedding("duplicate track ids in index")
        if arr.size and not is_unit_norm(arr):
            raise InvalidEmbedding("index vectors must be L2-normalized")
        self._ids = list(track_ids)
        self._rows = {track_id: i for i, track_id in enumerate(self._ids)}
        self._matrix = arr
        self._model_id = model_id
        self._version = embedding_version

    @classmethod
    def from_store(cls, store: EmbeddingStore) -> NumpyCosineIndex:
        ids, matrix = store.matrix()
        return cls(ids, matrix, model_id=store.model_id, embedding_version=store.embedding_version)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def embedding_version(self) -> str | None:
        return self._version

    @property
    def size(self) -> int:
        return len(self._ids)

    def check_model(self, model_id: str) -> None:
        """Refuse query vectors produced by a different model than the indexed ones."""
        if model_id != self._model_id:
            raise EmbeddingVersionMismatch(
                f"query embedded with {model_id}, index built with {self._model_id}",
                details={"query_model": model_id, "index_model": self._model_id},
            )

    def search(
        self, query: Vector, k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        if k <= 0 or not self._ids:
            return []
        q = l2_normalize(query)
        if q.ndim != 1 or q.shape[0] != self._matrix.shape[1]:
            raise InvalidEmbedding(
                f"query shape {q.shape} does not match index dim {self._matrix.shape[1]}"
            )
        if restrict_to is None:
            rows = np.arange(len(self._ids))
        else:
            rows = np.array(
                sorted({self._rows[t] for t in restrict_to if t in self._rows}), dtype=np.int64
            )
            if rows.size == 0:
                return []
        scores = self._matrix[rows] @ q
        k = min(k, rows.size)
        top = np.argpartition(-scores, k - 1)[:k] if k < rows.size else np.arange(rows.size)
        ranked = sorted(top, key=lambda i: (-float(scores[i]), self._ids[rows[i]]))
        return [(self._ids[rows[i]], float(np.clip(scores[i], -1.0, 1.0))) for i in ranked]

    def get(self, track_id: str) -> Vector | None:
        row = self._rows.get(track_id)
        return None if row is None else self._matrix[row]

    def __contains__(self, track_id: object) -> bool:
        return track_id in self._rows
