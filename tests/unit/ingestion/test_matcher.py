from datetime import UTC, datetime

import pytest

from music_discovery.domain.enums import DataSource, ExternalIdKind, MatchStatus
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.ingestion.matcher import SourceMatcher

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def discogs(
    track_id: str, title: str, artist: str, duration: float | None, release: str, pos: str
) -> Track:
    return Track(
        id=track_id,
        title=title,
        artists=[ArtistReference(artist_id=f"art_{artist}", name=artist)],
        duration_seconds=duration,
        release_id=release,
        external_ids=[
            ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.TRACK, value=f"1:{pos}")
        ],
        provenance=Provenance(source=DataSource.DISCOGS),
    )


def fma(
    title: str, artist: str, duration: float | None, release: str = "rel_fma", fma_id: str = "2"
) -> Track:
    return Track(
        id="trk_fma",
        title=title,
        artists=[ArtistReference(artist_id="art_fma", name=artist)],
        duration_seconds=duration,
        release_id=release,
        external_ids=[ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value=fma_id)],
        provenance=Provenance(source=DataSource.FMA),
    )


RELEASES = {"rel_d1": "Night Woodwinds", "rel_d2": "Live Versions", "rel_fma": "Night Woodwinds"}


def matcher(*tracks: Track) -> SourceMatcher:
    return SourceMatcher(tracks, release_titles=RELEASES)


def test_exact_match_with_duration_is_accepted() -> None:
    m = matcher(discogs("trk_d", "Low Tide Flute", "Lena Ostrova (2)", 275, "rel_d1", "A1"))
    decision = m.match(fma("Low Tide Flute!", "lena ostrova", 276), decided_at=NOW)
    assert decision is not None
    assert decision.status is MatchStatus.ACCEPTED
    assert decision.target.value == "1:A1"
    assert decision.target_position == "A1"
    assert decision.confidence is not None
    assert decision.confidence > 0.9
    assert decision.signals["chosen"]["duration_delta_s"] == 1.0  # type: ignore[index]


def test_release_title_alone_can_corroborate() -> None:
    m = matcher(discogs("trk_d", "Low Tide Flute", "Lena Ostrova", None, "rel_d1", "A1"))
    decision = m.match(fma("Low Tide Flute", "Lena Ostrova", None), decided_at=NOW)
    assert decision is not None
    assert decision.status is MatchStatus.ACCEPTED


def test_title_and_artist_without_corroboration_stay_unresolved() -> None:
    m = matcher(discogs("trk_d", "Low Tide Flute", "Lena Ostrova", None, "rel_d2", "A1"))
    decision = m.match(
        fma("Low Tide Flute", "Lena Ostrova", 275, release="rel_other"), decided_at=NOW
    )
    assert decision is not None
    assert decision.status is MatchStatus.UNRESOLVED
    assert decision.confidence is None


@pytest.mark.parametrize(
    "query",
    [
        fma("Low Tide Flute", "Someone Else", 275),  # title only
        fma("Completely Different", "Lena Ostrova", 275),  # artist only
    ],
)
def test_single_signal_is_never_a_match(query: Track) -> None:
    m = matcher(discogs("trk_d", "Low Tide Flute", "Lena Ostrova", 275, "rel_d1", "A1"))
    assert m.match(query, decided_at=NOW) is None


def test_two_equally_good_candidates_are_unresolved() -> None:
    m = matcher(
        discogs("trk_d1", "Low Tide Flute", "Lena Ostrova", 275, "rel_d1", "A1"),
        discogs("trk_d2", "Low Tide Flute", "Lena Ostrova", 274, "rel_d2", "B3"),
    )
    decision = m.match(fma("Low Tide Flute", "Lena Ostrova", 275), decided_at=NOW)
    assert decision is not None
    assert decision.status is MatchStatus.UNRESOLVED
    assert {c.value for c in decision.candidates} == {"1:A1", "1:B3"}


def test_contradicting_duration_is_rejected() -> None:
    m = matcher(discogs("trk_d", "Low Tide Flute", "Lena Ostrova", 275, "rel_d1", "A1"))
    decision = m.match(fma("Low Tide Flute", "Lena Ostrova", 420), decided_at=NOW)
    assert decision is not None
    assert decision.status is MatchStatus.REJECTED


def test_ids_are_never_compared() -> None:
    """An FMA id equal to a Discogs value must not create a match on its own."""
    m = matcher(discogs("trk_d", "Other Title", "Other Artist", 275, "rel_d1", "2"))
    assert m.match(fma("Low Tide Flute", "Lena Ostrova", 275, fma_id="1:2"), decided_at=NOW) is None


def test_discogs_tracks_without_discogs_ids_are_ignored() -> None:
    no_ext = discogs("trk_d", "Low Tide Flute", "Lena Ostrova", 275, "rel_d1", "A1").model_copy(
        update={"external_ids": []}
    )
    assert matcher(no_ext).match(fma("Low Tide Flute", "Lena Ostrova", 275), decided_at=NOW) is None
