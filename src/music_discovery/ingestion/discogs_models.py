"""Raw Discogs API payloads, validated on arrival.

Only the fields the importer uses are modelled; everything else is ignored. These models are
input-boundary types and never leave `ingestion/`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class DiscogsArtistCredit(_Raw):
    id: int | None = None
    name: str
    anv: str = ""
    join: str = ""
    role: str = ""


class DiscogsLabelRef(_Raw):
    id: int | None = None
    name: str
    catno: str = ""


class DiscogsTrack(_Raw):
    position: str = ""
    type_: str = "track"
    title: str = ""
    duration: str = ""
    artists: list[DiscogsArtistCredit] = []
    extraartists: list[DiscogsArtistCredit] = []
    sub_tracks: list[DiscogsTrack] = []


def _zero_as_none(value: Any) -> Any:
    # Discogs uses 0 for "unknown" in year and master_id fields.
    return None if value in (0, "0", "", None) else value


class DiscogsRelease(_Raw):
    id: int
    title: str
    year: int | None = None
    uri: str | None = None
    master_id: int | None = None
    artists: list[DiscogsArtistCredit] = []
    labels: list[DiscogsLabelRef] = []
    genres: list[str] = []
    styles: list[str] = []
    tracklist: list[DiscogsTrack] = []

    _year = field_validator("year", mode="before")(_zero_as_none)
    _master = field_validator("master_id", mode="before")(_zero_as_none)


class DiscogsMaster(_Raw):
    id: int
    title: str
    year: int | None = None
    uri: str | None = None
    main_release: int | None = None
    artists: list[DiscogsArtistCredit] = []
    genres: list[str] = []
    styles: list[str] = []

    _year = field_validator("year", mode="before")(_zero_as_none)


class DiscogsAlias(_Raw):
    id: int
    name: str


class DiscogsArtist(_Raw):
    id: int
    name: str
    realname: str | None = None
    uri: str | None = None
    namevariations: list[str] = []
    aliases: list[DiscogsAlias] = []


class DiscogsReleaseSummary(_Raw):
    """Entry of `/artists/{id}/releases` or `/labels/{id}/releases`."""

    id: int
    title: str
    type: str = "release"
    """`release` or `master`."""
    year: int | None = None
    main_release: int | None = None

    _year = field_validator("year", mode="before")(_zero_as_none)


class DiscogsSearchHit(_Raw):
    id: int
    type: str
    title: str
    master_id: int | None = None
    uri: str | None = None

    _master = field_validator("master_id", mode="before")(_zero_as_none)


class DiscogsPagination(_Raw):
    page: int = Field(ge=1)
    pages: int = Field(ge=0)
    per_page: int = Field(ge=1)
    items: int = Field(ge=0)
