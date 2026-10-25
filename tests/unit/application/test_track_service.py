from __future__ import annotations

from pathlib import Path

import pytest

from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.errors import AudioMissing, InvalidRequest, TrackNotFound
from music_discovery.domain.models import TrackAudio
from tests.support.world import AUDIO_BYTES, World


def test_detail_has_release_relationships_audio_and_coordinates() -> None:
    detail = World().track_service.get("trk_night")
    assert detail.view.track.title == "Night Train"
    assert detail.release is None  # no release recorded: stays None
    assert detail.view.audio is not None
    assert detail.view.coordinates is not None
    assert [r.view.track.id for r in detail.related] == ["trk_bus"]
    assert detail.relationship_counts == {RelationshipType.SAME_ARTIST: 1}

    garden = World().track_service.get("trk_both")
    assert garden.release is not None
    assert garden.release.title == "Garden Sessions"


def test_detail_of_track_without_audio_keeps_nulls() -> None:
    detail = World().track_service.get("trk_tape")
    assert detail.view.audio is None
    assert detail.view.coordinates is None
    assert detail.view.track.source_url is None


def test_unknown_track_is_not_found() -> None:
    service = World().track_service
    with pytest.raises(TrackNotFound):
        service.get("trk_missing")
    with pytest.raises(TrackNotFound):
        service.neighbors("trk_missing", 5)


def test_neighbors_come_from_the_original_space() -> None:
    result = World().track_service.neighbors("trk_night", 3)
    assert result.metric == "clap_cosine"
    assert result.items[0].view.track.id == "trk_bus"
    assert result.items[0].neighbor.score is not None
    assert "trk_night" not in [i.view.track.id for i in result.items]


def test_neighbors_without_embedding_or_semantic_are_labeled() -> None:
    no_audio = World().track_service.neighbors("trk_tape", 3)
    assert (no_audio.metric, no_audio.reason, no_audio.items) == (
        "catalog_relationship",
        "no_audio_embedding",
        [],
    )
    degraded = World(semantic=False).track_service.neighbors("trk_night", 3)
    assert degraded.reason == "semantic_unavailable"
    assert [i.view.track.id for i in degraded.items] == ["trk_bus"]


@pytest.mark.parametrize("k", [0, 51])
def test_neighbor_k_is_bounded(k: int) -> None:
    with pytest.raises(InvalidRequest):
        World().track_service.neighbors("trk_night", k)


def test_audio_file_resolves_inside_data_dir(tmp_path: Path) -> None:
    world = World(data_dir=tmp_path)
    audio = world.track_service.audio_file("trk_sound")
    assert audio.path == (tmp_path / "raw/fma/trk_sound.mp3").resolve()
    assert audio.path.read_bytes() == AUDIO_BYTES
    assert audio.media_type == "audio/mpeg"
    assert audio.license == "Attribution 4.0 International"


def test_audio_missing_cases(tmp_path: Path) -> None:
    world = World(data_dir=tmp_path)
    with pytest.raises(AudioMissing):
        world.track_service.audio_file("trk_tape")  # no TrackAudio record
    (tmp_path / "raw/fma/trk_title.mp3").unlink()
    with pytest.raises(AudioMissing):
        world.track_service.audio_file("trk_title")  # record but no file
    secret = tmp_path.parent / "secret.mp3"
    secret.write_bytes(b"x")
    world.audio.upsert(
        TrackAudio(track_id="trk_bus", source=DataSource.FMA, file_path="../secret.mp3")
    )
    with pytest.raises(AudioMissing, match="outside DATA_DIR"):
        world.track_service.audio_file("trk_bus")
    with pytest.raises(TrackNotFound):
        world.track_service.audio_file("trk_missing")
