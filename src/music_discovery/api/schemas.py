"""Public HTTP contract (base.md §13 + api-contracts additions). Wire format only.

DTOs are mapped from application results in `api/mapping.py`; domain and ORM objects never
leave the API. Rules that hold for every DTO:

- missing values are `null`, never 0 / "" / a made-up link;
- `score` fields are relevance scores in [0, 1] for ordering, not probabilities;
- MVP (ADR-0005): tracks expose `source_url` (the FMA track page); `preview_url` points to
  `/api/tracks/{id}/audio` only when a validated local clip exists.

Every response DTO carries examples (from `api/examples.py`) that are exported as frontend
fixtures and validated against these schemas in tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from music_discovery.domain.enums import (
    CapabilityStatus,
    ConstraintStatus,
    EvidenceStatus,
    FeedbackType,
    InterpreterStatus,
    MatchStrength,
    NextAction,
    RelationshipType,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.schemas import ConstraintAttribute, ConstraintOperator

API_VERSION = "1"
MAX_SEARCH_LIMIT = 100
MAX_QUERY_LENGTH = 500
MAX_FREE_TEXT_LENGTH = 500


def _examples(schema: dict[str, Any], cls: type[BaseModel]) -> None:
    from music_discovery.api.examples import examples_for  # examples build these classes

    found = examples_for(cls)
    if found:
        schema["examples"] = found


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_examples)


# --- Shared parts -----------------------------------------------------------------------


class ErrorBody(ApiModel):
    code: str = Field(description="Stable machine code, e.g. `track_not_found`.")
    message: str
    details: dict[str, JsonValue] = {}


class ErrorResponse(ApiModel):
    """The envelope of every non-2xx response."""

    error: ErrorBody


class Capabilities(ApiModel):
    semantic: CapabilityStatus
    llm_interpreter: InterpreterStatus
    map: CapabilityStatus


class ApiWarning(ApiModel):
    code: str = Field(description="e.g. `semantic_unavailable`, `llm_fallback`, `map_unavailable`")
    message: str


class Artist(ApiModel):
    artist_id: str
    name: str


class Spatial(ApiModel):
    """UMAP visualization coordinates; not a similarity measure."""

    x: float
    y: float
    projection_version: str


# --- Interpreted query ----------------------------------------------------------------


class Preference(ApiModel):
    value: str
    weight: float = Field(ge=0, le=1)
    source_span: str | None = None


class HardConstraint(ApiModel):
    attribute: ConstraintAttribute
    operator: ConstraintOperator
    value: str | None = None
    range: tuple[float | None, float | None] | None = None


class InterpretedQuery(ApiModel):
    """Public view of Agent A's SearchSpecification."""

    spec_version: int
    original_query: str
    mood_preferences: list[Preference]
    instrument_preferences: list[Preference]
    genre_preferences: list[Preference]
    tempo_preferences: list[Preference]
    energy_preferences: list[Preference]
    texture_preferences: list[Preference]
    era_preferences: list[Preference]
    vocal_preferences: Literal["required", "preferred", "avoided", "excluded", "unspecified"]
    hard_constraints: list[HardConstraint]
    negative_preferences: list[Preference]
    reference_track_ids: list[str]
    negative_reference_track_ids: list[str]
    excluded_track_ids: list[str]
    semantic_prompts: list[str]
    diversity: float
    uncertainties: list[str]
    interpreter: Literal["deterministic", "llm"]
    interpreter_model: str | None


# --- Search -------------------------------------------------------------------------------


class SearchRequest(ApiModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=10, ge=1, le=MAX_SEARCH_LIMIT)
    session_id: str | None = Field(
        default=None, description="Continue an existing session (follow-up query)."
    )


class ScoreBreakdown(ApiModel):
    """Normalized signals; `null` means the signal was not computed for this track."""

    semantic: float | None
    metadata: float | None
    relationship: float | None
    final: float


class ScoreBands(ApiModel):
    """Strength band per signal within this query; `null` = the signal is missing for this track
    (or has no calibrated bands). Show these, never the numbers."""

    semantic: MatchStrength | None
    metadata: MatchStrength | None
    relationship: MatchStrength | None


class ConstraintCheck(ApiModel):
    attribute: ConstraintAttribute
    operator: ConstraintOperator
    value: str | None
    status: ConstraintStatus


class TrackResult(ApiModel):
    track_id: str
    rank: int = Field(ge=1)
    title: str
    artists: list[Artist]
    score: float = Field(ge=0, le=1, description="Relevance for ordering; not a probability.")
    score_breakdown: ScoreBreakdown
    match_strength: MatchStrength | None = Field(
        description=(
            "Band of the audio (CLAP) match within this query, the one match_reasons describe; "
            "null when the track has no semantic score."
        )
    )
    score_bands: ScoreBands
    description: str | None = Field(description="Evidence-grounded text; null when too thin.")
    match_reasons: list[str]
    genres: list[str]
    styles: list[str]
    source_url: str | None
    preview_url: str | None
    audio_available: bool = Field(description="An audio embedding exists (audio was analyzed).")
    evidence_status: EvidenceStatus
    constraint_status: list[ConstraintCheck]
    uncertainty_flags: list[str]
    retrieval_sources: list[RetrievalSource]
    spatial: Spatial | None


