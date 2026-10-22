from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from music_discovery.audio.embedding_builder import EmbeddingBuilder
from music_discovery.audio.embedding_store import NpyEmbeddingStore, read_failures
from music_discovery.domain.enums import DataSource
from music_discovery.domain.errors import AudioDecodeError, AudioMissing, EmbeddingError
from music_discovery.domain.models import Provenance, Track, TrackAudio
from music_discovery.domain.protocols import Matrix
from tests.fakes import (
    FakeEncoder,
    FrozenClock,
    InMemoryTrackAudioRepository,
    InMemoryTrackRepository,
    InMemoryUnitOfWork,
)


class PickyEncoder(FakeEncoder):
    """Fails like the real encoder for missing or undecodable files."""

    def __init__(self, broken: set[str]) -> None:
        super().__init__(dim=8)
        self.broken = broken
        self.calls = 0

    def encode_audio(self, paths: Sequence[Path]) -> Matrix:
        self.calls += 1
        for p in paths:
            if not p.is_file():
                raise AudioMissing(f"missing {p}")
            if p.name in self.broken:
                raise AudioDecodeError(f"cannot decode {p}")
        return super().encode_audio(paths)


Catalog = tuple[InMemoryTrackRepository, InMemoryTrackAudioRepository]


@pytest.fixture
def catalog(data_dir: Path) -> Catalog:
    tracks, audio = InMemoryTrackRepository(), InMemoryTrackAudioRepository()
    for i in range(5):
        tid = f"trk_{i}"
        rel = f"raw/fma/fma_small/000/00000{i}.mp3"
        if i != 3:  # track 3's file is missing on disk
            (data_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (data_dir / rel).write_bytes(b"x")
        tracks.upsert(Track(id=tid, title=f"T{i}", provenance=Provenance(source=DataSource.FMA)))
        audio.upsert(TrackAudio(track_id=tid, source=DataSource.FMA, file_path=rel))
    return tracks, audio


def builder(encoder: PickyEncoder, catalog: Catalog, data_dir: Path) -> EmbeddingBuilder:
    tracks, audio = catalog
    return EmbeddingBuilder(
        encoder,
        audio,
        tracks,
        InMemoryUnitOfWork(tracks, audio),
        data_dir=data_dir,
        embeddings_dir=data_dir / "embeddings",
        clock=FrozenClock(),
    )


def test_build_writes_store_reports_failures_and_marks_tracks(
    catalog: Catalog, data_dir: Path
) -> None:
    encoder = PickyEncoder(broken={"000004.mp3"})
    report = builder(encoder, catalog, data_dir).run()
    assert report.requested == 5
    assert report.embedded == 3
    assert {(f.track_id, f.error_code) for f in report.failures} == {
        ("trk_3", "audio_missing"),
        ("trk_4", "audio_decode_error"),
    }
    assert report.directory is not None
    store = NpyEmbeddingStore.load(report.directory, expected_model_id=encoder.model_id)
    assert store.track_ids() == ["trk_0", "trk_1", "trk_2"]
    assert store.meta.failures == 2
    assert len(read_failures(report.directory)) == 2

    tracks, audio = catalog
    assert tracks.get("trk_0").audio_available  # type: ignore[union-attr]
    assert not tracks.get("trk_3").audio_available, "failed tracks stay unanalyzed"  # type: ignore[union-attr]
    assert audio.get("trk_0").embedding_version == report.embedding_version  # type: ignore[union-attr]
    assert audio.get("trk_4").embedding_version is None  # type: ignore[union-attr]


def test_rerun_with_same_inputs_is_a_no_op(catalog: Catalog, data_dir: Path) -> None:
    encoder = PickyEncoder(broken=set())
    first = builder(encoder, catalog, data_dir).run()
    calls = encoder.calls
    second = builder(encoder, catalog, data_dir).run()
    assert second.skipped_existing
    assert encoder.calls == calls
    assert second.embedding_version == first.embedding_version


def test_interrupted_run_resumes_from_cache(catalog: Catalog, data_dir: Path) -> None:
    encoder = PickyEncoder(broken=set())
    build = builder(encoder, catalog, data_dir)

    class StopError(Exception):
        pass

    def stop_after_two(done: int, total: int) -> None:
        if done == 2:
            raise StopError

    build._progress = stop_after_two
    with pytest.raises(StopError):
        build.run()
    build._progress = None
    calls_before = encoder.calls
    report = build.run()
    assert report.from_cache == 2
    assert encoder.calls - calls_before == 3, "only the 3 tracks without a cached vector are tried"
    assert report.embedded == 4


def test_changed_track_set_requires_force(catalog: Catalog, data_dir: Path) -> None:
    encoder = PickyEncoder(broken=set())
    build = builder(encoder, catalog, data_dir)
    build.run(track_ids=["trk_0", "trk_1"])
    with pytest.raises(EmbeddingError, match="different track set"):
        build.run()
    report = build.run(force=True)
    assert report.embedded == 4


def test_embeddings_are_cached_vectors(catalog: Catalog, data_dir: Path) -> None:
    encoder = PickyEncoder(broken=set())
    report = builder(encoder, catalog, data_dir).run(track_ids=["trk_0"])
    store = NpyEmbeddingStore.load(report.directory, expected_model_id=None)  # type: ignore[arg-type]
    cached = np.load(data_dir / "embeddings" / "cache" / report.embedding_version / "trk_0.npy")
    np.testing.assert_array_equal(store.get("trk_0"), cached)
