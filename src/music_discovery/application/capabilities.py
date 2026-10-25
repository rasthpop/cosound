"""Which optional parts of the system are working (base.md §16, `/api/health`).

- semantic: CLAP text encoder + vector index loaded at startup (a later load failure shows up
  per search as a `semantic_unavailable` degraded flag);
- llm_interpreter: `disabled` without an LLM, `fallback` while the OpenRouter circuit breaker
  is open, `available`/`used` otherwise;
- map: a validated projection is loaded.

Each search reports its own capabilities too: what actually ran for that request.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from music_discovery.application.map_service import MapService
from music_discovery.domain.enums import CapabilityStatus, InterpreterStatus
from music_discovery.domain.protocols import Clock

SEMANTIC_FLAG = "semantic_unavailable"


class LLMStatusSource(Protocol):
    @property
    def status(self) -> str:
        """ "available", or "fallback" while the provider is considered down."""
        ...


@dataclass(frozen=True)
class Capabilities:
    semantic: CapabilityStatus
    llm_interpreter: InterpreterStatus
    map: CapabilityStatus
    semantic_reason: str | None = None
    map_reason: str | None = None


@dataclass(frozen=True)
class SearchWarning:
    code: str
    message: str


class CapabilityService:
    def __init__(
        self,
        *,
        semantic_reason: str | None,
        llm: LLMStatusSource | None,
        map_service: MapService,
        clock: Clock,
        ttl_s: float = 5.0,
    ) -> None:
        """`semantic_reason` is None when the semantic retriever was wired at startup."""
        self._semantic_reason = semantic_reason
        self._llm = llm
        self._map = map_service
        self._clock = clock
        self._ttl_s = ttl_s
        self._cached: tuple[float, Capabilities] | None = None

    @property
    def llm_configured(self) -> bool:
        return self._llm is not None

    def current(self) -> Capabilities:
        now = self._clock.now().timestamp()
        if self._cached is not None and now - self._cached[0] < self._ttl_s:
            return self._cached[1]
        if self._llm is None:
            llm = InterpreterStatus.DISABLED
        elif self._llm.status == "available":
            llm = InterpreterStatus.USED
        else:
            llm = InterpreterStatus.FALLBACK
        status = Capabilities(
            semantic=_status(self._semantic_reason is None),
            semantic_reason=self._semantic_reason,
            llm_interpreter=llm,
            map=_status(self._map.available),
            map_reason=self._map.meta().reason,
        )
        self._cached = (now, status)
        return status

    def for_turn(self, *, degraded: Sequence[str], interpreter: str) -> Capabilities:
        """What a single search actually used."""
        base = self.current()
        semantic_down = any(flag.startswith(SEMANTIC_FLAG) for flag in degraded)
        reasons = [f.split(":", 1)[1] for f in degraded if f.startswith(SEMANTIC_FLAG + ":")]
        if self._llm is None:
            llm = InterpreterStatus.DISABLED
        elif interpreter == "llm":
            llm = InterpreterStatus.USED
        else:
            llm = InterpreterStatus.FALLBACK
        return Capabilities(
            semantic=_status(base.semantic is CapabilityStatus.AVAILABLE and not semantic_down),
            semantic_reason=base.semantic_reason or (reasons[0] if reasons else None),
            llm_interpreter=llm,
            map=base.map,
            map_reason=base.map_reason,
        )


def _status(ok: bool) -> CapabilityStatus:
    return CapabilityStatus.AVAILABLE if ok else CapabilityStatus.UNAVAILABLE


WARNING_MESSAGES = {
    "semantic_unavailable": (
        "Audio-semantic search is unavailable; results are ranked on metadata only."
    ),
    "llm_fallback": (
        "The language model did not answer; the query was read by the deterministic parser."
    ),
    "map_unavailable": "The track map is unavailable; results have no map coordinates.",
}


def turn_warnings(
    degraded: Sequence[str], capabilities: Capabilities, *, llm_fallback_reason: str | None
) -> list[SearchWarning]:
    """User-facing notes about degraded parts of one search, deduplicated by code."""
    codes: list[str] = []
    for flag in degraded:
        codes.append(SEMANTIC_FLAG if flag.startswith(SEMANTIC_FLAG) else flag)
    if capabilities.semantic is CapabilityStatus.UNAVAILABLE:
        codes.append(SEMANTIC_FLAG)
    if llm_fallback_reason is not None:
        codes.append("llm_fallback")
    if capabilities.map is CapabilityStatus.UNAVAILABLE:
        codes.append("map_unavailable")
    unique = list(dict.fromkeys(codes))
    return [
        SearchWarning(code, WARNING_MESSAGES.get(code, code.replace("_", " "))) for code in unique
    ]
