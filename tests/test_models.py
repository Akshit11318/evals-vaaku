import pytest
from config.settings import load_settings
from src.errors import ModelLoadError
from src.models.device import select_device
from src.models.registry import MODEL_SPECS


def test_registry_has_the_speech_models():
    assert set(MODEL_SPECS) == {"whisper-small", "whisper-medium", "vaakku", "mms"}
    for code in ("te", "ta", "hi", "kn", "ml"):
        assert code in MODEL_SPECS["whisper-small"].languages
        assert code in MODEL_SPECS["vaakku"].languages
        assert code in MODEL_SPECS["mms"].languages
    assert MODEL_SPECS["vaakku"].adapter_id == "rudra11/vaakku-whisper-small"
    assert "en" not in MODEL_SPECS["vaakku"].languages


def test_medium_is_not_replaced_when_gpu_is_short(monkeypatch):
    monkeypatch.setenv("ALLOW_CPU_FALLBACK", "0")
    monkeypatch.setenv("PREFER_GPU", "1")
    settings = load_settings()
    gpu = {"available": True, "free_mb": 100, "name": "Test GPU"}
    with pytest.raises(ModelLoadError) as caught:
        select_device(MODEL_SPECS["whisper-medium"], settings, gpu)
    message = str(caught.value)
    assert "whisper-small" not in message
    assert "No other model was substituted." in message
