"""Deterministic encoders, embedding store and exact vector index for tests."""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

import numpy as np

from music_discovery.domain.protocols import Matrix, Vector


def hashed_unit_vector(text: str, dim: int) -> Vector:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    raw = np.random.default_rng(seed).standard_normal(dim).astype(np.float32)
    return (raw / np.linalg.norm(raw)).astype(np.float32)


class FakeEncoder:
    """Text and audio encoder producing stable, L2-normalized pseudo-embeddings."""

    def __init__(self, dim: int = 16, model_id: str = "fake-clap-v1") -> None:
        self._dim = dim
        self._model_id = model_id
        self.text_calls: list[list[str]] = []
        self.audio_calls: list[list[Path]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def encode_texts(self, texts: Sequence[str]) -> Matrix:
        self.text_calls.append(list(texts))
        return self._stack([f"text:{t}" for t in texts])

    def encode_audio(self, paths: Sequence[Path]) -> Matrix:
        self.audio_calls.append(list(paths))
        return self._stack([f"audio:{p.name}" for p in paths])

    def _stack(self, keys: list[str]) -> Matrix:
        if not keys:
            return np.zeros((0, self._dim), dtype=np.float32)
        return np.stack([hashed_unit_vector(k, self._dim) for k in keys])


class InMemoryEmbeddingStore:
    def __init__(
        self,
        vectors: Mapping[str, Vector],
        *,
        model_id: str = "fake-clap-v1",
        embedding_version: str = "ev-test",
    ) -> None:
        self._vectors = {k: np.asarray(v, dtype=np.float32) for k, v in vectors.items()}
        self._model_id = model_id
        self._version = embedding_version

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def embedding_version(self) -> str:
        return self._version

    def track_ids(self) -> list[str]:
        return sorted(self._vectors)

    def get(self, track_id: str) -> Vector | None:
        return self._vectors.get(track_id)

    def matrix(self) -> tuple[list[str], Matrix]:
        ids = self.track_ids()
        return ids, np.stack([self._vectors[i] for i in ids]) if ids else np.zeros(
            (0, 0), np.float32
        )


class BruteForceVectorIndex:
    """Exact cosine search over a small in-memory set of normalized vectors."""

    def __init__(self, vectors: Mapping[str, Vector], *, model_id: str = "fake-clap-v1") -> None:
        self._vectors = {k: np.asarray(v, dtype=np.float32) for k, v in vectors.items()}
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def search(
        self, query: Vector, k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        q = np.asarray(query, dtype=np.float32)
        q = q / np.linalg.norm(q)
        allowed = None if restrict_to is None else set(restrict_to)
        scored = [
            (track_id, float(np.dot(vec, q) / np.linalg.norm(vec)))
            for track_id, vec in self._vectors.items()
            if allowed is None or track_id in allowed
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]

    def get(self, track_id: str) -> Vector | None:
        return self._vectors.get(track_id)

    def __contains__(self, track_id: object) -> bool:
        return track_id in self._vectors
