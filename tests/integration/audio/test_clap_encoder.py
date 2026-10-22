"""Real CLAP checkpoint (ADR-0002). Slow: run with `pytest --run-slow`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from music_discovery.audio.clap_encoder import ClapEncoder
from music_discovery.domain.protocols import AudioEncoder, TextEncoder

pytestmark = pytest.mark.slow

CHECKPOINT = Path(__file__).parents[3] / "data" / "models" / "larger_clap_music_and_speech"
MODEL_ID = "laion/larger_clap_music_and_speech@195c3a3e68faebb3e2088b9a79e79b43ddbda76b"


@pytest.fixture(scope="module")
def encoder() -> ClapEncoder:
    if not (CHECKPOINT / "pytorch_model.bin").is_file():
        pytest.skip("CLAP checkpoint not fetched (scripts/fetch_clap_model.py)")
    return ClapEncoder(CHECKPOINT, MODEL_ID)


def write(path: Path, signal: np.ndarray, rate: int = 44100) -> Path:
    sf.write(str(path), signal.astype(np.float32), rate)
    return path


def tone(seconds: float, rate: int = 44100) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return 0.3 * np.sin(2 * np.pi * 440 * t)


def test_protocols_and_dimensions(encoder: ClapEncoder) -> None:
    assert isinstance(encoder, TextEncoder)
    assert isinstance(encoder, AudioEncoder)
    assert encoder.embedding_dim == 512


def test_text_embeddings_are_normalized_and_not_collapsed(encoder: ClapEncoder) -> None:
    texts = [
        "a pure sine tone",
        "white noise",
        "a calm flute melody",
        "aggressive heavy metal with drums",
    ]
    m = encoder.encode_texts(texts)
    assert m.shape == (4, 512)
    assert m.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(m, axis=1), 1.0, rtol=1e-4)
    sims = m @ m.T
    off_diagonal = sims[~np.eye(4, dtype=bool)]
    assert off_diagonal.max() < 0.9, "collapsed text tower (see ADR-0002)"
    single = encoder.encode_texts(["a calm flute melody"])
    np.testing.assert_allclose(single[0], m[2], atol=1e-4)


def test_audio_embeddings_are_deterministic(encoder: ClapEncoder, tmp_path: Path) -> None:
    path = write(tmp_path / "tone.wav", tone(30))
    first = encoder.encode_audio([path])
    second = encoder.encode_audio([path])
    assert first.shape == (1, 512)
    np.testing.assert_allclose(np.linalg.norm(first, axis=1), 1.0, rtol=1e-4)
    np.testing.assert_array_equal(first, second)
    short = encoder.encode_audio([write(tmp_path / "short.wav", tone(4))])
    assert short.shape == (1, 512)


def test_matching_description_ranks_first(encoder: ClapEncoder, tmp_path: Path) -> None:
    """Smoke check only (two synthetic sounds), not a quality claim."""
    rng = np.random.default_rng(0)
    clips = [
        write(tmp_path / "tone.wav", tone(10)),
        write(tmp_path / "noise.wav", rng.standard_normal(441000) * 0.1),
    ]
    audio = encoder.encode_audio(clips)
    text = encoder.encode_texts(["a pure sine tone", "white noise"])
    sims = audio @ text.T
    assert sims[0, 0] > sims[0, 1], "the tone is closer to 'a pure sine tone'"
    assert sims[1, 1] > sims[0, 1], "'white noise' is closer to the noise than to the tone"
