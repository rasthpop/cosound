"""In-memory repositories implementing the domain repository protocols."""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from typing import Generic, Protocol, TypeVar

from music_discovery.domain.enums import MatchStatus, RelationshipType
from music_discovery.domain.errors import StaleSessionVersion
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import (
    Artist,
    CatalogEntity,
    CrossSourceMatch,
    Label,
    Release,
    SearchSession,
    Track,
    TrackAudio,
    TrackRelationship,
)
from music_discovery.domain.schemas import FeedbackEvent

K = TypeVar("K")
V = TypeVar("V")


class Snapshottable(Protocol):
    def _snapshot(self) -> object: ...
    def _restore(self, state: object) -> None: ...


class _Store(Generic[K, V]):
    def __init__(self) -> None:
        self._items: dict[K, V] = {}

    def _snapshot(self) -> object:
        return dict(self._items)

    def _restore(self, state: object) -> None:
        assert isinstance(state, dict)
        self._items = state


E = TypeVar("E", bound=CatalogEntity)


class _EntityStore(_Store[str, E]):
    def get(self, entity_id: str) -> E | None:
        return self._items.get(entity_id)

    def find_by_external_id(self, external_id: ExternalId) -> E | None:
        for entity in self._items.values():
            if external_id in entity.external_ids:
                return entity
        return None

    def upsert(self, entity: E) -> None:
        self._items[entity.id] = entity


class InMemoryTrackRepository(_EntityStore[Track]):
    def get_many(self, track_ids: Sequence[str]) -> list[Track]:
        return [self._items[i] for i in track_ids if i in self._items]

    def list_page(self, *, limit: int, after: str | None = None) -> list[Track]:
        ids = sorted(i for i in self._items if after is None or i > after)
        return [self._items[i] for i in ids[:limit]]

    def count(self) -> int:
        return len(self._items)


class InMemoryReleaseRepository(_EntityStore[Release]):
    pass


class InMemoryArtistRepository(_EntityStore[Artist]):
    pass


class InMemoryLabelRepository(_EntityStore[Label]):
    pass


class InMemoryTrackAudioRepository(_Store[str, TrackAudio]):
    def get(self, track_id: str) -> TrackAudio | None:
        return self._items.get(track_id)

    def upsert(self, audio: TrackAudio) -> None:
        self._items[audio.track_id] = audio

    def list_all(self) -> list[TrackAudio]:
        return [self._items[k] for k in sorted(self._items)]


class InMemoryRelationshipRepository(_Store[tuple[str, str, str], TrackRelationship]):
    def upsert(self, relationship: TrackRelationship) -> None:
        key = (
            relationship.source_track_id,
            relationship.target_track_id,
            str(relationship.relationship_type),
        )
        self._items[key] = relationship

    def for_track(
        self, track_id: str, types: Collection[RelationshipType] | None = None
    ) -> list[TrackRelationship]:
        found = [
            r
            for r in self._items.values()
            if r.source_track_id == track_id and (types is None or r.relationship_type in types)
        ]
        return sorted(found, key=lambda r: (str(r.relationship_type), r.target_track_id))


class InMemoryMatchRepository(_Store[tuple[str, str], CrossSourceMatch]):
    def upsert(self, match: CrossSourceMatch) -> None:
        self._items[(match.track_id, match.target.key)] = match

    def for_track(self, track_id: str) -> list[CrossSourceMatch]:
        return [m for (t, _), m in sorted(self._items.items()) if t == track_id]

    def list_by_status(self, status: MatchStatus) -> list[CrossSourceMatch]:
        return [m for _, m in sorted(self._items.items()) if m.status is status]


class InMemorySessionRepository(_Store[str, SearchSession]):
    def get(self, session_id: str) -> SearchSession | None:
        return self._items.get(session_id)

    def save(self, session: SearchSession, *, expected_version: int | None) -> None:
        stored = self._items.get(session.session_id)
        stored_version = None if stored is None else stored.version
        if stored_version != expected_version:
            raise StaleSessionVersion(
                f"session {session.session_id} is at version {stored_version}, "
                f"expected {expected_version}",
                details={"session_id": session.session_id},
            )
        self._items[session.session_id] = session


class InMemoryFeedbackRepository(_Store[str, FeedbackEvent]):
    def add(self, event: FeedbackEvent) -> None:
        self._items[event.event_id] = event

    def for_session(self, session_id: str) -> list[FeedbackEvent]:
        events = [e for e in self._items.values() if e.search_session_id == session_id]
        return sorted(events, key=lambda e: (e.timestamp, e.event_id))


class InMemoryUnitOfWork:
    """Restores every registered store if the transaction body raises."""

    def __init__(self, *stores: Snapshottable) -> None:
        self._stores = stores

    @contextmanager
    def transaction(self) -> Iterator[None]:
        snapshots = [store._snapshot() for store in self._stores]
        try:
            yield
        except BaseException:
            for store, snapshot in zip(self._stores, snapshots, strict=True):
                store._restore(snapshot)
            raise
