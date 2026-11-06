import numpy as np
import soundfile as sf
from src.datasets.manifest import load_manifest
from src.errors import DatasetError


def test_manifest_requires_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("sample_id,audio_path\n1,a.wav\n", encoding="utf-8")
    try:
        load_manifest(path, tmp_path, "hi", 5)
    except DatasetError as exc:
        assert "reference" in str(exc)
    else:
        raise AssertionError("expected a manifest error")


def test_manifest_reads_audio(tmp_path):
    wav = tmp_path / "a.wav"
    sf.write(wav, np.zeros(1600, dtype=np.float32), 16000)
    manifest = tmp_path / "set.csv"
    manifest.write_text(
        "sample_id,audio_path,reference,language,speaker_id\ns1,a.wav,नमस्ते,hindi,speaker-a\n",
        encoding="utf-8",
    )
    samples = load_manifest(manifest, tmp_path, "hi", 5)
    assert len(samples) == 1
    assert samples[0].language == "hi"
    assert samples[0].reference == "नमस्ते"
