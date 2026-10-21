import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.ingestion.discogs_models import (
    DiscogsArtist,
    DiscogsArtistCredit,
    DiscogsRelease,
)
from music_discovery.ingestion.names import matching_key, strip_disambiguator
from music_discovery.ingestion.normalizer import (
    NormalizedRelease,
    artist_id_for,
    discogs_ext,
    master_id_for,
    normalize_artist,
    normalize_release,
    parse_duration,
    release_id_for,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "discogs"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def full() -> NormalizedRelease:
    return normalize_release(
        DiscogsRelease.model_validate(load("release_full.json")), imported_at=NOW
    )


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [
        ("4:35", 275.0),
        ("0:59", 59.0),
        ("12:01", 721.0),
        ("1:02:03", 3723.0),
        ("", None),
        (None, None),
        ("bad", None),
        ("4:75", None),
        ("4", None),
    ],
)
def test_parse_duration(raw: str | None, seconds: float | None) -> None:
    assert parse_duration(raw) == seconds


@pytest.mark.parametrize(
    ("raw", "display", "key"),
    [
        ("Lena Ostrova (2)", "Lena Ostrova", "lena ostrova"),
        ("The Reed Collective", "The Reed Collective", "reed collective"),
        ("Björk", "Björk", "bjork"),
        ("Simon & Garfunkel", "Simon & Garfunkel", "simon and garfunkel"),
        ("  A.B.C.  (12)", "A.B.C.", "a b c"),
    ],
)
def test_names(raw: str, display: str, key: str) -> None:
    assert strip_disambiguator(raw) == display
    assert matching_key(raw) == key


def test_headings_dropped_and_index_expanded(full: NormalizedRelease) -> None:
    titles = [t.title for t in full.tracks]
    assert titles == ["Low Tide Flute", "Reed Signal", "Dusk", "Dawn", "Coda"]
    assert [e.position for e in full.release.track_listing] == ["A1", "A2", "B1a", "B1b", "B2"]


def test_track_fields_link_back_to_release(full: NormalizedRelease) -> None:
    first = full.tracks[0]
    assert first.release_id == release_id_for(900001) == full.release.id
    assert first.master_release_id == master_id_for(800001)
    assert first.year == 1998
    assert first.genres == ["Electronic", "Jazz"]
    assert first.styles == ["Ambient", "Downtempo"], "duplicate style removed"
    assert first.discogs_url == "https://www.discogs.com/release/900001-Synthetic-Night-Woodwinds"
    assert first.provenance.source is DataSource.DISCOGS
    assert first.external_ids == [discogs_ext(ExternalIdKind.TRACK, "900001:A1")]
    assert first.audio_available is False
    assert all(e.track_id for e in full.release.track_listing)


def test_durations_unknown_stay_none(full: NormalizedRelease) -> None:
    assert [t.duration_seconds for t in full.tracks] == [275.0, None, 300.0, 3723.0, None]


def test_artist_credits_are_structured(full: NormalizedRelease) -> None:
    release_artists = full.release.artists
    assert [(a.name, a.join) for a in release_artists] == [
        ("Lena Ostrova", "&"),
        ("The Reed Collective", None),
    ]
    reed_signal = full.tracks[1]
    assert [(a.name, a.join) for a in reed_signal.artists] == [
        ("Marco Vell", "feat."),
        ("Lena Ostrova", None),
    ]
    assert full.tracks[0].artists == release_artists, (
        "tracks without credits inherit release artists"
    )
    lena = next(a for a in full.artists if a.name == "Lena Ostrova")
    assert lena.id == artist_id_for(DiscogsArtistCredit(id=700001, name="any name"))
    assert set(lena.aliases) == {"Lena O.", "Lena Ostrova (2)"}
    flute_player = next(a for a in full.artists if a.name == "Ines Daro")
    assert flute_player.external_ids == [discogs_ext(ExternalIdKind.ARTIST, 700004)]


def test_labels_deduplicated_with_catalog_number(full: NormalizedRelease) -> None:
    assert [(lbl.name, lbl.catalog_number) for lbl in full.release.labels] == [
        ("Quiet Field Records", "QF 012")
    ]
    assert [lbl.name for lbl in full.labels] == ["Quiet Field Records"]


def test_release_external_ids_include_master(full: NormalizedRelease) -> None:
    assert full.release.external_ids == [
        discogs_ext(ExternalIdKind.RELEASE, 900001),
        discogs_ext(ExternalIdKind.MASTER, 800001),
    ]


def test_minimal_release_unknowns() -> None:
    raw = DiscogsRelease.model_validate(load("release_minimal.json"))
    out = normalize_release(raw, imported_at=NOW)
    assert out.release.year is None
    assert out.release.master_release_id is None
    assert out.release.discogs_url is None
    assert [t.title for t in out.tracks] == ["First", "Second", "Lonely Index"]
    assert len({t.id for t in out.tracks}) == 3, "unnumbered tracks still get distinct ids"
    assert out.tracks[0].external_ids[0].value == "900002:#1"
    assert out.labels[0].external_ids == [], "labels without a Discogs id get no external id"
    various = out.artists[0]
    assert various.external_ids == []


def test_normalization_is_deterministic() -> None:
    raw = DiscogsRelease.model_validate(load("release_full.json"))
    assert normalize_release(raw, imported_at=NOW) == normalize_release(raw, imported_at=NOW)


def test_normalize_artist_keeps_variations() -> None:
    artist = normalize_artist(DiscogsArtist.model_validate(load("artist.json")), imported_at=NOW)
    assert artist.name == "Lena Ostrova"
    assert set(artist.aliases) == {
        "Lena Ostrova (2)",
        "Lena O.",
        "L. Ostrova",
        "Night Reed",
        "Lena Ostrovskaya",
    }
    assert artist.id == artist_id_for(DiscogsArtistCredit(id=700001, name="Lena Ostrova (2)"))
