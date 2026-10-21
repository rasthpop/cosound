"""Versioned on-disk embedding store (base.md §9.1, implements `domain.protocols.EmbeddingStore`).

Layout of one version::

    data/embeddings/{embedding_version}/
    ├── audio_embeddings.npy   float32 (n, d), L2-normalized
    ├── track_ids.json         row order: internal track ids
    ├── meta.json              model, checkpoint, preprocessing, package versions, counts
    └── failures.csv           track_id, path, error_code, message

The store refuses to load embeddings produced by a different model than the one configured,
so embeddings from different checkpoints can never be mixed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from music_discovery.domain.errors import EmbeddingVersionMismatch, InvalidEmbedding
from music_discovery.domain.protocols import Matrix, Vector
from music_discovery.domain.vectors import is_unit_norm

EMBEDDINGS_FILE = "audio_embeddings.npy"
IDS_FILE = "track_ids.json"
META_FILE = "meta.json"
FAILURES_FILE = "failures.csv"


class EmbeddingFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    track_id: str
    path: str
    error_code: str
    message: str = ""


class EmbeddingMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    embedding_version: str
    model_id: str
    checkpoint_sha256: str | None = None
    preprocessing: dict[str, Any]
    package_versions: dict[str, str]
    created_at: datetime
    manifest_sha256: str | None = None
    n: int = Field(ge=0)
    dim: int = Field(ge=1)
    failures: int = Field(ge=0)


def embedding_version_for(model_id: str, preprocessing: Mapping[str, Any]) -> str:
    """Short, stable hash of everything that changes the meaning of an embedding."""
    canonical = json.dumps({"model_id": model_id, "preprocessing": preprocessing}, sort_keys=True)
    return "ev-" + hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _atomic_write(path: Path, write: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def write_embeddings(
    root: Path,
    meta: EmbeddingMeta,
    track_ids: Sequence[str],
    matrix: Matrix,
    failures: Sequence[EmbeddingFailure] = (),
) -> Path:
    """Persist one embedding version. Validates before writing anything."""
    _validate(track_ids, matrix, meta)
    directory = root / meta.embedding_version
    directory.mkdir(parents=True, exist_ok=True)

    def save_matrix(tmp: Path) -> None:
        with tmp.open("wb") as handle:
            np.save(handle, np.asarray(matrix, dtype=np.float32), allow_pickle=False)

    def save_failures(tmp: Path) -> None:
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EmbeddingFailure.model_fields))
            writer.writeheader()
            for failure in failures:
                writer.writerow(failure.model_dump())

    _atomic_write(directory / EMBEDDINGS_FILE, save_matrix)
    _atomic_write(directory / IDS_FILE, lambda tmp: tmp.write_text(json.dumps(list(track_ids))))
    _atomic_write(directory / FAILURES_FILE, save_failures)
    # meta.json last: its presence marks a complete version
    _atomic_write(directory / META_FILE, lambda tmp: tmp.write_text(meta.model_dump_json(indent=2)))
    return directory


def _validate(track_ids: Sequence[str], matrix: Matrix, meta: EmbeddingMeta) -> None:
    arr = np.asarray(matrix)
    if arr.ndim != 2:
        raise InvalidEmbedding(f"embedding matrix must be 2-d, got shape {arr.shape}")
    if arr.shape[0] != len(track_ids):
        raise InvalidEmbedding(f"{arr.shape[0]} rows for {len(track_ids)} track ids")
    if len(set(track_ids)) != len(track_ids):
        raise InvalidEmbedding("duplicate track ids in embedding store")
    if arr.shape[0] and arr.shape[1] != meta.dim:
        raise InvalidEmbedding(f"matrix dim {arr.shape[1]} != meta dim {meta.dim}")
    if meta.n != arr.shape[0]:
        raise InvalidEmbedding(f"meta n={meta.n} but matrix has {arr.shape[0]} rows")
    if arr.size and not np.all(np.isfinite(arr)):
        raise InvalidEmbedding("embedding matrix contains NaN or infinite values")
    if arr.size and not is_unit_norm(arr):
        raise InvalidEmbedding("embeddings must be L2-normalized")


class NpyEmbeddingStore:
    """Read-only view of one persisted embedding version."""

    def __init__(self, meta: EmbeddingMeta, track_ids: list[str], matrix: Matrix) -> None:
        _validate(track_ids, matrix, meta)
        self._meta = meta
        self._ids = track_ids
        self._matrix = matrix
        self._rows = {track_id: i for i, track_id in enumerate(track_ids)}

    @classmethod
    def load(cls, directory: Path, *, expected_model_id: str | None) -> NpyEmbeddingStore:
        meta_path = directory / META_FILE
        if not meta_path.is_file():
            raise InvalidEmbedding(f"no complete embedding version at {directory}")
        meta = EmbeddingMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        if expected_model_id is not None and meta.model_id != expected_model_id:
            raise EmbeddingVersionMismatch(
                f"embeddings in {directory} were made with {meta.model_id}, "
                f"but {expected_model_id} is configured",
                details={"stored": meta.model_id, "configured": expected_model_id},
            )
        track_ids = json.loads((directory / IDS_FILE).read_text(encoding="utf-8"))
        matrix = np.load(directory / EMBEDDINGS_FILE, allow_pickle=False).astype(np.float32)
        return cls(meta, list(track_ids), matrix)

    @property
    def meta(self) -> EmbeddingMeta:
        return self._meta

    @property
    def model_id(self) -> str:
        return self._meta.model_id

    @property
    def embedding_version(self) -> str:
        return self._meta.embedding_version

    def track_ids(self) -> list[str]:
        return list(self._ids)

    def get(self, track_id: str) -> Vector | None:
        row = self._rows.get(track_id)
        return None if row is None else self._matrix[row]

    def matrix(self) -> tuple[list[str], Matrix]:
        return list(self._ids), self._matrix


def resolve_version_dir(root: Path, active: str | None) -> Path:
    """The configured embedding version, or else the most recently created complete one."""
    if active:
        directory = root / active
        if not (directory / META_FILE).is_file():
            raise InvalidEmbedding(f"ACTIVE_EMBEDDING_VERSION {active} not found under {root}")
        return directory
    candidates = [d for d in root.glob("ev-*") if (d / META_FILE).is_file()]
    if not candidates:
        raise InvalidEmbedding(
            f"no embedding versions under {root}; run scripts/build_embeddings.py"
        )

    def created(directory: Path) -> datetime:
        meta = EmbeddingMeta.model_validate_json(
            (directory / META_FILE).read_text(encoding="utf-8")
        )
        return meta.created_at

    return max(candidates, key=lambda d: (created(d), d.name))


def read_failures(directory: Path) -> list[EmbeddingFailure]:
    path = directory / FAILURES_FILE
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [EmbeddingFailure.model_validate(row) for row in csv.DictReader(handle)]
