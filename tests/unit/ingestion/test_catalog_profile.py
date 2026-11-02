from __future__ import annotations

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import ArtistReference, Provenance, Track, TrackAudio
from music_discovery.ingestion.catalog_report import profile
from tests.fakes import InMemoryTrackAudioRepository, InMemoryTrackRepository

FMA = Provenance(source=DataSource.FMA)


def test_profile_counts_missing_values_and_coverage() -> None:
    tracks = InMemoryTrackRepository()
    tracks.upsert(
        Track(
            id="trk_a",
            title="A",
            provenance=FMA,
            genres=["Folk", "Pop"],
            year=2001,
            artists=[ArtistReference(artist_id="art_1", name="X")],
        )
    )
    tracks.upsert(Track(id="trk_b", title="B", provenance=FMA, genres=["Folk"]))
    tracks.upsert(Track(id="trk_c", title="C", provenance=FMA))
    audio = InMemoryTrackAudioRepository()
    audio.upsert(
        TrackAudio(track_id="trk_a", source=DataSource.FMA, file_path="a.mp3", license="CC BY")
    )
    audio.upsert(TrackAudio(track_id="trk_b", source=DataSource.FMA, file_path="b.mp3"))

    p = profile(tracks, audio)

    assert p.tracks == 3
    assert p.present["year"] == 1
    assert p.present["artists"] == 1
    assert p.present["genres"] == 2
    assert p.present["styles"] == 0
    assert p.first_genre == {"Folk": 2, "(none)": 1}
    assert p.genres_per_track == {0: 1, 1: 1, 2: 1}
    assert p.with_decodable_audio == 2
    assert p.without_audio == ["trk_c"]
    assert p.audio_licenses == {"CC BY": 1, "(not recorded)": 1}
