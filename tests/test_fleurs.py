import io

import numpy as np
import soundfile as sf
from src.audio.io import load_mono
from src.datasets.fleurs import _row_to_sample
from src.errors import DatasetError


def test_fleurs_row_saves_wav_bytes_without_torchcodec(tmp_path):
    buffer = io.BytesIO()
    tone = np.linspace(-0.2, 0.2, 1600, dtype=np.float32)
    sf.write(buffer, tone, 16000, format="WAV")
    sample = _row_to_sample(
        {
            "id": 7,
            "transcription": "नमस्ते",
            "audio": {"bytes": buffer.getvalue(), "path": "7.wav"},
        },
        "hi",
        tmp_path,
    )
    saved, sample_rate, _duration = load_mono(tmp_path / "7.wav")
    assert sample.sample_id == "7"
    assert sample.reference == "नमस्ते"
    assert sample_rate == 16000
    assert saved.shape == tone.shape


def test_repeated_fleurs_ids_stay_separate_clips(tmp_path):
    def wav_bytes():
        buffer = io.BytesIO()
        sf.write(buffer, np.zeros(800, dtype=np.float32), 16000, format="WAV")
        return buffer.getvalue()

    first = _row_to_sample(
        {"id": 1, "transcription": "एक", "audio": {"bytes": wav_bytes(), "path": "111.wav"}},
        "hi",
        tmp_path,
    )
    second = _row_to_sample(
        {"id": 1, "transcription": "दो", "audio": {"bytes": wav_bytes(), "path": "222.wav"}},
        "hi",
        tmp_path,
    )
    assert first.sample_id == "111"
    assert second.sample_id == "222"
    assert first.audio_path != second.audio_path


def test_fleurs_row_rejects_missing_audio(tmp_path):
    try:
        _row_to_sample(
            {"id": 8, "transcription": "hello", "audio": {"bytes": None, "path": None}},
            "hi",
            tmp_path,
        )
    except DatasetError as exc:
        assert "no audio bytes" in str(exc)
    else:
        raise AssertionError("expected a dataset error")
