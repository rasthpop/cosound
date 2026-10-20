from datetime import UTC, datetime
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from music_discovery.domain.enums import (
    DataSource,
    EvidenceStatus,
    ExternalIdKind,
    MatchStatus,
    RelationshipType,
)
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import (
    Artist,
    ArtistReference,
    CrossSourceMatch,
    Label,
    LabelReference,
    Provenance,
    Release,
    Track,
    TrackAudio,
    TracklistEntry,
    TrackRelationship,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
DISCOGS = Provenance(source=DataSource.DISCOGS, imported_at=NOW)
FMA = Provenance(source=DataSource.FMA, imported_at=NOW)


M = TypeVar("M", bound=BaseModel)


def roundtrip(model: M) -> M:
    return type(model).model_validate(model.model_dump(mode="json"))


def make_track(**overrides: object) -> Track:
    values: dict[str, object] = {"id": "trk_1", "title": "Flute Song", "provenance": FMA}
    values.update(overrides)
    return Track.model_validate(values)


def test_minimal_track_keeps_unknowns_as_none() -> None:
    track = make_track()
    assert track.year is None
    assert track.duration_seconds is None
    assert track.preview_url is None
    assert track.metadata_confidence is None
    assert track.audio_available is False
    assert track.evidence_status is EvidenceStatus.METADATA_ONLY
    dumped = track.model_dump(mode="json")
    assert dumped["duration_seconds"] is None
    assert dumped["preview_url"] is None


def test_full_track_roundtrip() -> None:
    track = make_track(
        artists=[ArtistReference(artist_id="art_1", name="A", join="&")],
        release_id="rel_1",
        master_release_id="mst_1",
        year=1999,
        genres=["Electronic"],
        styles=["Ambient"],
        labels=[LabelReference(label_id="lbl_1", name="L", catalog_number="CAT 1")],
        duration_seconds=272.0,
        discogs_url="https://www.discogs.com/release/1",
        audio_source=DataSource.FMA,
        audio_path="raw/fma/fma_small/000/000002.mp3",
        metadata_confidence=0.9,
        audio_embedding_id="emb_1",
        spatial_x=-2.4,
        spatial_y=1.8,
        external_ids=[ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value="2")],
    )
    assert roundtrip(track) == track
    assert track.evidence_status is EvidenceStatus.AUDIO_AND_METADATA


def test_track_is_frozen_and_strict() -> None:
    track = make_track()
    with pytest.raises(ValidationError):
        track.title = "Other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        make_track(unexpected_field=1)
    assert track.model_copy(update={"year": 2001}).year == 2001


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "  "},
        {"year": 1200},
        {"duration_seconds": -1.0},
        {"metadata_confidence": 1.5},
        {"discogs_url": "discogs.com/release/1"},
        {"spatial_x": 1.0},
        {"audio_path": "a.mp3"},
    ],
)
def test_track_rejects_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_track(**overrides)


def test_release_preserves_structured_tracklist() -> None:
    release = Release(
        id="rel_1",
        title="Album",
        year=1999,
        genres=["Jazz"],
        styles=["Cool Jazz"],
        artists=[ArtistReference(artist_id="art_1", name="A")],
        track_listing=[
            TracklistEntry(position="A1", title="One", duration_seconds=180.0),
            TracklistEntry(position="A2", title="Two", duration_seconds=None),
        ],
        master_release_id="mst_1",
        provenance=DISCOGS,
    )
    assert roundtrip(release) == release
    assert release.track_listing[1].duration_seconds is None


def test_artist_and_label_roundtrip() -> None:
    artist = Artist(id="art_1", name="Name", aliases=["Alias"], provenance=DISCOGS)
    label = Label(id="lbl_1", name="Label", provenance=DISCOGS)
    assert roundtrip(artist) == artist
    assert roundtrip(label) == label


def test_track_audio_embedding_fields_go_together() -> None:
    audio = TrackAudio(track_id="trk_1", source=DataSource.FMA, file_path="raw/a.mp3")
    assert audio.has_embedding is False
    with pytest.raises(ValidationError):
        TrackAudio(
            track_id="trk_1", source=DataSource.FMA, file_path="raw/a.mp3", embedding_model="m"
        )
    full = TrackAudio(
        track_id="trk_1",
        source=DataSource.FMA,
        file_path="raw/a.mp3",
        sample_rate=44100,
        license="CC BY 4.0",
        embedding_model="clap-music",
        embedding_version="ev1",
        embedding_path="embeddings/ev1",
    )
    assert full.has_embedding
    assert roundtrip(full) == full


def test_relationship_needs_two_tracks() -> None:
    with pytest.raises(ValidationError):
        TrackRelationship(
            source_track_id="trk_1",
            target_track_id="trk_1",
            relationship_type=RelationshipType.SAME_ARTIST,
            evidence_source=DataSource.DISCOGS,
        )


def test_cross_source_match_rules() -> None:
    target = ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.RELEASE, value="9")
    unresolved = CrossSourceMatch(
        track_id="trk_1",
        target=target,
        status=MatchStatus.UNRESOLVED,
        method="title_artist_duration",
        candidates=[target],
        signals={"title": True, "duration_delta_s": 4.2},
        decided_at=NOW,
    )
    assert roundtrip(unresolved) == unresolved
    with pytest.raises(ValidationError):
        CrossSourceMatch(
            track_id="trk_1",
            target=target,
            status=MatchStatus.ACCEPTED,
            method="title_artist_duration",
            decided_at=NOW,
        )


def test_naive_datetimes_rejected() -> None:
    with pytest.raises(ValidationError):
        Provenance(source=DataSource.FMA, imported_at=datetime(2026, 1, 1))
