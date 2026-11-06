"""AI4Bharat IndicConformer 600M multilingual. RNNT by default, CTC if configured."""

from __future__ import annotations

import gc
import time

import numpy as np

from src.errors import UnsupportedLanguage
from src.models.registry import ModelSpec, Transcription


class IndicConformerAdapter:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self.model = None
        self.device = "cpu"
        self.model_version = spec.hf_id
        self.peak_gpu_mb: float | None = None
        self.load_note = ""
        self.decoder = "rnnt"

    def ensure_loaded(self) -> None:
        if self.model is not None:
            return
        from config.settings import load_settings
        from transformers import AutoModel

        from src.models.device import select_device
        from src.system.gpu import gpu_status

        settings = load_settings()
        self.decoder = (
            settings.indic_decoder if settings.indic_decoder in {"rnnt", "ctc"} else "rnnt"
        )
        self.device, self.load_note = select_device(self.spec, settings, gpu_status())
        self.model = AutoModel.from_pretrained(self.spec.hf_id, trust_remote_code=True)
        if self.device == "cuda":
            try:
                self.model.to(self.device)
            except Exception as exc:
                self.device = "cpu"
                self.load_note = (
                    f"{self.load_note} Could not move IndicConformer to GPU ({exc}). "
                    "Running this same model on CPU."
                )
        self.model.eval()
        import transformers

        self.model_version = (
            f"{self.spec.hf_id} decoder={self.decoder} "
            f"transformers={transformers.__version__} device={self.device}"
        )

    def transcribe(self, audio, sample_rate: int, language: str) -> Transcription:
        if language not in self.spec.languages:
            raise UnsupportedLanguage(
                f"{self.spec.display_name} does not support '{language}'. "
                "No substitute model was used."
            )
        self.ensure_loaded()
        import torch

        waveform = _waveform(audio, sample_rate)
        waveform = waveform.to(self.device)
        started = time.perf_counter()
        with torch.inference_mode():
            if self.device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            text = self.model(waveform, language, self.decoder)
            if self.device == "cuda":
                self.peak_gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        elapsed = time.perf_counter() - started
        if not isinstance(text, str):
            text = str(text)
        return Transcription(
            text=text.strip(),
            inference_time_s=elapsed,
            device=self.device,
            peak_gpu_mb=self.peak_gpu_mb,
            model_version=self.model_version,
            notes=self.load_note,
        )

    def unload(self) -> None:
        self.model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return


def _waveform(audio, sample_rate: int):
    import torch
    import torchaudio

    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    waveform = torch.from_numpy(array)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != 16_000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 16_000)
    return waveform.contiguous()
