"""Interfaces that services depend on. Concrete implementations live outside the domain.

Every protocol has an in-memory fake in `tests/fakes/`, checked against it by mypy.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel

from music_discovery.domain.enums import DataSource, MatchStatus, RelationshipType
from music_discovery.domain.ids import ExternalId, IdPrefix
from music_discovery.domain.models import (
    Artist,
    CrossSourceMatch,
    ImportRun,
    Label,
    Release,
    SearchSession,
    Track,
    TrackAudio,
    TrackRelationship,
)
from music_discovery.domain.schemas import AudioProbeResult, FeedbackEvent, LLMResult

Vector = npt.NDArray[np.float32]
"""A single embedding, shape (d,)."""
Matrix = npt.NDArray[np.float32]
"""Row-stacked embeddings, shape (n, d)."""

T = TypeVar("T", bound=BaseModel)

# --- Infrastructure basics -----------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...
    def sleep(self, seconds: float) -> None: ...


@runtime_checkable
class IdGenerator(Protocol):
    def new(self, prefix: IdPrefix) -> str: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Groups repository writes so they commit or roll back together."""

    def transaction(self) -> AbstractContextManager[None]: ...


# --- Catalog repositories ------------------------------------------------------------


@runtime_checkable
class TrackRepository(Protocol):
    def get(self, track_id: str) -> Track | None: ...
    def get_many(self, track_ids: Sequence[str]) -> list[Track]:
        """Tracks in the requested order; unknown ids are skipped."""
        ...

    def find_by_external_id(self, external_id: ExternalId) -> Track | None: ...
    def upsert(self, track: Track) -> None: ...
    def list_page(self, *, limit: int, after: str | None = None) -> list[Track]:
        """Tracks ordered by id, starting after the given id (keyset pagination)."""
        ...

    def count(self) -> int: ...


@runtime_checkable
class ReleaseRepository(Protocol):
    def get(self, release_id: str) -> Release | None: ...
    def find_by_external_id(self, external_id: ExternalId) -> Release | None: ...
    def upsert(self, release: Release) -> None: ...


@runtime_checkable
class ArtistRepository(Protocol):
    def get(self, artist_id: str) -> Artist | None: ...
    def find_by_external_id(self, external_id: ExternalId) -> Artist | None: ...
    def upsert(self, artist: Artist) -> None: ...


@runtime_checkable
class LabelRepository(Protocol):
    def get(self, label_id: str) -> Label | None: ...
    def find_by_external_id(self, external_id: ExternalId) -> Label | None: ...
    def upsert(self, label: Label) -> None: ...


@runtime_checkable
class TrackAudioRepository(Protocol):
    def get(self, track_id: str) -> TrackAudio | None: ...
    def upsert(self, audio: TrackAudio) -> None: ...
    def list_all(self) -> list[TrackAudio]: ...


@runtime_checkable
class RelationshipRepository(Protocol):
    def upsert(self, relationship: TrackRelationship) -> None: ...
    def for_track(
        self, track_id: str, types: Collection[RelationshipType] | None = None
    ) -> list[TrackRelationship]:
        """Relationships where the track is the source, ordered by (type, target)."""
        ...

    def replace_all(self, relationships: Sequence[TrackRelationship]) -> None:
        """Swap the whole derived graph in one step (recomputation is idempotent)."""
        ...


@runtime_checkable
class MatchRepository(Protocol):
    """Cross-source match decisions, keyed by (track_id, target)."""

    def upsert(self, match: CrossSourceMatch) -> None: ...
    def for_track(self, track_id: str) -> list[CrossSourceMatch]: ...
    def list_by_status(self, status: MatchStatus) -> list[CrossSourceMatch]: ...


@runtime_checkable
class ImportRunRepository(Protocol):
    def save(self, run: ImportRun) -> None: ...
    def get(self, run_id: str) -> ImportRun | None: ...
    def latest(self, source: DataSource) -> ImportRun | None: ...


# --- Sessions & feedback -------------------------------------------------------------


@runtime_checkable
class SessionRepository(Protocol):
    def get(self, session_id: str) -> SearchSession | None: ...
    def save(self, session: SearchSession, *, expected_version: int | None) -> None:
        """Store a session. `expected_version` is the version that was read (None = new).

        Raises `StaleSessionVersion` if the stored version differs.
        """
        ...


@runtime_checkable
class FeedbackRepository(Protocol):
    def add(self, event: FeedbackEvent) -> None: ...
    def for_session(self, session_id: str) -> list[FeedbackEvent]: ...


# --- Embeddings & search -------------------------------------------------------------


@runtime_checkable
class TextEncoder(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def embedding_dim(self) -> int: ...
    def encode_texts(self, texts: Sequence[str]) -> Matrix: ...


@runtime_checkable
class AudioEncoder(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def embedding_dim(self) -> int: ...
    def encode_audio(self, paths: Sequence[Path]) -> Matrix: ...


@runtime_checkable
class EmbeddingStore(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def embedding_version(self) -> str: ...
    def track_ids(self) -> list[str]: ...
    def get(self, track_id: str) -> Vector | None: ...
    def matrix(self) -> tuple[list[str], Matrix]: ...


@runtime_checkable
class VectorIndex(Protocol):
    @property
    def model_id(self) -> str: ...
    def search(
        self, query: Vector, k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        """Top-k (track_id, cosine) pairs, best first. Tracks without embeddings never appear."""
        ...

    def get(self, track_id: str) -> Vector | None: ...
    def __contains__(self, track_id: object) -> bool: ...


@runtime_checkable
class LexicalIndex(Protocol):
    def search(
        self, terms: Sequence[str], k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]: ...


# --- Audio, LLM, spatial -------------------------------------------------------------


@runtime_checkable
class AudioProbe(Protocol):
    def probe(self, path: Path) -> AudioProbeResult: ...


@runtime_checkable
class StructuredLLM(Protocol):
    """Optional LLM (OpenRouter free models). Returns an error result instead of raising."""

    def generate(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[T],
        timeout_s: float | None = None,
    ) -> LLMResult[T]: ...


@runtime_checkable
class SpatialRepository(Protocol):
    @property
    def projection_version(self) -> str: ...
    def coordinates(self, track_id: str) -> tuple[float, float] | None: ...
    def all_coordinates(self) -> Mapping[str, tuple[float, float]]: ...
