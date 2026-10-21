"""CLAP text and audio encoder (ADR-0002; implements `AudioEncoder` and `TextEncoder`).

The model is loaded lazily from a local snapshot (never downloaded at runtime). Audio is decoded,
downmixed to mono, resampled to 48 kHz and split into fixed 10 s windows, so embeddings are
deterministic (the processor's default random crop is never triggered). Window embeddings are
mean-pooled; every output vector is L2-normalized float32.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from importlib.metadata import version
from math import gcd
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import soundfile as sf
from scipy.signal import resample_poly

from music_discovery.domain.errors import AudioDecodeError, AudioMissing, ModelLoadError
from music_discovery.domain.protocols import Matrix, Vector
from music_discovery.domain.vectors import l2_normalize

log = logging.getLogger(__name__)

SAMPLE_RATE = 48_000
WINDOW_S = 10.0
MAX_WINDOWS = 3
MIN_TAIL_S = 3.0


def load_mono_48k(
    path: Path, *, max_seconds: float = WINDOW_S * MAX_WINDOWS
) -> npt.NDArray[np.float32]:
    """Decode an audio file to mono float32 at 48 kHz (at most `max_seconds`)."""
    if not path.is_file():
        raise AudioMissing(f"audio file not found: {path}", details={"path": str(path)})
    try:
        info = sf.info(str(path))
        frames = int(min(info.frames, info.samplerate * max_seconds))
        data, rate = sf.read(str(path), frames=frames, dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError, ValueError) as exc:
        raise AudioDecodeError(f"cannot decode {path}", details={"path": str(path)}) from exc
    mono = data.mean(axis=1)
    if rate != SAMPLE_RATE:
        divisor = gcd(int(rate), SAMPLE_RATE)
        mono = resample_poly(mono, SAMPLE_RATE // divisor, int(rate) // divisor)
    return np.asarray(mono, dtype=np.float32)


def split_windows(
    audio: npt.NDArray[np.float32],
    *,
    window_s: float = WINDOW_S,
    max_windows: int = MAX_WINDOWS,
    min_tail_s: float = MIN_TAIL_S,
) -> list[npt.NDArray[np.float32]]:
    """Non-overlapping windows of at most `window_s`; a short trailing window is dropped."""
    if audio.size == 0:
        raise AudioDecodeError("audio is empty")
    size = int(window_s * SAMPLE_RATE)
    windows = [audio[i : i + size] for i in range(0, audio.size, size)][:max_windows]
    if len(windows) > 1 and windows[-1].size < int(min_tail_s * SAMPLE_RATE):
        windows = windows[:-1]
    return windows


class ClapEncoder:
    """Hugging Face `transformers` CLAP model behind the domain encoder protocols."""

    def __init__(
        self,
        checkpoint_dir: Path,
        model_id: str,
        *,
        batch_size: int = 8,
        num_threads: int | None = None,
    ) -> None:
        self._dir = checkpoint_dir
        self._model_id = model_id
        self._batch_size = batch_size
        self._num_threads = num_threads
        self._model: Any = None
        self._processor: Any = None
        self._dim: int | None = None
        self._lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def embedding_dim(self) -> int:
        self._load()
        assert self._dim is not None
        return self._dim

    def preprocessing(self) -> dict[str, Any]:
        """Everything that changes the meaning of an embedding (feeds `embedding_version`)."""
        return {
            "sample_rate": SAMPLE_RATE,
            "window_s": WINDOW_S,
            "max_windows": MAX_WINDOWS,
            "min_tail_s": MIN_TAIL_S,
            "pooling": "mean_then_l2",
            "resampler": "scipy.signal.resample_poly",
            "channels": "mean_downmix",
            "transformers": version("transformers"),
        }

    def _load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import ClapModel, ClapProcessor

                if self._num_threads:
                    torch.set_num_threads(self._num_threads)
                model: Any = ClapModel.from_pretrained(self._dir, local_files_only=True)
                model.eval()
                processor: Any = ClapProcessor.from_pretrained(self._dir, local_files_only=True)
            except (OSError, ValueError, ImportError, RuntimeError) as exc:
                raise ModelLoadError(
                    f"cannot load CLAP checkpoint from {self._dir}",
                    details={"checkpoint": str(self._dir), "model_id": self._model_id},
                ) from exc
            self._dim = int(model.config.projection_dim)
            self._processor = processor
            self._model = model
            log.info("loaded CLAP model %s from %s", self._model_id, self._dir)

    def encode_texts(self, texts: Sequence[str]) -> Matrix:
        self._load()
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        import torch

        rows: list[npt.NDArray[np.float32]] = []
        with torch.inference_mode():
            for start in range(0, len(texts), self._batch_size):
                batch = list(texts[start : start + self._batch_size])
                inputs = self._processor.tokenizer(batch, padding=True, return_tensors="pt")
                output = self._model.get_text_features(**inputs)
                rows.append(_features(output))
        return l2_normalize(np.concatenate(rows))

    def encode_audio(self, paths: Sequence[Path]) -> Matrix:
        """One embedding per file. Raises on the first file that cannot be read."""
        if not paths:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        return np.stack([self.encode_audio_file(p) for p in paths])

    def encode_audio_file(self, path: Path) -> Vector:
        return self.encode_waveform(load_mono_48k(path))

    def encode_waveform(self, audio: npt.NDArray[np.float32]) -> Vector:
        """Embed a mono 48 kHz waveform via fixed windows and mean pooling."""
        self._load()
        import torch

        windows = split_windows(audio)
        with torch.inference_mode():
            inputs = self._processor.feature_extractor(
                windows, sampling_rate=SAMPLE_RATE, return_tensors="pt"
            )
            window_vectors = l2_normalize(_features(self._model.get_audio_features(**inputs)))
        return l2_normalize(window_vectors.mean(axis=0))


def _features(output: Any) -> npt.NDArray[np.float32]:
    """Projected embeddings from a `get_*_features` call (tensor or model output)."""
    tensor = output if hasattr(output, "detach") else output.pooler_output
    return np.asarray(tensor.detach().cpu().numpy(), dtype=np.float32)
