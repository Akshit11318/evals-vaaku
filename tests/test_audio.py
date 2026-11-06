import numpy as np
import soundfile as sf
from src.audio.io import load_mono
from src.audio.perturb import apply_transform


def test_noise_keeps_the_original_file(tmp_path):
    path = tmp_path / "clean.wav"
    tone = np.linspace(-0.2, 0.2, 16000, dtype=np.float32)
    sf.write(path, tone, 16000)
    before = path.read_bytes()
    audio, sample_rate, duration = load_mono(path)
    noisy = apply_transform(audio, sample_rate, {"type": "noise", "snr_db": 5}, seed=3)
    assert path.read_bytes() == before
    assert not np.allclose(audio, noisy)
    assert duration > 0.9


def test_speed_changes_length():
    audio = np.zeros(16000, dtype=np.float32)
    audio[1000:2000] = 0.2
    faster = apply_transform(audio, 16000, {"type": "speed", "rate": 1.2}, seed=1)
    assert len(faster) < len(audio)
