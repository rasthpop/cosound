"""Embedding normalization and cosine similarity (base.md §9.2).

Vectors are stored L2-normalized as float32, so cosine similarity is a dot product.
Zero and non-finite vectors are errors, never silently zeroed.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from music_discovery.domain.errors import InvalidEmbedding

EPS = 1e-12
UNIT_NORM_TOLERANCE = 1e-3

FloatArray = npt.NDArray[np.float32]


def l2_normalize(x: npt.ArrayLike) -> FloatArray:
    """Normalize a vector (d,) or each row of a matrix (n, d)."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim not in (1, 2) or arr.shape[-1] == 0:
        raise InvalidEmbedding(f"expected a vector or matrix, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise InvalidEmbedding("embedding contains NaN or infinite values")
    norms = np.linalg.norm(arr, axis=-1, keepdims=True)
    if np.any(norms < EPS):
        raise InvalidEmbedding("embedding is a zero vector")
    return (arr / norms).astype(np.float32)


def is_unit_norm(x: npt.ArrayLike, tolerance: float = UNIT_NORM_TOLERANCE) -> bool:
    arr = np.asarray(x, dtype=np.float32)
    return bool(np.all(np.abs(np.linalg.norm(arr, axis=-1) - 1.0) <= tolerance))


def cosine(a: npt.ArrayLike, b: npt.ArrayLike) -> float:
    """Cosine similarity of two vectors in [-1, 1]."""
    va, vb = l2_normalize(a), l2_normalize(b)
    if va.ndim != 1 or vb.ndim != 1 or va.shape != vb.shape:
        raise InvalidEmbedding(f"cannot compare shapes {va.shape} and {vb.shape}")
    return float(np.clip(np.dot(va, vb), -1.0, 1.0))
