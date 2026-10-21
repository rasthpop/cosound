from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from music_discovery.audio.clap_encoder import (
    SAMPLE_RATE,
    ClapEncoder,
    load_mono_48k,
    split_windows,
)
from music_discovery.domain.errors import AudioDecodeError, AudioMissing, ModelLoadError


def seconds(n: float) -> np.ndarray:
    return np.zeros(int(n * SAMPLE_RATE), dtype=np.float32)


@pytest.mark.parametrize(
    ("length_s", "expected"),
    [
        (30.0, [10.0, 10.0, 10.0]),
        (29.98, [10.0, 10.0, 9.98]),
        (21.0, [10.0, 10.0]),
        (24.0, [10.0, 10.0, 4.0]),
        (6.0, [6.0]),
        (2.0, [2.0]),
        (45.0, [10.0, 10.0, 10.0]),
    ],
)
def test_split_windows(length_s: float, expected: list[float]) -> None:
    windows = split_windows(seconds(length_s))
    assert [round(w.size / SAMPLE_RATE, 2) for w in windows] == expected


def test_split_windows_rejects_empty() -> None:
    with pytest.raises(AudioDecodeError):
        split_windows(np.zeros(0, dtype=np.float32))


def test_load_resamples_and_downmixes(tmp_path: Path) -> None:
    rate = 22050
    t = np.arange(rate * 2) / rate
    stereo = np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)], axis=1) * 0.5
    path = tmp_path / "stereo.wav"
    sf.write(str(path), stereo.astype(np.float32), rate)
    audio = load_mono_48k(path)
    assert audio.ndim == 1
    assert audio.dtype == np.float32
    assert audio.size == pytest.approx(2 * SAMPLE_RATE, abs=2)


def test_load_truncates_to_max_seconds(tmp_path: Path) -> None:
    path = tmp_path / "long.wav"
    sf.write(str(path), np.zeros(SAMPLE_RATE * 40, dtype=np.float32), SAMPLE_RATE)
    assert load_mono_48k(path).size == SAMPLE_RATE * 30


def test_load_errors(tmp_path: Path) -> None:
    with pytest.raises(AudioMissing):
        load_mono_48k(tmp_path / "nope.mp3")
    garbage = tmp_path / "garbage.mp3"
    garbage.write_bytes(b"not audio" * 100)
    with pytest.raises(AudioDecodeError):
        load_mono_48k(garbage)


def test_missing_checkpoint_raises_model_load_error(tmp_path: Path) -> None:
    encoder = ClapEncoder(tmp_path / "no-model", "clap@x")
    assert encoder.model_id == "clap@x"
    with pytest.raises(ModelLoadError):
        encoder.encode_texts(["flute"])
