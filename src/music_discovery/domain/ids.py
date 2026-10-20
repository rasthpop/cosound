"""Stable internal identifiers and external identifier references.

Catalog ids are deterministic (uuid5 of the source key) so re-imports are idempotent.
Session/query/event ids are random and come from an `IdGenerator`.
"""

from __future__ import annotations

import re
import uuid
from enum import StrEnum

from music_discovery.domain.base import FrozenModel, NonEmptyStr
from music_discovery.domain.enums import DataSource, ExternalIdKind

# Fixed namespace for this project. Changing it would change every catalog id.
ID_NAMESPACE = uuid.UUID("6f1d3c52-8a4e-5b7e-9c2d-1e0f4a6b8c3d")


class IdPrefix(StrEnum):
    TRACK = "trk"
    ARTIST = "art"
    RELEASE = "rel"
    MASTER = "mst"
    LABEL = "lbl"
    SESSION = "ses"
    QUERY = "qry"
    EVENT = "evt"


_ID_PATTERN = re.compile(r"^(?P<prefix>[a-z]{3})_(?P<body>[0-9a-z]+)$")


class ExternalId(FrozenModel):
    """An identifier in an external source, kept separate from internal ids."""

    source: DataSource
    kind: ExternalIdKind
    value: NonEmptyStr

    @property
    def key(self) -> str:
        return f"{self.source}:{self.kind}:{self.value}"


def stable_id(prefix: IdPrefix, external: ExternalId) -> str:
    """Deterministic internal id for an entity identified by an external source key."""
    return f"{prefix}_{uuid.uuid5(ID_NAMESPACE, external.key).hex}"


def random_id(prefix: IdPrefix) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def id_prefix(value: str) -> IdPrefix | None:
    """Return the prefix of a well-formed internal id, or None."""
    match = _ID_PATTERN.match(value)
    if match is None:
        return None
    try:
        return IdPrefix(match["prefix"])
    except ValueError:
        return None


def is_valid_id(value: str, prefix: IdPrefix) -> bool:
    return id_prefix(value) is prefix
