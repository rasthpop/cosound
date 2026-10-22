import pytest

from music_discovery.domain.protocols import LexicalIndex
from music_discovery.infrastructure.lexical_index import BM25FieldIndex, tokenize

DOCS = {
    "trk_1": {"title": "Low Tide Flute", "genres": "Folk", "tags": "calm"},
    "trk_2": {"title": "Night Drive", "genres": "Electronic | Ambient Electronic", "tags": ""},
    "trk_3": {"title": "Flute Flute Flute", "genres": "Experimental", "tags": ""},
    "trk_4": {"title": "Café Bossa", "genres": "Jazz | Latin", "tags": "warm"},
    "trk_5": {"title": "Drum & Bass Session", "genres": "Drum & Bass", "tags": ""},
}
WEIGHTS = {"title": 1.0, "genres": 2.0, "tags": 1.5}


@pytest.fixture
def index() -> BM25FieldIndex:
    return BM25FieldIndex(DOCS, field_weights=WEIGHTS)


def test_tokenize() -> None:
    assert tokenize("Café Bossa — Drum & Bass!") == ["cafe", "bossa", "drum", "and", "bass"]


def test_protocol(index: BM25FieldIndex) -> None:
    assert isinstance(index, LexicalIndex)
    assert index.size == 5


def test_search_ranks_and_skips_non_matches(index: BM25FieldIndex) -> None:
    results = index.search(["flute"], 10)
    assert [t for t, _ in results] == ["trk_3", "trk_1"], "higher term frequency ranks first"
    assert all(score > 0 for _, score in results)
    assert index.search(["violin"], 10) == []


def test_field_weights_matter(index: BM25FieldIndex) -> None:
    electronic = dict(index.search(["electronic"], 10))
    assert set(electronic) == {"trk_2"}
    genre_only = BM25FieldIndex(DOCS, field_weights={"genres": 2.0})
    title_only = BM25FieldIndex(DOCS, field_weights={"title": 1.0})
    assert genre_only.search(["electronic"], 5)
    assert title_only.search(["electronic"], 5) == []


def test_multi_token_terms_need_all_tokens_in_one_field(index: BM25FieldIndex) -> None:
    assert [t for t, _ in index.search(["drum and bass"], 5)] == ["trk_5"]
    assert [t for t, _ in index.search(["cafe"], 5)] == ["trk_4"], "accents are folded"
    assert index.search(["night flute"], 5) == []


def test_restrict_to_and_k(index: BM25FieldIndex) -> None:
    assert index.search(["flute"], 10, restrict_to=["trk_1", "trk_x"]) == [
        ("trk_1", pytest.approx(index.score("trk_1", ["flute"])))
    ]
    assert len(index.search(["flute"], 1)) == 1
    assert index.search(["flute"], 0) == []


def test_matches_report_fields(index: BM25FieldIndex) -> None:
    assert index.matches("trk_1", ["flute", "calm", "jazz"]) == [
        ("title", "flute"),
        ("tags", "calm"),
    ]
    assert index.matches("trk_5", ["drum and bass"]) == [
        ("title", "drum and bass"),
        ("genres", "drum and bass"),
    ]
    assert index.matches("trk_missing", ["flute"]) == []
