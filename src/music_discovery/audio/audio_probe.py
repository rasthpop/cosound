"""Decodability check for local audio files (implements `domain.protocols.AudioProbe`)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from music_discovery.domain.schemas import AudioProbeResult


class SoundfileProbe:
    """Opens the file with libsndfile (WAV, FLAC, OGG, MP3), reads the start and checks it.

    A file is usable when it exists, decodes, is at least `min_duration_s` long and is not
    digital silence. A few FMA clips are known to be truncated or corrupt.
    """

    def __init__(
        self, *, min_duration_s: float = 5.0, read_seconds: float = 30.0, silence_rms: float = 1e-4
    ) -> None:
        self._min_duration = min_duration_s
        self._read_seconds = read_seconds
        self._silence_rms = silence_rms

    def probe(self, path: Path) -> AudioProbeResult:
        if not path.is_file():
            return AudioProbeResult(ok=False, error_code="audio_missing")
        if path.stat().st_size == 0:
            return AudioProbeResult(ok=False, error_code="audio_empty")
        try:
            info = sf.info(str(path))
            frames = int(min(info.frames, info.samplerate * self._read_seconds))
            data, _ = sf.read(str(path), frames=frames, dtype="float32", always_2d=True)
        except (sf.LibsndfileError, RuntimeError, ValueError):
            return AudioProbeResult(ok=False, error_code="audio_decode_error")
        duration = info.frames / info.samplerate if info.samplerate else 0.0
        if duration < self._min_duration:
            return AudioProbeResult(
                ok=False,
                error_code="audio_too_short",
                duration_seconds=duration,
                sample_rate=info.samplerate or None,
            )
        rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
        if rms < self._silence_rms:
            return AudioProbeResult(
                ok=False,
                error_code="audio_silent",
                duration_seconds=duration,
                sample_rate=info.samplerate,
            )
        return AudioProbeResult(ok=True, duration_seconds=duration, sample_rate=info.samplerate)
