"""Catalog entities (base.md §5.1, §5.2).

A `Track` is a searchable recording or track-listing entry. It is not the same thing as a
physical Discogs release: one release has many tracks, and different releases can contain
versions of the same recording (linked through `master_release_id`, not merged).

Optional facts are `None` when unknown. They are never replaced by zero, empty strings, or False.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, JsonValue, model_validator

from music_discovery.domain.base import (
    AwareDatetime,
    FrozenModel,
    NonEmptyStr,
    UnitInterval,
    WebUrl,
)
from music_discovery.domain.enums import (
    DataSource,
    EvidenceStatus,
    MatchStatus,
    RelationshipType,
)
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.schemas import FeedbackEvent, SearchSpecification

Year = Annotated[int, Field(ge=1800, le=2100)]
Seconds = Annotated[float, Field(ge=0.0)]


class Provenance(FrozenModel):
    """Where a record came from and, when it was inferred, how confident we are."""

    source: DataSource
    imported_at: AwareDatetime | None = None
    method: str | None = None
    confidence: UnitInterval | None = None


class CatalogEntity(FrozenModel):
    """Shared shape of catalog records: a stable internal id plus external identifiers."""

    id: NonEmptyStr
    external_ids: list[ExternalId] = []
    provenance: Provenance


class ArtistReference(FrozenModel):
    artist_id: NonEmptyStr
    name: NonEmptyStr
    role: str | None = None
    join: str | None = None
    """Discogs join phrase to the next artist (e.g. "&", "feat."), kept for display."""


class LabelReference(FrozenModel):
    label_id: NonEmptyStr
    name: NonEmptyStr
    catalog_number: str | None = None


class Artist(CatalogEntity):
    name: NonEmptyStr
    aliases: list[NonEmptyStr] = []


class Label(CatalogEntity):
    name: NonEmptyStr


class TracklistEntry(FrozenModel):
    """One entry of a release's track listing, preserved as structured data."""

    position: str | None = None
    title: NonEmptyStr
    duration_seconds: Seconds | None = None
    artists: list[ArtistReference] = []
    track_id: str | None = None
    """Internal id of the `Track` created for this entry, once imported."""


class Release(CatalogEntity):
    title: NonEmptyStr
    year: Year | None = None
    genres: list[NonEmptyStr] = []
    styles: list[NonEmptyStr] = []
    artists: list[ArtistReference] = []
    labels: list[LabelReference] = []
    track_listing: list[TracklistEntry] = []
    master_release_id: str | None = None
    discogs_url: WebUrl | None = None


class Track(CatalogEntity):
    """Searchable track. Genres and styles are tags from `provenance.source`, not audio facts."""

    title: NonEmptyStr
    artists: list[ArtistReference] = []
    release_id: str | None = None
    master_release_id: str | None = None
    year: Year | None = None
    genres: list[NonEmptyStr] = []
    styles: list[NonEmptyStr] = []
    labels: list[LabelReference] = []
    duration_seconds: Seconds | None = None
    discogs_url: WebUrl | None = None
    audio_source: DataSource | None = None
    audio_path: str | None = None
    preview_url: WebUrl | None = None
    metadata_confidence: UnitInterval | None = None
    audio_embedding_id: str | None = None
    spatial_x: float | None = None
    spatial_y: float | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if (self.spatial_x is None) != (self.spatial_y is None):
            raise ValueError("spatial_x and spatial_y must both be set or both be None")
        if self.audio_path is not None and self.audio_source is None:
            raise ValueError("audio_path requires audio_source")
        return self

    @property
    def audio_available(self) -> bool:
        """True only when the audio has been analyzed (an embedding exists)."""
        return self.audio_embedding_id is not None

    @property
    def evidence_status(self) -> EvidenceStatus:
        if self.audio_available:
            return EvidenceStatus.AUDIO_AND_METADATA
        return EvidenceStatus.METADATA_ONLY


