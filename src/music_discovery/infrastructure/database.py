"""SQLite schema and connection handling (SQLAlchemy Core).

Storage choices:
- Scalar fields are real columns, so they can be filtered and indexed.
- Lists and nested values (genres, styles, artist/label references, track listings, provenance,
  match signals) are JSON columns, so models round-trip without loss.
- `track_artists` / `track_labels` index tracks by artist and label, and `external_ids` maps
  source identifiers to internal ids for every entity type.
- Foreign keys are not declared: imports may write tracks before their artists or labels, and
  repositories behave the same as the in-memory fakes.
- Timestamps are stored as ISO-8601 strings so the timezone offset is preserved.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import (
    JSON,
    Column,
    Connection,
    Engine,
    Float,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.pool import StaticPool

SCHEMA_VERSION = 2
"""2: tracks.source_url, tracks.tags (ADR-0005). No migrations: delete a local v1 database."""

metadata = MetaData()

schema_version = Table(
    "schema_version",
    metadata,
    Column("version", Integer, nullable=False),
)

tracks = Table(
    "tracks",
    metadata,
    Column("id", String, primary_key=True),
    Column("title", Text, nullable=False),
    Column("artists", JSON, nullable=False),
    Column("release_id", String),
    Column("master_release_id", String),
    Column("year", Integer),
    Column("genres", JSON, nullable=False),
    Column("styles", JSON, nullable=False),
    Column("tags", JSON, nullable=False),
    Column("labels", JSON, nullable=False),
    Column("duration_seconds", Float),
    Column("discogs_url", Text),
    Column("source_url", Text),
    Column("audio_source", String),
    Column("audio_path", Text),
    Column("preview_url", Text),
    Column("metadata_confidence", Float),
    Column("audio_embedding_id", String),
    Column("spatial_x", Float),
    Column("spatial_y", Float),
    Column("provenance", JSON, nullable=False),
    Index("ix_tracks_release_id", "release_id"),
    Index("ix_tracks_master_release_id", "master_release_id"),
)

artists = Table(
    "artists",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("aliases", JSON, nullable=False),
    Column("provenance", JSON, nullable=False),
)

labels = Table(
    "labels",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("provenance", JSON, nullable=False),
)

releases = Table(
    "releases",
    metadata,
    Column("id", String, primary_key=True),
    Column("title", Text, nullable=False),
    Column("year", Integer),
    Column("genres", JSON, nullable=False),
    Column("styles", JSON, nullable=False),
    Column("artists", JSON, nullable=False),
    Column("labels", JSON, nullable=False),
    Column("track_listing", JSON, nullable=False),
    Column("master_release_id", String),
    Column("discogs_url", Text),
    Column("provenance", JSON, nullable=False),
)

track_artists = Table(
    "track_artists",
    metadata,
    Column("track_id", String, nullable=False),
    Column("position", Integer, nullable=False),
    Column("artist_id", String, nullable=False),
    PrimaryKeyConstraint("track_id", "position"),
    Index("ix_track_artists_artist_id", "artist_id"),
)

track_labels = Table(
    "track_labels",
    metadata,
    Column("track_id", String, nullable=False),
    Column("position", Integer, nullable=False),
    Column("label_id", String, nullable=False),
    PrimaryKeyConstraint("track_id", "position"),
    Index("ix_track_labels_label_id", "label_id"),
)

external_ids = Table(
    "external_ids",
    metadata,
    Column("entity_type", String, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("position", Integer, nullable=False),
    Column("source", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("value", String, nullable=False),
    PrimaryKeyConstraint("entity_type", "entity_id", "position"),
    Index("ix_external_ids_lookup", "entity_type", "source", "kind", "value"),
)

track_audio = Table(
    "track_audio",
    metadata,
    Column("track_id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("file_path", Text, nullable=False),
    Column("duration_seconds", Float),
    Column("sample_rate", Integer),
    Column("license", Text),
    Column("embedding_model", String),
    Column("embedding_version", String),
    Column("embedding_path", Text),
)

relationships = Table(
    "relationships",
    metadata,
    Column("source_track_id", String, nullable=False),
    Column("target_track_id", String, nullable=False),
    Column("relationship_type", String, nullable=False),
    Column("evidence_source", String, nullable=False),
    Column("weight", Float),
    PrimaryKeyConstraint("source_track_id", "target_track_id", "relationship_type"),
)

cross_source_matches = Table(
    "cross_source_matches",
    metadata,
    Column("track_id", String, nullable=False),
    Column("target_key", String, nullable=False),
    Column("target", JSON, nullable=False),
    Column("target_position", String),
    Column("status", String, nullable=False),
    Column("method", String, nullable=False),
    Column("confidence", Float),
    Column("signals", JSON, nullable=False),
    Column("candidates", JSON, nullable=False),
    Column("decided_at", String, nullable=False),
    PrimaryKeyConstraint("track_id", "target_key"),
    Index("ix_cross_source_matches_status", "status"),
)

# Written by the bounded Discogs importer (P02.T04); no repository yet.
import_runs = Table(
    "import_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("selection_hash", String),
    Column("started_at", String, nullable=False),
    Column("finished_at", String),
    Column("counts", JSON, nullable=False),
    Column("errors", JSON, nullable=False),
)

# Search sessions (P06.T07). Added without a schema-version bump: `create_all` adds them to an
# existing v2 database, and nothing else changed.
search_sessions = Table(
    "search_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("feedback_history", JSON, nullable=False),
)

search_turns = Table(
    "search_turns",
    metadata,
    Column("session_id", String, nullable=False),
    Column("position", Integer, nullable=False),
    Column("query_id", String, nullable=False),
    Column("query_text", Text, nullable=False),
    Column("spec", JSON, nullable=False),
    Column("result_track_ids", JSON, nullable=False),
    Column("created_at", String, nullable=False),
    Column("triggered_by_event_id", String),
    Column("change_summary", JSON, nullable=False),
    PrimaryKeyConstraint("session_id", "position"),
    Index("ux_search_turns_query", "session_id", "query_id", unique=True),
)

feedback_events = Table(
    "feedback_events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("search_session_id", String, nullable=False),
    Column("query_id", String, nullable=False),
    Column("track_id", String),
    Column("event_type", String, nullable=False),
    Column("attribute", String),
    Column("value", JSON),
    Column("free_text", Text),
    Column("timestamp", String, nullable=False),
    Index("ix_feedback_events_session", "search_session_id"),
)


class SchemaVersionError(RuntimeError):
    """The database was created by a different schema version."""


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite") and (
        url.endswith(":memory:") or url in ("sqlite://", "sqlite:///")
    ):
        # One shared connection, otherwise each connection sees its own empty database.
        return create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    return create_engine(url)


class Database:
    """Engine plus a unit of work: writes inside `transaction()` commit or roll back together."""

    def __init__(self, url: str) -> None:
        self.engine = _make_engine(url)
        self._current: ContextVar[Connection | None] = ContextVar(
            f"db_connection_{id(self)}", default=None
        )

    def init_schema(self) -> None:
        """Create missing tables and record the schema version. Safe to call repeatedly."""
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            stored = conn.execute(select(schema_version.c.version)).scalars().all()
            if not stored:
                conn.execute(schema_version.insert().values(version=SCHEMA_VERSION))
            elif stored != [SCHEMA_VERSION]:
                raise SchemaVersionError(
                    f"database schema version {stored} does not match {SCHEMA_VERSION}"
                )

    def schema_version(self) -> int | None:
        with self.connect() as conn:
            return conn.execute(select(func.max(schema_version.c.version))).scalar()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Join the current transaction, or start one that commits on success."""
        if self._current.get() is not None:
            yield
            return
        with self.engine.begin() as conn:
            token = self._current.set(conn)
            try:
                yield
            finally:
                self._current.reset(token)

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Connection for one repository call: the open transaction's, or a short-lived one."""
        current = self._current.get()
        if current is not None:
            yield current
            return
        with self.engine.begin() as conn:
            yield conn

    def dispose(self) -> None:
        self.engine.dispose()
