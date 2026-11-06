from dataclasses import dataclass

import numpy as np
import soundfile as sf
from config.settings import load_settings
from src.experiments.config import ExperimentConfig
from src.experiments.runner import run_experiment
from src.models.registry import Transcription
from src.storage.db import Store


@dataclass
class FakeAdapter:
    model_id: str
    calls: list

    def ensure_loaded(self):
        return None

    def transcribe(self, audio, sample_rate, language):
        self.calls.append(language)
        return Transcription("hello", 0.01, "cpu", None, "fake")

    def unload(self):
        return None

    @property
    def spec(self):
        return type("Spec", (), {"model_id": self.model_id})()


def test_run_persists_and_skips_completed_rows(tmp_path):
    wav = tmp_path / "a.wav"
    sf.write(wav, np.ones(1600, dtype=np.float32) * 0.1, 16000)
    settings = load_settings()
    settings.ensure_dirs()
    store = Store(settings.db_path)
    store.init()
    config = ExperimentConfig(
        name="check",
        dataset_id="custom",
        language="hi",
        limit=1,
        models=["whisper-small"],
        conditions=["clean"],
        snr_levels=[],
        speed_factors=[],
        manifest_path=str(tmp_path / "m.csv"),
        audio_dir=str(tmp_path),
    )
    (tmp_path / "m.csv").write_text(
        f"sample_id,audio_path,reference,language\ns1,{wav.name},hello there,hi\n",
        encoding="utf-8",
    )
    experiment_id = store.create(config)
    calls = []
    run_experiment(
        store,
        experiment_id,
        settings,
        adapter_factory=lambda model_id: FakeAdapter(model_id, calls),
    )
    finished = store.get(experiment_id)
    assert finished["status"] == "completed"
    rows = store.list_predictions(experiment_id)
    assert rows[0]["prediction"] == "hello"
    assert rows[0]["wer"] is not None
    again = Store(settings.db_path)
    assert again.get(experiment_id)["status"] == "completed"
    run_experiment(
        store,
        experiment_id,
        settings,
        adapter_factory=lambda model_id: FakeAdapter(model_id, calls),
    )
    assert len(calls) == 1


def test_model_load_failure_is_stored(tmp_path):
    wav = tmp_path / "a.wav"
    sf.write(wav, np.ones(1600, dtype=np.float32) * 0.1, 16000)
    settings = load_settings()
    settings.ensure_dirs()
    store = Store(settings.db_path)
    store.init()
    manifest = tmp_path / "m.csv"
    manifest.write_text(
        f"sample_id,audio_path,reference,language\ns1,{wav.name},hello,hi\n",
        encoding="utf-8",
    )
    config = ExperimentConfig(
        name="fail",
        dataset_id="custom",
        language="hi",
        limit=1,
        models=["whisper-small"],
        conditions=["clean"],
        snr_levels=[],
        speed_factors=[],
        manifest_path=str(manifest),
        audio_dir=str(tmp_path),
    )
    experiment_id = store.create(config)

    class Broken:
        spec = type("Spec", (), {"model_id": "whisper-small"})()

        def ensure_loaded(self):
            raise RuntimeError("weights missing")

        def unload(self):
            return None

    run_experiment(store, experiment_id, settings, adapter_factory=lambda _model: Broken())
    finished = store.get(experiment_id)
    assert finished["status"] == "failed"
    assert "weights missing" in finished["error"]
    assert store.list_predictions(experiment_id)[0]["error"]
