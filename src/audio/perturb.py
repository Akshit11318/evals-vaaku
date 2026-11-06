"""One transformation at a time. The source file is never overwritten."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

from src.audio.io import write_wav


def stable_seed(base_seed: int, sample_id: str, condition: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{sample_id}:{condition}".encode()).hexdigest()
    return int(digest[:8], 16)


def apply_transform(audio: np.ndarray, sample_rate: int, parameters: dict, seed: int) -> np.ndarray:
    kind = parameters.get("type", "clean")
    source = np.asarray(audio, dtype=np.float32).copy()
    if kind == "clean":
        return source
    if kind == "noise":
        return _noise(source, float(parameters["snr_db"]), seed)
    if kind == "speed":
        return _speed(source, float(parameters["rate"]))
    if kind == "volume":
        return _volume(source, sample_rate, float(parameters["gain_db"]))
    if kind == "reverb":
        return _reverb(source, sample_rate, float(parameters.get("decay", 0.45)))
    if kind == "mp3":
        return _mp3(source, sample_rate, int(parameters.get("bitrate", 64)), seed)
    raise ValueError(f"Unknown transformation '{kind}'.")


def materialize(
    source_path: Path,
    dest: Path,
    parameters: dict,
    seed: int,
    sample_rate: int,
) -> Path:
    """Write a transformed copy. A clean condition returns the original path."""
    if parameters.get("type", "clean") == "clean":
        return source_path
    if dest.exists():
        return dest
    from src.audio.io import load_mono

    audio, sr, _duration = load_mono(source_path, sample_rate)
    transformed = apply_transform(audio, sr, parameters, seed)
    write_wav(dest, transformed, sr)
    return dest


def _noise(audio: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    signal_power = float(np.mean(np.square(audio)) + 1e-12)
    noise = rng.normal(0.0, 1.0, size=audio.shape).astype(np.float32)
    noise_power = float(np.mean(np.square(noise)) + 1e-12)
    target = signal_power / (10 ** (snr_db / 10))
    mixed = audio + noise * np.sqrt(target / noise_power)
    return np.clip(mixed, -1.0, 1.0).astype(np.float32)


def _speed(audio: np.ndarray, rate: float) -> np.ndarray:
    import librosa

    stretched = librosa.effects.time_stretch(np.asarray(audio, dtype=np.float32), rate=rate)
    return stretched.astype(np.float32)


def _volume(audio: np.ndarray, sample_rate: int, gain_db: float) -> np.ndarray:
    from audiomentations import Gain

    transform = Gain(min_gain_db=gain_db, max_gain_db=gain_db, p=1.0)
    transformed = transform(np.asarray(audio, dtype=np.float32), sample_rate=sample_rate)
    return np.clip(transformed, -1.0, 1.0).astype(np.float32)


def _reverb(audio: np.ndarray, sample_rate: int, decay: float) -> np.ndarray:
    impulse = np.zeros(int(sample_rate * 0.4), dtype=np.float32)
    impulse[0] = 1.0
    for index, delay in enumerate((0.03, 0.07, 0.13, 0.21)):
        position = int(delay * sample_rate)
        if position < len(impulse):
            impulse[position] = decay * (0.55**index)
    wet = fftconvolve(audio, impulse, mode="full")[: len(audio)]
    peak = float(np.max(np.abs(wet)) + 1e-8)
    return np.clip(wet / max(peak, 1.0), -1.0, 1.0).astype(np.float32)


def _mp3(audio: np.ndarray, sample_rate: int, bitrate: int, seed: int) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is not on PATH, so MP3 compression cannot run.")
    from src.audio.io import write_wav

    folder = Path(tempfile.mkdtemp(prefix=f"vaku-mp3-{seed}-"))
    wav_in = folder / "in.wav"
    mp3_path = folder / "out.mp3"
    wav_out = folder / "out.wav"
    write_wav(wav_in, audio, sample_rate)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(wav_in),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            f"{bitrate}k",
            str(mp3_path),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-i", str(mp3_path), "-ar", str(sample_rate), "-ac", "1", str(wav_out)],
        check=True,
        capture_output=True,
    )
    import soundfile as sf

    decoded, _sr = sf.read(str(wav_out), always_2d=False)
    return np.asarray(decoded, dtype=np.float32)