class SearchResponse(ApiModel):
    query_id: str | None = Field(description="Null only when no search ran.")
    session_id: str
    outcome: SearchOutcomeKind
    clarification_question: str | None
    no_match_reasons: list[str] = Field(
        description="Why nothing was confident (outcome no_confident_match)."
    )
    interpreted_query: InterpretedQuery
    results: list[TrackResult]
    capabilities: Capabilities
    warnings: list[ApiWarning]
    change_summary: list[str] = Field(description="What changed since the previous turn.")


# --- Tracks ---------------------------------------------------------------------------------


class Release(ApiModel):
    release_id: str
    title: str
    year: int | None


class AudioInfo(ApiModel):
    duration_seconds: float | None
    license: str | None


class RelatedTrack(ApiModel):
    track_id: str
    title: str
    artists: list[Artist]
    relationship_type: RelationshipType


class TrackDetail(ApiModel):
    track_id: str
    title: str
    artists: list[Artist]
    release: Release | None
    year: int | None
    genres: list[str]
    styles: list[str]
    tags: list[str]
    duration_seconds: float | None
    source_url: str | None
    preview_url: str | None
    audio_available: bool
    evidence_status: EvidenceStatus
    audio: AudioInfo | None = Field(description="The validated local clip, when there is one.")
    related_tracks: list[RelatedTrack] = Field(
        description="Catalog context (not audio similarity); capped per relationship type."
    )
    relationship_counts: dict[str, int]
    spatial: Spatial | None


class Neighbor(ApiModel):
    track_id: str
    title: str
    artists: list[Artist]
    score: float | None = Field(
        description="Cosine for clap_cosine; the relationship weight (often null) otherwise."
    )
    relationship_types: list[RelationshipType]
    audio_available: bool
    spatial: Spatial | None


class NeighborsResponse(ApiModel):
    track_id: str
    metric: Literal["clap_cosine", "catalog_relationship"]
    model_id: str | None
    reason: Literal["no_audio_embedding", "semantic_unavailable"] | None = Field(
        description="Why audio neighbors are missing; null for clap_cosine."
    )
    neighbors: list[Neighbor]


# --- Feedback & sessions ------------------------------------------------------------------


class FeedbackRequest(ApiModel):
    session_id: str
    query_id: str
    event_type: FeedbackType | None = Field(
        default=None, description="Typed event; omit to send free_text only."
    )
    track_id: str | None = None
    attribute: str | None = None
    value: bool | float | str | None = None
    free_text: str | None = Field(default=None, max_length=MAX_FREE_TEXT_LENGTH)
    refresh: bool = Field(default=False, description="Return the refreshed plate.")
    limit: int = Field(default=10, ge=1, le=MAX_SEARCH_LIMIT)


class SearchState(ApiModel):
    session_id: str
    session_version: int
    interpreted_query: InterpretedQuery


class FeedbackResponse(ApiModel):
    accepted: bool
    reason: str | None = Field(description="Why the feedback was not applied.")
    updated_search_state: SearchState
    change_summary: list[str]
    next_action: NextAction
    refreshed: SearchResponse | None


class FeedbackEventRecord(ApiModel):
    event_id: str
    query_id: str
    event_type: FeedbackType
    track_id: str | None
    attribute: str | None
    value: bool | float | str | None
    free_text: str | None
    timestamp: datetime


class SessionTurn(ApiModel):
    query_id: str
    query_text: str
    interpreted_query: InterpretedQuery
    result_track_ids: list[str]
    created_at: datetime
    triggered_by_event_id: str | None
    change_summary: list[str]


class SessionResponse(ApiModel):
    session_id: str
    created_at: datetime
    version: int
    original_query: str | None
    turns: list[SessionTurn]
    feedback: list[FeedbackEventRecord]


# --- Map ----------------------------------------------------------------------------------


class MapPoint(ApiModel):
    track_id: str
    x: float
    y: float
    title: str
    artist: str | None
    genre: str | None
    style: str | None
    source_url: str | None
    has_audio: bool


class MapPointsResponse(ApiModel):
    points: list[MapPoint]
    next_cursor: str | None = Field(description="Pass as `cursor` for the next page.")
    projection_version: str


class MapBounds(ApiModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class MapMetaResponse(ApiModel):
    status: CapabilityStatus
    reason: str | None
    projection_version: str | None
    embedding_version: str | None
    model_id: str | None
    created_at: datetime | None
    bounds: MapBounds | None
    n_points: int
    excluded_tracks: int | None = Field(description="Catalog tracks without audio, not shown.")
    coordinate_transform: dict[str, JsonValue] | None


# --- Health --------------------------------------------------------------------------------


class HealthResponse(ApiModel):
    status: Literal["ok"]
    api_version: str
    capabilities: Capabilities
    semantic_reason: str | None
    map_reason: str | None
