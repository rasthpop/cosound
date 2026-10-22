from __future__ import annotations

import pytest

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import ArtistReference, Provenance, Track
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.infrastructure.lexical_index import BM25FieldIndex
from music_discovery.retrieval.metadata_retriever import (
    DEFAULT_FIELD_WEIGHTS,
    MetadataRetriever,
    TrackFacts,
    era_range,
    metadata_document,
)

FMA = Provenance(source=DataSource.FMA)


def track(
    tid: str,
    title: str,
    artist: str,
    genres: list[str],
    tags: list[str] | None = None,
    year: int | None = None,
) -> Track:
    return Track(
        id=tid,
        title=title,
        artists=[ArtistReference(artist_id=f"art_{artist}", name=artist)],
        genres=genres,
        tags=tags or [],
        year=year,
        provenance=FMA,
    )


CATALOG = [
    track("trk_flute_title", "Flute Song", "Lena", ["Folk"], year=1985),
    track(
        "trk_ambient",
        "Drift",
        "Blue Dot Sessions",
        ["Electronic", "Ambient Electronic"],
        ["chill"],
        2014,
    ),
    track("trk_jazz", "Helado", "Blue Dot Sessions", ["Jazz"], ["warm", "relaxed"], 2015),
    track("trk_punk", "Noise", "Riot", ["Rock", "Punk"], year=1979),
    track("trk_unknown_year", "Untitled", "Anon", ["Experimental"]),
]
ALBUMS = {"trk_jazz": "Late Night Cafe"}


@pytest.fixture
def retriever() -> MetadataRetriever:
    docs = {t.id: metadata_document(t, ALBUMS.get(t.id)) for t in CATALOG}
    index = BM25FieldIndex(docs, field_weights=DEFAULT_FIELD_WEIGHTS)
    facts = {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in CATALOG}
    return MetadataRetriever(index, facts)


def spec(**kw: object) -> SearchSpecification:
    return SearchSpecification.model_validate({"original_query": "q", **kw})


def pref(value: str) -> dict[str, object]:
    return {"value": value, "weight": 0.8}


def test_genre_tag_match(retriever: MetadataRetriever) -> None:
    result = retriever.retrieve(spec(genre_preferences=[pref("ambient")]), k=5)
    assert [h.track_id for h in result.hits] == ["trk_ambient"]
    match = result.hits[0].matched_fields[0]
    assert (match.field, match.term, match.kind, match.source) == (
        "genres",
        "ambient",
        "tag",
        DataSource.FMA,
    )


def test_artist_and_album_match(retriever: MetadataRetriever) -> None:
    by_artist = retriever.retrieve(spec(original_query="blue dot sessions"), k=5)
    assert {h.track_id for h in by_artist.hits} == {"trk_ambient", "trk_jazz"}
    by_album = retriever.retrieve(spec(original_query="late night cafe"), k=5)
    assert by_album.hits[0].track_id == "trk_jazz"
    assert {m.field for m in by_album.hits[0].matched_fields} == {"album"}


def test_flute_in_title_is_lexical_not_instrument_evidence(retriever: MetadataRetriever) -> None:
    result = retriever.retrieve(
        spec(original_query="Something with a flute", instrument_preferences=[pref("flute")]), k=5
    )
    hit = result.hits[0]
    assert hit.track_id == "trk_flute_title"
    assert {(m.field, m.kind) for m in hit.matched_fields} == {("title", "lexical")}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1980s", (1980, 1989)),
        ("80s", (1980, 1989)),
        ("80's", (1980, 1989)),
        ("00s", (2000, 2009)),
        ("1995", (1995, 1995)),
        ("2010s", (2010, 2019)),
        ("modern", None),
        ("8", None),
    ],
)
def test_era_range(value: str, expected: tuple[int, int] | None) -> None:
    assert era_range(value) == expected


def test_era_match_uses_year(retriever: MetadataRetriever) -> None:
    result = retriever.retrieve(spec(era_preferences=[pref("80s")]), k=5)
    assert [h.track_id for h in result.hits] == ["trk_flute_title"]
    assert [(m.field, m.kind) for m in result.hits[0].matched_fields] == [("year", "tag")]


def test_query_words_drop_stopwords_and_negatives(retriever: MetadataRetriever) -> None:
    s = spec(
        original_query="Something warm with jazz",
        genre_preferences=[pref("jazz")],
        negative_preferences=[pref("warm")],
    )
    assert retriever.query_terms(s) == ["jazz"]
    negatives = retriever.negative_matches(s, ["trk_jazz", "trk_punk"])
    assert list(negatives) == ["trk_jazz"], "only tracks containing a negative term"
    assert [(m.field, m.term) for m in negatives["trk_jazz"]] == [("tags", "warm")]


def test_score_covers_every_track_including_zero(retriever: MetadataRetriever) -> None:
    result = retriever.score(
        spec(genre_preferences=[pref("jazz")]), ["trk_jazz", "trk_punk", "trk_not_in_catalog"]
    )
    assert [(h.track_id, h.raw_score > 0) for h in result.hits] == [
        ("trk_jazz", True),
        ("trk_punk", False),
    ]
    assert result.score_of("trk_punk") == 0.0, "evaluated and no match is 0.0"
    assert result.score_of("trk_not_in_catalog") is None


def test_no_terms_no_hits(retriever: MetadataRetriever) -> None:
    assert retriever.retrieve(spec(original_query="something please"), k=5).hits == []


def test_synonym_hook(retriever: MetadataRetriever) -> None:
    docs = {t.id: metadata_document(t, None) for t in CATALOG}
    expanding = MetadataRetriever(
        BM25FieldIndex(docs, field_weights=DEFAULT_FIELD_WEIGHTS),
        {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in CATALOG},
        expand=lambda term: [term, "chill"] if term == "relaxed" else [term],
    )
    assert "trk_ambient" in {
        h.track_id for h in expanding.retrieve(spec(mood_preferences=[pref("relaxed")]), k=5).hits
    }
