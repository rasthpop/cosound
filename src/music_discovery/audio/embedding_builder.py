"""Offline audio-embedding generation (base.md §9.1).

Reads the validated audio of the selected tracks, encodes each file once, writes a versioned
embedding store, and marks the tracks as analyzed in the catalog. Per-track vectors are cached
while the run progresses, so an interrupted run resumes instead of starting over. A file that
cannot be decoded or encoded is reported as a failure and skipped; it never stops the run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from music_discovery.audio.embedding_store import (
    META_FILE,
    EmbeddingFailure,
    EmbeddingMeta,
    embedding_version_for,
    write_embeddings,
)
from music_discovery.domain.errors import AudioError, EmbeddingError
from music_discovery.domain.models import TrackAudio
from music_discovery.domain.protocols import (
    Clock,
    Matrix,
    TrackAudioRepository,
    TrackRepository,
    UnitOfWork,
    Vector,
)
from music_discovery.domain.vectors import l2_normalize

log = logging.getLogger(__name__)

PACKAGES = ("numpy", "scipy", "soundfile", "torch", "transformers")


class BuildableEncoder(Protocol):
    """An `AudioEncoder` that also describes its preprocessing (for the embedding version)."""

    @property
    def model_id(self) -> str: ...
    @property
    def embedding_dim(self) -> int: ...
    def encode_audio(self, paths: Sequence[Path]) -> Matrix: ...
    def preprocessing(self) -> dict[str, Any]: ...


@dataclass
class BuildReport:
    embedding_version: str
    directory: Path | None
    requested: int = 0
    embedded: int = 0
    from_cache: int = 0
    skipped_existing: bool = False
    failures: list[EmbeddingFailure] = field(default_factory=list)


def _package_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            continue
    return versions


def _inputs_sha256(audio: Sequence[TrackAudio]) -> str:
    canonical = json.dumps(sorted((a.track_id, a.file_path) for a in audio))
    return hashlib.sha256(canonical.encode()).hexdigest()


class EmbeddingBuilder:
    def __init__(
        self,
        encoder: BuildableEncoder,
        audio: TrackAudioRepository,
        tracks: TrackRepository,
        uow: UnitOfWork,
        *,
        data_dir: Path,
        embeddings_dir: Path,
        clock: Clock,
        checkpoint_sha256: str | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        self._encoder = encoder
        self._audio = audio
        self._tracks = tracks
        self._uow = uow
        self._data_dir = data_dir
        self._root = embeddings_dir
        self._clock = clock
        self._checkpoint_sha256 = checkpoint_sha256
        self._progress = progress

    def version(self) -> str:
        return embedding_version_for(self._encoder.model_id, self._encoder.preprocessing())

    def run(
        self,
        *,
        track_ids: Sequence[str] | None = None,
        manifest_sha256: str | None = None,
        force: bool = False,
    ) -> BuildReport:
        version_id = self.version()
        selected = self._select(track_ids)
        report = BuildReport(embedding_version=version_id, directory=None, requested=len(selected))
        directory = self._root / version_id
        inputs_sha = _inputs_sha256(selected)

        existing = directory / META_FILE
        if existing.is_file() and not force:
            meta = EmbeddingMeta.model_validate_json(existing.read_text(encoding="utf-8"))
            if meta.preprocessing.get("inputs_sha256") == inputs_sha:
                report.directory = directory
                report.skipped_existing = True
                report.embedded = meta.n
                return report
            raise EmbeddingError(
                f"{directory} holds embeddings for a different track set; rerun with force=True",
                details={"embedding_version": version_id},
            )

        cache = self._root / "cache" / version_id
        cache.mkdir(parents=True, exist_ok=True)
        ids: list[str] = []
        rows: list[Vector] = []
        for done, audio in enumerate(selected, start=1):
            vector = self._vector(audio, cache, report)
            if vector is not None:
                ids.append(audio.track_id)
                rows.append(vector)
            if self._progress is not None:
                self._progress(done, len(selected))

        matrix = np.stack(rows) if rows else np.zeros((0, self._encoder.embedding_dim), np.float32)
        meta = EmbeddingMeta(
            embedding_version=version_id,
            model_id=self._encoder.model_id,
            checkpoint_sha256=self._checkpoint_sha256,
            preprocessing={**self._encoder.preprocessing(), "inputs_sha256": inputs_sha},
            package_versions=_package_versions(),
            created_at=self._clock.now(),
            manifest_sha256=manifest_sha256,
            n=len(ids),
            dim=int(matrix.shape[1]) if matrix.size else self._encoder.embedding_dim,
            failures=len(report.failures),
        )
        report.directory = write_embeddings(self._root, meta, ids, matrix, report.failures)
        self._mark_analyzed(ids, version_id)
        report.embedded = len(ids)
        return report

    def _select(self, track_ids: Sequence[str] | None) -> list[TrackAudio]:
        records = self._audio.list_all()
        if track_ids is not None:
            wanted = set(track_ids)
            records = [a for a in records if a.track_id in wanted]
        return sorted(records, key=lambda a: a.track_id)

    def _vector(self, audio: TrackAudio, cache: Path, report: BuildReport) -> Vector | None:
        cached = cache / f"{audio.track_id}.npy"
        if cached.is_file():
            report.from_cache += 1
            loaded: Vector = np.load(cached, allow_pickle=False).astype(np.float32)
            return loaded
        path = self._data_dir / audio.file_path
        try:
            vector = l2_normalize(self._encoder.encode_audio([path])[0])
        except (AudioError, EmbeddingError) as exc:
            report.failures.append(
                EmbeddingFailure(
                    track_id=audio.track_id,
                    path=audio.file_path,
                    error_code=exc.code,
                    message=exc.message,
                )
            )
            log.warning("embedding failed for %s: %s", audio.track_id, exc.code)
            return None
        tmp = cached.with_name(cached.name + ".tmp")
        with tmp.open("wb") as handle:
            np.save(handle, vector, allow_pickle=False)
        tmp.replace(cached)
        return vector

    def _mark_analyzed(self, track_ids: Sequence[str], version_id: str) -> None:
        """Record the embedding on TrackAudio and Track (`audio_available` becomes true)."""
        model_id = self._encoder.model_id
        for start in range(0, len(track_ids), 500):
            chunk = track_ids[start : start + 500]
            with self._uow.transaction():
                for track in self._tracks.get_many(chunk):
                    audio = self._audio.get(track.id)
                    if audio is not None:
                        self._audio.upsert(
                            audio.model_copy(
                                update={
                                    "embedding_model": model_id,
                                    "embedding_version": version_id,
                                    "embedding_path": f"embeddings/{version_id}",
                                }
                            )
                        )
                    self._tracks.upsert(track.model_copy(update={"audio_embedding_id": version_id}))
