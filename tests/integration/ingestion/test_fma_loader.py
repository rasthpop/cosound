from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from music_discovery.audio.audio_probe import SoundfileProbe
from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlImportRunRepository,
    SqlReleaseRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.ingestion.fma_loader import (
    FmaImporter,
    FmaImportReport,
    FmaWriters,
    fma_audio_path,
    fma_ext,
    fma_track_id,
    load_echonest,
    load_genres,
    load_track_urls,
    load_tracks,
)
from tests.fakes import FrozenClock, SequentialIdGenerator

FIXTURES = Path(__file__).parents[2] / "fixtures" / "fma"


def write_wav(path: Path, seconds: float, amplitude: float = 0.3, rate: int = 22050) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    sf.write(
        str(path), (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32), rate, format="WAV"
    )
    return path


# --- Paths & metadata ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("tid", "expected"),
    [
        (2, "000/000002.mp3"),
        (140, "000/000140.mp3"),
        (999, "000/000999.mp3"),
        (123456, "123/123456.mp3"),
    ],
)
def test_audio_path(tid: int, expected: str) -> None:
    assert fma_audio_path(Path("/a"), tid) == Path("/a") / expected


def test_load_tracks_parses_two_row_header_and_lists() -> None:
    records = {r.fma_track_id: r for r in load_tracks(FIXTURES, subset="small")}
    assert sorted(records) == [2, 5, 140, 999], "large-only track filtered out"
    first = records[2]
    assert first.title == "Low Tide"
    assert first.artist_name == "Synthetic Artist"
    assert first.album_title == "Synthetic Album"
    assert first.year == 2009
    assert first.genre_ids == [17]
    assert first.tags == ["flute", "calm"]
    assert first.duration_seconds == 168.0
    assert first.license == "Attribution-NonCommercial 3.0 International"
    assert first.split == "training"
    assert records[5].license is None
    assert records[5].genre_ids == [17, 103]
    assert records[140].year is None
    assert records[999].title is None
    assert records[999].genre_top is None


def test_load_tracks_subsets_are_nested() -> None:
    assert len(load_tracks(FIXTURES, subset="large")) == 5
    assert len(load_tracks(FIXTURES, subset=None)) == 5
    with pytest.raises(ValueError, match="unknown FMA subset"):
        load_tracks(FIXTURES, subset="tiny")


def test_load_tracks_out_of_range_year_is_none() -> None:
    large = {r.fma_track_id: r for r in load_tracks(FIXTURES, subset="large")}
    assert large[123456].year == 1890


def test_track_urls_skip_missing_and_invalid() -> None:
    assert load_track_urls(FIXTURES) == {
        2: "https://freemusicarchive.org/music/Synthetic_Artist/Synthetic_Album/Low_Tide"
    }
    assert load_track_urls(FIXTURES / "nowhere") == {}


def test_genres_and_echonest() -> None:
    assert load_genres(FIXTURES)[103] == "Psych-Folk"
    echonest = load_echonest(FIXTURES)
    assert echonest[2] == {"acousticness": 0.9, "instrumentalness": 0.85, "tempo": 92.0}
    assert "instrumentalness" not in echonest[140], "missing values stay missing"
    assert load_echonest(FIXTURES, [140]).keys() == {140}
    assert load_echonest(FIXTURES / "nowhere") == {}


# --- Audio probe -------------------------------------------------------------------------


def test_probe_accepts_decodable_audio(tmp_path: Path) -> None:
    result = SoundfileProbe().probe(write_wav(tmp_path / "ok.wav", 6.0))
    assert result.ok
    assert result.duration_seconds == pytest.approx(6.0, abs=0.01)
    assert result.sample_rate == 22050


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        (lambda p: p, "audio_missing"),
        (lambda p: (p.write_bytes(b""), p)[1], "audio_empty"),
        (lambda p: (p.write_bytes(b"definitely not audio" * 50), p)[1], "audio_decode_error"),
        (lambda p: write_wav(p, 1.0), "audio_too_short"),
        (lambda p: write_wav(p, 6.0, amplitude=0.0), "audio_silent"),
    ],
)
def test_probe_rejects_unusable_audio(
    tmp_path: Path, setup: Callable[[Path], Path], code: str
) -> None:
    path = setup(tmp_path / "clip.wav")
    result = SoundfileProbe().probe(path)
    assert not result.ok
    assert result.error_code == code


