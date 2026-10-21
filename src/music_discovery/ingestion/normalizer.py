"""Raw Discogs payloads -> domain entities (base.md §10.2).

Track listings, artist credits and master links are preserved as structured data. Genres and
styles are kept as source-attributed tags; nothing about sound is inferred from them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.domain.ids import ExternalId, IdPrefix, stable_id
from music_discovery.domain.models import (
    Artist,
    ArtistReference,
    Label,
    LabelReference,
    Provenance,
    Release,
    Track,
    TracklistEntry,
)
from music_discovery.ingestion.discogs_models import (
    DiscogsArtist,
    DiscogsArtistCredit,
    DiscogsLabelRef,
    DiscogsRelease,
    DiscogsTrack,
)
from music_discovery.ingestion.names import matching_key, strip_disambiguator

_DURATION = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")
MIN_YEAR, MAX_YEAR = 1800, 2100


def parse_duration(value: str | None) -> float | None:
    """'4:35' -> 275.0, '1:02:03' -> 3723.0; empty or malformed -> None (unknown, not zero)."""
    if not value:
        return None
    match = _DURATION.match(value.strip())
    if match is None:
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    if seconds >= 60:
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def discogs_ext(kind: ExternalIdKind, value: int | str) -> ExternalId:
    return ExternalId(source=DataSource.DISCOGS, kind=kind, value=str(value))


def artist_id_for(credit: DiscogsArtistCredit) -> str:
    """Internal artist id. Credits without a Discogs id (e.g. id 0) are keyed by name."""
    if credit.id:
        return stable_id(IdPrefix.ARTIST, discogs_ext(ExternalIdKind.ARTIST, credit.id))
    key = f"name:{matching_key(credit.name)}"
    return stable_id(IdPrefix.ARTIST, discogs_ext(ExternalIdKind.ARTIST, key))


def label_id_for(label: DiscogsLabelRef) -> str:
    if label.id:
        return stable_id(IdPrefix.LABEL, discogs_ext(ExternalIdKind.LABEL, label.id))
    key = f"name:{matching_key(label.name)}"
    return stable_id(IdPrefix.LABEL, discogs_ext(ExternalIdKind.LABEL, key))


def release_id_for(release_id: int) -> str:
    return stable_id(IdPrefix.RELEASE, discogs_ext(ExternalIdKind.RELEASE, release_id))


def master_id_for(master_id: int) -> str:
    return stable_id(IdPrefix.MASTER, discogs_ext(ExternalIdKind.MASTER, master_id))


def track_id_for(release_id: int, position_key: str) -> str:
    return stable_id(
        IdPrefix.TRACK, discogs_ext(ExternalIdKind.TRACK, f"{release_id}:{position_key}")
    )


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            out.append(cleaned)
    return out


def _year(value: int | None) -> int | None:
    return value if value is not None and MIN_YEAR <= value <= MAX_YEAR else None


def _url(value: str | None) -> str | None:
    return value if value and value.startswith(("http://", "https://")) else None


def artist_refs(credits: Iterable[DiscogsArtistCredit]) -> list[ArtistReference]:
    return [
        ArtistReference(
            artist_id=artist_id_for(c),
            name=strip_disambiguator(c.name),
            role=c.role.strip() or None,
            join=c.join.strip() or None,
        )
        for c in credits
        if c.name.strip()
    ]


def label_refs(labels: Iterable[DiscogsLabelRef]) -> list[LabelReference]:
    refs: dict[str, LabelReference] = {}
    for label in labels:
        if not label.name.strip():
            continue
        label_id = label_id_for(label)
        refs.setdefault(
            label_id,
            LabelReference(
                label_id=label_id,
                name=label.name.strip(),
                catalog_number=label.catno.strip() or None,
            ),
        )
    return list(refs.values())


def flatten_tracklist(tracklist: Iterable[DiscogsTrack]) -> list[DiscogsTrack]:
    """Drop headings and expand index tracks into their sub-tracks (an empty index is a track)."""
    flat: list[DiscogsTrack] = []
    for entry in tracklist:
        if entry.type_ == "heading" or not entry.title.strip():
            continue
        if entry.type_ == "index" and entry.sub_tracks:
            flat.extend(flatten_tracklist(entry.sub_tracks))
        else:
            flat.append(entry)
    return flat


@dataclass(frozen=True)
class NormalizedRelease:
    release: Release
    tracks: list[Track]
    artists: list[Artist]
    labels: list[Label]


def normalize_release(raw: DiscogsRelease, *, imported_at: datetime) -> NormalizedRelease:
    provenance = Provenance(source=DataSource.DISCOGS, imported_at=imported_at, method="api")
    release_id = release_id_for(raw.id)
    master_id = master_id_for(raw.master_id) if raw.master_id else None
    release_artists = artist_refs(raw.artists)
    labels = label_refs(raw.labels)
    genres = _unique(raw.genres)
    styles = _unique(raw.styles)
    year = _year(raw.year)
    url = _url(raw.uri)

    tracks: list[Track] = []
    entries: list[TracklistEntry] = []
    credits: dict[str, DiscogsArtistCredit] = {}
    for c in raw.artists:
        credits.setdefault(artist_id_for(c), c)

    for ordinal, entry in enumerate(flatten_tracklist(raw.tracklist), start=1):
        position = entry.position.strip() or None
        track_id = track_id_for(raw.id, position or f"#{ordinal}")
        track_artists = artist_refs(entry.artists) or release_artists
        for c in [*entry.artists, *entry.extraartists]:
            credits.setdefault(artist_id_for(c), c)
        duration = parse_duration(entry.duration)
        entries.append(
            TracklistEntry(
                position=position,
                title=entry.title.strip(),
                duration_seconds=duration,
                artists=artist_refs(entry.artists),
                track_id=track_id,
            )
        )
        tracks.append(
            Track(
                id=track_id,
                title=entry.title.strip(),
                artists=track_artists,
                release_id=release_id,
                master_release_id=master_id,
                year=year,
                genres=genres,
                styles=styles,
                labels=labels,
                duration_seconds=duration,
                discogs_url=url,
                external_ids=[
                    discogs_ext(ExternalIdKind.TRACK, f"{raw.id}:{position or f'#{ordinal}'}")
                ],
                provenance=provenance,
            )
        )

    release = Release(
        id=release_id,
        title=raw.title.strip(),
        year=year,
        genres=genres,
        styles=styles,
        artists=release_artists,
        labels=labels,
        track_listing=entries,
        master_release_id=master_id,
        discogs_url=url,
        external_ids=[discogs_ext(ExternalIdKind.RELEASE, raw.id)]
        + ([discogs_ext(ExternalIdKind.MASTER, raw.master_id)] if raw.master_id else []),
        provenance=provenance,
    )
    artists = [
        _artist_from_credit(aid, c, provenance) for aid, c in credits.items() if c.name.strip()
    ]
    label_entities = [
        Label(
            id=ref.label_id,
            name=ref.name,
            external_ids=[discogs_ext(ExternalIdKind.LABEL, lbl.id)] if lbl.id else [],
            provenance=provenance,
        )
        for ref, lbl in _label_pairs(raw.labels, labels)
    ]
    return NormalizedRelease(release=release, tracks=tracks, artists=artists, labels=label_entities)


def _label_pairs(
    raw_labels: Iterable[DiscogsLabelRef], refs: list[LabelReference]
) -> list[tuple[LabelReference, DiscogsLabelRef]]:
    by_id = {label_id_for(lbl): lbl for lbl in reversed(list(raw_labels)) if lbl.name.strip()}
    return [(ref, by_id[ref.label_id]) for ref in refs]


def _artist_from_credit(
    artist_id: str, credit: DiscogsArtistCredit, provenance: Provenance
) -> Artist:
    name = strip_disambiguator(credit.name)
    aliases = _unique(a for a in (credit.anv, credit.name) if a.strip() and a.strip() != name)
    return Artist(
        id=artist_id,
        name=name,
        aliases=aliases,
        external_ids=[discogs_ext(ExternalIdKind.ARTIST, credit.id)] if credit.id else [],
        provenance=provenance,
    )


def normalize_artist(raw: DiscogsArtist, *, imported_at: datetime) -> Artist:
    """Full artist record: name variations and aliases are kept for matching and display."""
    name = strip_disambiguator(raw.name)
    variations = [raw.name, *(raw.namevariations), *(a.name for a in raw.aliases)]
    if raw.realname:
        variations.append(raw.realname)
    return Artist(
        id=stable_id(IdPrefix.ARTIST, discogs_ext(ExternalIdKind.ARTIST, raw.id)),
        name=name,
        aliases=_unique(v for v in variations if v.strip() != name),
        external_ids=[discogs_ext(ExternalIdKind.ARTIST, raw.id)],
        provenance=Provenance(source=DataSource.DISCOGS, imported_at=imported_at, method="api"),
    )
