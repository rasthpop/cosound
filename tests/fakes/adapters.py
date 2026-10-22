"""Fakes for lexical search, audio probing, the LLM and the spatial projection."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from music_discovery.domain.schemas import AudioProbeResult, LLMResult

T = TypeVar("T", bound=BaseModel)


class FakeLexicalIndex:
    """Scores documents by how many query terms they contain (case-insensitive)."""

    def __init__(self, documents: Mapping[str, str]) -> None:
        self._tokens = {doc_id: set(text.casefold().split()) for doc_id, text in documents.items()}

    def search(
        self, terms: Sequence[str], k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        wanted = {t.casefold() for t in terms}
        allowed = None if restrict_to is None else set(restrict_to)
        scored = [
            (doc_id, float(len(wanted & tokens)))
            for doc_id, tokens in self._tokens.items()
            if (allowed is None or doc_id in allowed) and wanted & tokens
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]

    def matches(self, doc_id: str, terms: Sequence[str]) -> list[tuple[str, str]]:
        tokens = self._tokens.get(doc_id, set())
        return [("text", t) for t in terms if t.casefold() in tokens]


class FakeAudioProbe:
    """Every file decodes unless listed in `failures` (path name -> error code)."""

    def __init__(
        self, failures: Mapping[str, str] | None = None, duration_seconds: float = 30.0
    ) -> None:
        self._failures = dict(failures or {})
        self._duration = duration_seconds
        self.probed: list[Path] = []

    def probe(self, path: Path) -> AudioProbeResult:
        self.probed.append(path)
        if path.name in self._failures:
            return AudioProbeResult(ok=False, error_code=self._failures[path.name])
        return AudioProbeResult(ok=True, duration_seconds=self._duration, sample_rate=44100)


@dataclass(frozen=True)
class LLMCall:
    task: str
    system: str
    user: str
    schema: type[BaseModel]


class FakeStructuredLLM:
    """Replays queued responses: a model instance (success) or a string (error code)."""

    def __init__(
        self, responses: Sequence[BaseModel | str] = (), model_id: str = "fake/model:free"
    ) -> None:
        self._responses = list(responses)
        self._model_id = model_id
        self.calls: list[LLMCall] = []

    def generate(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[T],
        timeout_s: float | None = None,
    ) -> LLMResult[T]:
        self.calls.append(LLMCall(task=task, system=system, user=user, schema=schema))
        if not self._responses:
            return LLMResult[T](error_code="unavailable")
        response = self._responses.pop(0)
        if isinstance(response, str):
            return LLMResult[T](error_code=response, model_id=self._model_id)
        if not isinstance(response, schema):
            return LLMResult[T](error_code="invalid_output", raw_text=response.model_dump_json())
        return LLMResult[T](parsed=response, model_id=self._model_id, latency_ms=1.0)


class InMemorySpatialRepository:
    def __init__(
        self,
        coordinates: Mapping[str, tuple[float, float]],
        projection_version: str = "umap-test",
    ) -> None:
        self._coordinates = dict(coordinates)
        self._version = projection_version

    @property
    def projection_version(self) -> str:
        return self._version

    def coordinates(self, track_id: str) -> tuple[float, float] | None:
        return self._coordinates.get(track_id)

    def all_coordinates(self) -> Mapping[str, tuple[float, float]]:
        return dict(self._coordinates)
