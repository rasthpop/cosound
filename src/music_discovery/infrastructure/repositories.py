"""SQLite implementations of the catalog, session and feedback repository protocols."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Connection, Table, delete, func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from music_discovery.domain.enums import DataSource, MatchStatus, RelationshipType
from music_discovery.domain.errors import StaleSessionVersion
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import (
    Artist,
    CatalogEntity,
    CrossSourceMatch,
    ImportRun,
    Label,
    Release,
    SearchSession,
    SearchTurnRecord,
    Track,
    TrackAudio,
    TrackRelationship,
)
from music_discovery.domain.schemas import FeedbackEvent
from music_discovery.infrastructure import database as db
from music_discovery.infrastructure.database import Database

E = TypeVar("E", bound=CatalogEntity)


def _upsert(conn: Connection, table: Table, row: Mapping[str, Any]) -> None:
    keys = [c.name for c in table.primary_key.columns]
    stmt = sqlite_insert(table).values(**row)
    updates = {name: stmt.excluded[name] for name in row if name not in keys}
    conn.execute(stmt.on_conflict_do_update(index_elements=keys, set_=updates))


def _row(model: BaseModel, *, exclude: set[str] | None = None) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude=exclude)


class _EntityRepository(Generic[E]):
    """Shared logic for entities with an `id` and `external_ids`."""

    model: type[E]
    table: Table
    entity_type: str

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, entity_id: str) -> E | None:
        with self._db.connect() as conn:
            found = self._load(conn, [entity_id])
        return found.get(entity_id)

    def find_by_external_id(self, external_id: ExternalId) -> E | None:
        query = (
            select(db.external_ids.c.entity_id)
            .where(
                db.external_ids.c.entity_type == self.entity_type,
                db.external_ids.c.source == str(external_id.source),
                db.external_ids.c.kind == str(external_id.kind),
                db.external_ids.c.value == external_id.value,
            )
            .order_by(db.external_ids.c.entity_id)
            .limit(1)
        )
        with self._db.connect() as conn:
            entity_id = conn.execute(query).scalar()
            if entity_id is None:
                return None
            return self._load(conn, [entity_id]).get(entity_id)

    def upsert(self, entity: E) -> None:
        with self._db.connect() as conn:
            _upsert(conn, self.table, _row(entity, exclude={"external_ids"}))
            self._replace_external_ids(conn, entity.id, entity.external_ids)
            self._after_upsert(conn, entity)

    def _after_upsert(self, conn: Connection, entity: E) -> None:
        """Hook for maintaining secondary index tables."""

    def _replace_external_ids(
        self, conn: Connection, entity_id: str, ids: Sequence[ExternalId]
    ) -> None:
        table = db.external_ids
        conn.execute(
            delete(table).where(
                table.c.entity_type == self.entity_type, table.c.entity_id == entity_id
            )
        )
        if ids:
            conn.execute(
                insert(table),
                [
                    {
                        "entity_type": self.entity_type,
                        "entity_id": entity_id,
                        "position": i,
                        "source": str(ext.source),
                        "kind": str(ext.kind),
                        "value": ext.value,
                    }
                    for i, ext in enumerate(ids)
                ],
            )

    def _load(self, conn: Connection, entity_ids: Sequence[str]) -> dict[str, E]:
        if not entity_ids:
            return {}
        rows = conn.execute(select(self.table).where(self.table.c.id.in_(entity_ids))).mappings()
        records = {row["id"]: dict(row) for row in rows}
        ext_rows = conn.execute(
            select(db.external_ids)
            .where(
                db.external_ids.c.entity_type == self.entity_type,
                db.external_ids.c.entity_id.in_(list(records)),
            )
            .order_by(db.external_ids.c.entity_id, db.external_ids.c.position)
        ).mappings()
        for record in records.values():
            record["external_ids"] = []
        for ext in ext_rows:
            records[ext["entity_id"]]["external_ids"].append(
                {"source": ext["source"], "kind": ext["kind"], "value": ext["value"]}
            )
        return {key: self.model.model_validate(value) for key, value in records.items()}


class SqlTrackRepository(_EntityRepository[Track]):
    model = Track
    table = db.tracks
    entity_type = "track"

    def get_many(self, track_ids: Sequence[str]) -> list[Track]:
        with self._db.connect() as conn:
            found = self._load(conn, list(dict.fromkeys(track_ids)))
        return [found[i] for i in track_ids if i in found]

    def list_page(self, *, limit: int, after: str | None = None) -> list[Track]:
        query = select(db.tracks.c.id).order_by(db.tracks.c.id).limit(limit)
        if after is not None:
            query = query.where(db.tracks.c.id > after)
        with self._db.connect() as conn:
            ids = list(conn.execute(query).scalars())
            found = self._load(conn, ids)
        return [found[i] for i in ids]

    def count(self) -> int:
        with self._db.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(db.tracks)).scalar_one())

    def _after_upsert(self, conn: Connection, entity: Track) -> None:
        for table, refs, key in (
            (db.track_artists, [a.artist_id for a in entity.artists], "artist_id"),
            (db.track_labels, [lbl.label_id for lbl in entity.labels], "label_id"),
        ):
            conn.execute(delete(table).where(table.c.track_id == entity.id))
            if refs:
                conn.execute(
                    insert(table),
                    [
                        {"track_id": entity.id, "position": i, key: ref}
                        for i, ref in enumerate(refs)
                    ],
                )


class SqlReleaseRepository(_EntityRepository[Release]):
    model = Release
    table = db.releases
    entity_type = "release"


class SqlArtistRepository(_EntityRepository[Artist]):
    model = Artist
    table = db.artists
    entity_type = "artist"


class SqlLabelRepository(_EntityRepository[Label]):
    model = Label
    table = db.labels
    entity_type = "label"


class SqlTrackAudioRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, track_id: str) -> TrackAudio | None:
        query = select(db.track_audio).where(db.track_audio.c.track_id == track_id)
        with self._db.connect() as conn:
            row = conn.execute(query).mappings().first()
        return None if row is None else TrackAudio.model_validate(dict(row))

    def upsert(self, audio: TrackAudio) -> None:
        with self._db.connect() as conn:
            _upsert(conn, db.track_audio, _row(audio))

    def list_all(self) -> list[TrackAudio]:
        query = select(db.track_audio).order_by(db.track_audio.c.track_id)
        with self._db.connect() as conn:
            return [TrackAudio.model_validate(dict(r)) for r in conn.execute(query).mappings()]


class SqlRelationshipRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def upsert(self, relationship: TrackRelationship) -> None:
        with self._db.connect() as conn:
            _upsert(conn, db.relationships, _row(relationship))

    def for_track(
        self, track_id: str, types: Collection[RelationshipType] | None = None
    ) -> list[TrackRelationship]:
        table = db.relationships
        query = (
            select(table)
            .where(table.c.source_track_id == track_id)
            .order_by(table.c.relationship_type, table.c.target_track_id)
        )
        if types is not None:
            query = query.where(table.c.relationship_type.in_([str(t) for t in types]))
        with self._db.connect() as conn:
            return [
                TrackRelationship.model_validate(dict(r)) for r in conn.execute(query).mappings()
            ]

    def replace_all(self, relationships: Sequence[TrackRelationship]) -> None:
        with self._db.connect() as conn:
            conn.execute(delete(db.relationships))
            if relationships:
                conn.execute(insert(db.relationships), [_row(r) for r in relationships])


class SqlMatchRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def upsert(self, match: CrossSourceMatch) -> None:
        row = _row(match)
        row["target_key"] = match.target.key
        with self._db.connect() as conn:
            _upsert(conn, db.cross_source_matches, row)

    def for_track(self, track_id: str) -> list[CrossSourceMatch]:
        table = db.cross_source_matches
        return self._query(
            select(table).where(table.c.track_id == track_id).order_by(table.c.target_key)
        )

    def list_by_status(self, status: MatchStatus) -> list[CrossSourceMatch]:
        table = db.cross_source_matches
        return self._query(
            select(table)
            .where(table.c.status == str(status))
            .order_by(table.c.track_id, table.c.target_key)
        )

    def _query(self, query: Any) -> list[CrossSourceMatch]:
        with self._db.connect() as conn:
            rows = [dict(r) for r in conn.execute(query).mappings()]
        for row in rows:
            row.pop("target_key")
        return [CrossSourceMatch.model_validate(r) for r in rows]


class SqlImportRunRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def save(self, run: ImportRun) -> None:
        with self._db.connect() as conn:
            _upsert(conn, db.import_runs, _row(run))

    def get(self, run_id: str) -> ImportRun | None:
        query = select(db.import_runs).where(db.import_runs.c.id == run_id)
        with self._db.connect() as conn:
            row = conn.execute(query).mappings().first()
        return None if row is None else ImportRun.model_validate(dict(row))

    def latest(self, source: DataSource) -> ImportRun | None:
        table = db.import_runs
        query = (
            select(table)
            .where(table.c.source == str(source))
            .order_by(table.c.started_at.desc(), table.c.id.desc())
            .limit(1)
        )
        with self._db.connect() as conn:
            row = conn.execute(query).mappings().first()
        return None if row is None else ImportRun.model_validate(dict(row))


class SqlSessionRepository:
    """Sessions with their turns. `save` is a compare-and-set on the stored version."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, session_id: str) -> SearchSession | None:
        sessions, turns = db.search_sessions, db.search_turns
        with self._db.connect() as conn:
            row = conn.execute(select(sessions).where(sessions.c.id == session_id)).mappings()
            found = row.first()
            if found is None:
                return None
            turn_rows = conn.execute(
                select(turns).where(turns.c.session_id == session_id).order_by(turns.c.position)
            ).mappings()
            records = [
                SearchTurnRecord.model_validate(
                    {k: v for k, v in r.items() if k not in ("session_id", "position")}
                )
                for r in turn_rows
            ]
        return SearchSession.model_validate(
            {
                "session_id": found["id"],
                "created_at": found["created_at"],
                "version": found["version"],
                "turns": records,
                "feedback_history": found["feedback_history"],
            }
        )

    def save(self, session: SearchSession, *, expected_version: int | None) -> None:
        sessions = db.search_sessions
        data = _row(session)
        row = {
            "id": session.session_id,
            "created_at": data["created_at"],
            "version": session.version,
            "feedback_history": data["feedback_history"],
        }
        with self._db.transaction(), self._db.connect() as conn:
            if expected_version is None:
                exists = conn.execute(
                    select(sessions.c.version).where(sessions.c.id == session.session_id)
                ).first()
                if exists is not None:
                    raise _stale(session.session_id, exists[0], expected_version)
                conn.execute(insert(sessions).values(**row))
            else:
                updated = conn.execute(
                    update(sessions)
                    .where(sessions.c.id == session.session_id)
                    .where(sessions.c.version == expected_version)
                    .values(**row)
                )
                if updated.rowcount != 1:
                    stored = conn.execute(
                        select(sessions.c.version).where(sessions.c.id == session.session_id)
                    ).scalar()
                    raise _stale(session.session_id, stored, expected_version)
            self._replace_turns(conn, session.session_id, data["turns"])

    def _replace_turns(
        self, conn: Connection, session_id: str, turns: Sequence[Mapping[str, Any]]
    ) -> None:
        table = db.search_turns
        conn.execute(delete(table).where(table.c.session_id == session_id))
        if turns:
            conn.execute(
                insert(table),
                [{**t, "session_id": session_id, "position": i} for i, t in enumerate(turns)],
            )


def _stale(session_id: str, stored: int | None, expected: int | None) -> StaleSessionVersion:
    return StaleSessionVersion(
        f"session {session_id} is at version {stored}, expected {expected}",
        details={"session_id": session_id},
    )


class SqlFeedbackRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def add(self, event: FeedbackEvent) -> None:
        with self._db.connect() as conn:
            _upsert(conn, db.feedback_events, _row(event))

    def for_session(self, session_id: str) -> list[FeedbackEvent]:
        table = db.feedback_events
        query = (
            select(table)
            .where(table.c.search_session_id == session_id)
            .order_by(table.c.timestamp, table.c.event_id)
        )
        with self._db.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [FeedbackEvent.model_validate(dict(r)) for r in rows]