class TrackAudio(FrozenModel):
    """A locally available, legally usable audio file for a track."""

    track_id: NonEmptyStr
    source: DataSource
    file_path: NonEmptyStr
    """Relative to DATA_DIR. Never a hard-coded absolute path."""
    duration_seconds: Seconds | None = None
    sample_rate: Annotated[int, Field(gt=0)] | None = None
    license: str | None = None
    embedding_model: str | None = None
    embedding_version: str | None = None
    embedding_path: str | None = None

    @model_validator(mode="after")
    def _embedding_fields_together(self) -> Self:
        fields = (self.embedding_model, self.embedding_version)
        if any(f is None for f in fields) and any(f is not None for f in fields):
            raise ValueError("embedding_model and embedding_version must be set together")
        if self.embedding_path is not None and self.embedding_version is None:
            raise ValueError("embedding_path requires embedding_version")
        return self

    @property
    def has_embedding(self) -> bool:
        return self.embedding_version is not None


class TrackRelationship(FrozenModel):
    """Catalog context between two tracks. Not evidence of audio similarity."""

    source_track_id: NonEmptyStr
    target_track_id: NonEmptyStr
    relationship_type: RelationshipType
    evidence_source: DataSource
    weight: UnitInterval | None = None

    @model_validator(mode="after")
    def _distinct_tracks(self) -> Self:
        if self.source_track_id == self.target_track_id:
            raise ValueError("a relationship needs two different tracks")
        return self


class CrossSourceMatch(FrozenModel):
    """A decision about whether a local track corresponds to a record in another source.

    Ambiguous decisions stay `UNRESOLVED` with their candidates; they are never forced.
    """

    track_id: NonEmptyStr
    target: ExternalId
    target_position: str | None = None
    status: MatchStatus
    method: NonEmptyStr
    confidence: UnitInterval | None = None
    signals: dict[str, JsonValue] = {}
    candidates: list[ExternalId] = []
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _accepted_needs_confidence(self) -> Self:
        if self.status is MatchStatus.ACCEPTED and self.confidence is None:
            raise ValueError("an accepted match must record its confidence")
        return self


class SearchTurnRecord(FrozenModel):
    """One query or refinement within a session, with the spec it ran and what it showed."""

    query_id: NonEmptyStr
    query_text: NonEmptyStr
    spec: SearchSpecification
    result_track_ids: list[NonEmptyStr] = []
    created_at: AwareDatetime
    triggered_by_event_id: str | None = None
    change_summary: list[NonEmptyStr] = []


class SearchSession(FrozenModel):
    """Multi-turn search state. The only versioned aggregate; updates return a new version."""

    session_id: NonEmptyStr
    created_at: AwareDatetime
    version: Annotated[int, Field(ge=0)] = 0
    turns: list[SearchTurnRecord] = []
    feedback_history: list[FeedbackEvent] = []

    @property
    def current_spec(self) -> SearchSpecification | None:
        return self.turns[-1].spec if self.turns else None

    @property
    def spec_history(self) -> list[SearchSpecification]:
        return [turn.spec for turn in self.turns]

    @property
    def original_query(self) -> str | None:
        return self.turns[0].spec.original_query if self.turns else None

    def turn(self, query_id: str) -> SearchTurnRecord | None:
        return next((t for t in self.turns if t.query_id == query_id), None)

    def with_turn(self, turn: SearchTurnRecord) -> SearchSession:
        if self.turn(turn.query_id) is not None:
            raise ValueError(f"query {turn.query_id} is already in the session")
        return self.model_copy(update={"turns": [*self.turns, turn], "version": self.version + 1})

    def with_feedback(self, event: FeedbackEvent) -> SearchSession:
        if event.search_session_id != self.session_id:
            raise ValueError("feedback belongs to a different session")
        return self.model_copy(
            update={
                "feedback_history": [*self.feedback_history, event],
                "version": self.version + 1,
            }
        )
