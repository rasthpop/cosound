from pathlib import Path

from music_discovery.ingestion.fma_loader import FmaTrackRecord
from music_discovery.ingestion.fma_manifest import (
    MANIFEST_COLUMNS,
    license_permits_research,
    read_manifest,
    render_manifest,
    select_manifest,
)

GENRES = {1: "Folk", 2: "Ambient", 3: "Punk", 4: "Jazz"}


def record(tid: int, **kw: object) -> FmaTrackRecord:
    values: dict[str, object] = {
        "fma_track_id": tid,
        "title": f"Track {tid}",
        "artist_id": tid,
        "artist_name": f"Artist {tid}",
        "album_id": None,
        "album_title": None,
        "year": None,
        "genre_top": "Folk",
        "genre_ids": [1],
        "genre_all_ids": [1],
        "tags": [],
        "duration_seconds": 30.0,
        "license": "Attribution",
        "subset": "small",
        "split": "training",
    }
    values.update(kw)
    return FmaTrackRecord.model_validate(values)


POOL = [
    record(1, title="Flute Morning"),
    record(2, title="Second Flute", artist_name="Artist 1"),  # same artist as track 1
    record(3, title="Flute Without License", license=None),
    record(4, genre_ids=[2], genre_all_ids=[2], genre_top="Electronic"),
    record(5, genre_ids=[3], genre_all_ids=[3], genre_top="Rock"),
    record(6, genre_ids=[4], genre_all_ids=[4], genre_top="International"),
    *[record(100 + i) for i in range(30)],
]


def test_license_filter() -> None:
    assert license_permits_research("Attribution-NonCommercial 3.0 International")
    assert license_permits_research("CC0 1.0 Universal")
    assert not license_permits_research(None)
    assert not license_permits_research("All rights reserved")


def test_selection_is_deterministic_and_sized() -> None:
    first = select_manifest(POOL, genres=GENRES, echonest={})
    second = select_manifest(list(reversed(POOL)), genres=GENRES, echonest={})
    assert [r.record.fma_track_id for r in first] == [r.record.fma_track_id for r in second]
    assert len(first) == 20
    assert select_manifest(POOL, genres=GENRES, echonest={}, seed=7) != first


def test_selection_rules() -> None:
    rows = select_manifest(POOL, genres=GENRES, echonest={})
    ids = {r.record.fma_track_id for r in rows}
    assert 3 not in ids, "unlicensed track excluded"
    assert not {1, 2} <= ids, "at most one track per artist"
    themes = {r.record.fma_track_id: r.theme for r in rows}
    assert themes.get(1) == "flute"
    assert themes.get(4) == "ambient_atmospheric"
    assert themes.get(5) == "aggressive_fast"
    assert themes.get(6) == "jazz"
    assert len({r.record.artist_name for r in rows}) == len(rows)


def test_render_roundtrip(tmp_path: Path) -> None:
    rows = select_manifest(POOL, genres=GENRES, echonest={})
    content = render_manifest(rows, audio_dir_rel=Path("raw/fma/fma_small"))
    assert content == render_manifest(rows, audio_dir_rel=Path("raw/fma/fma_small"))
    path = tmp_path / "m.csv"
    path.write_text(content)
    parsed = read_manifest(path)
    assert tuple(parsed[0]) == MANIFEST_COLUMNS
    assert (
        parsed[0]["audio_path"] == f"raw/fma/fma_small/000/{int(parsed[0]['fma_track_id']):06d}.mp3"
    )
    assert {row["listening_status"] for row in parsed} == {"pending"}
    assert {row["split"] for row in parsed} == {"corpus"}


def test_committed_manifest_shape() -> None:
    path = Path(__file__).parents[3] / "data" / "evaluation" / "fma_20_manifest.csv"
    rows = read_manifest(path)
    assert len(rows) == 20
    assert len({r["fma_track_id"] for r in rows}) == 20
    assert len({r["artist"] for r in rows}) == 20
    assert all(r["license"] for r in rows)
    assert all(r["listening_status"] in {"pending", "confirmed"} for r in rows)
