"""Load and check audio. The original file is only read."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def load_mono(path: Path, target_sr: int = 16_000) -> tuple[np.ndarray, int, float]:
    audio, sample_rate = sf.read(str(path), always_2d=False)
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim > 1:
        array = array.mean(axis=1)
    if array.size == 0:
        raise ValueError(f"Empty audio: {path}")
    if sample_rate != target_sr:
        import librosa

        array = librosa.resample(array, orig_sr=sample_rate, target_sr=target_sr).astype(np.float32)
        sample_rate = target_sr
    duration = float(len(array) / sample_rate)
    return array, sample_rate, duration


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.asarray(audio, dtype=np.float32), sample_rate)


def validate_audio_file(path: Path, sample_id: str) -> list[str]:
    if not path.is_file():
        return [f"{sample_id}: missing audio at {path}"]
    try:
        _audio, _sr, duration = load_mono(path)
    except Exception as exc:
        return [f"{sample_id}: unreadable audio ({exc})"]
    if duration < 0.05:
        return [f"{sample_id}: audio is shorter than 50 ms"]
    return []
