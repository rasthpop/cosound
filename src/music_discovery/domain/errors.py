"""Domain error hierarchy (base.md §16).

Every error has a stable machine `code`. The API layer maps codes to HTTP statuses and never
inspects messages. Situations that are normal outcomes rather than failures are *not* errors:
missing metadata stays `None`, and "no relevant candidates" is the
`SearchOutcomeKind.NO_CONFIDENT_MATCH` outcome.
"""

from __future__ import annotations

from typing import Any, ClassVar


class MusicDiscoveryError(Exception):
    code: ClassVar[str] = "music_discovery_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


# --- External data sources -------------------------------------------------


class DataSourceError(MusicDiscoveryError):
    code = "data_source_error"


class DiscogsRateLimited(DataSourceError):
    code = "discogs_rate_limited"

    def __init__(
        self,
        message: str,
        *,
        retry_after_s: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after_s = retry_after_s


class DiscogsUnavailable(DataSourceError):
    code = "discogs_unavailable"


class DiscogsNotFound(DataSourceError):
    code = "discogs_not_found"


class DiscogsAuthError(DataSourceError):
    code = "discogs_auth_error"


class DiscogsResponseInvalid(DataSourceError):
    code = "discogs_response_invalid"


# --- Audio -------------------------------------------------------------------


class AudioError(MusicDiscoveryError):
    code = "audio_error"


class AudioMissing(AudioError):
    code = "audio_missing"


class AudioDecodeError(AudioError):
    code = "audio_decode_error"


# --- Embeddings & indexes ----------------------------------------------------


class EmbeddingError(MusicDiscoveryError):
    code = "embedding_error"


class ModelLoadError(EmbeddingError):
    code = "model_load_error"


class InvalidEmbedding(EmbeddingError):
    code = "invalid_embedding"


class EmbeddingVersionMismatch(EmbeddingError):
    code = "embedding_version_mismatch"


class IndexEntryMissing(EmbeddingError):
    code = "index_entry_missing"


# --- Agents --------------------------------------------------------------------


class AgentOutputError(MusicDiscoveryError):
    """Invalid structured output from an agent or LLM. Callers fall back to deterministic logic."""

    code = "agent_output_invalid"


# --- Constraints ---------------------------------------------------------------


class ConstraintError(MusicDiscoveryError):
    code = "constraint_error"


class ContradictoryConstraintsError(ConstraintError):
    code = "contradictory_constraints"


class InvalidConstraintError(ConstraintError):
    code = "invalid_constraint"


# --- Spatial artifacts -----------------------------------------------------------


class SpatialArtifactError(MusicDiscoveryError):
    code = "spatial_artifact_error"


class ProjectionMissing(SpatialArtifactError):
    code = "projection_unavailable"


class ProjectionMismatch(SpatialArtifactError):
    code = "projection_mismatch"


# --- Sessions & feedback -----------------------------------------------------------


class SessionError(MusicDiscoveryError):
    code = "session_error"


class SessionNotFound(SessionError):
    code = "session_not_found"


class QueryNotInSession(SessionError):
    code = "query_not_in_session"


class TrackNotInResults(SessionError):
    code = "track_not_in_results"


class InvalidFeedbackEvent(SessionError):
    code = "invalid_feedback_event"


class StaleSessionVersion(SessionError):
    """Optimistic-concurrency conflict: the session changed since it was read."""

    code = "stale_session_version"


# --- Lookups ---------------------------------------------------------------------------


class NotFoundError(MusicDiscoveryError):
    code = "not_found"


class TrackNotFound(NotFoundError):
    code = "track_not_found"