# --- Import -------------------------------------------------------------------------------


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(f"sqlite:///{tmp_path / 'catalog.db'}")
    database.init_schema()
    yield database
    database.dispose()


def run_import(database: Database, data_dir: Path) -> FmaImportReport:
    writers = FmaWriters(
        tracks=SqlTrackRepository(database),
        releases=SqlReleaseRepository(database),
        artists=SqlArtistRepository(database),
        audio=SqlTrackAudioRepository(database),
        runs=SqlImportRunRepository(database),
        uow=database,
    )
    importer = FmaImporter(
        writers,
        SoundfileProbe(),
        data_dir=data_dir,
        clock=FrozenClock(),
        ids=SequentialIdGenerator(),
    )
    return importer.run(
        load_tracks(FIXTURES),
        audio_dir=data_dir / "raw" / "fma" / "fma_small",
        genres=load_genres(FIXTURES),
        source_urls=load_track_urls(FIXTURES),
    )


def test_import_links_metadata_and_validated_audio(database: Database, data_dir: Path) -> None:
    audio_dir = data_dir / "raw" / "fma" / "fma_small"
    write_wav(fma_audio_path(audio_dir, 2), 8.0)  # valid
    (fma_audio_path(audio_dir, 5)).write_bytes(b"")  # present but broken
    report = run_import(database, data_dir)
    assert report.counts == {
        "tracks": 3,
        "audio_valid": 1,
        "audio_missing": 1,
        "audio_invalid": 1,
        "skipped": 1,
    }
    assert {(f.key, f.code) for f in report.failures} == {
        ("fma:5", "audio_empty"),
        ("fma:999", "missing_title"),
    }

    tracks = SqlTrackRepository(database)
    with_audio = tracks.get(fma_track_id(2))
    assert with_audio is not None
    assert with_audio.audio_source is DataSource.FMA
    assert with_audio.audio_path == "raw/fma/fma_small/000/000002.mp3"
    assert with_audio.genres == ["Folk"]
    assert with_audio.tags == ["flute", "calm"]
    assert with_audio.artists[0].name == "Synthetic Artist"
    assert with_audio.release_id is not None
    assert with_audio.audio_available is False, "decodable, but not analyzed until embeddings exist"
    assert tracks.find_by_external_id(fma_ext(ExternalIdKind.TRACK, 2)) == with_audio

    assert with_audio.source_url == (
        "https://freemusicarchive.org/music/Synthetic_Artist/Synthetic_Album/Low_Tide"
    )
    assert with_audio.discogs_url is None

    broken = tracks.get(fma_track_id(5))
    assert broken is not None
    assert broken.audio_path is None, "broken file must not be presented as audio"
    assert broken.genres == ["Folk", "Psych-Folk"]
    assert broken.source_url is None, "empty URL stays missing"

    audio = SqlTrackAudioRepository(database).list_all()
    assert [a.track_id for a in audio] == [fma_track_id(2)]
    assert audio[0].license == "Attribution-NonCommercial 3.0 International"
    assert audio[0].duration_seconds == pytest.approx(8.0, abs=0.01)

    run = SqlImportRunRepository(database).latest(DataSource.FMA)
    assert run is not None
    assert run.counts["tracks"] == 3


def test_reimport_is_idempotent(database: Database, data_dir: Path) -> None:
    run_import(database, data_dir)
    ids = [t.id for t in SqlTrackRepository(database).list_page(limit=50)]
    run_import(database, data_dir)
    assert [t.id for t in SqlTrackRepository(database).list_page(limit=50)] == ids
