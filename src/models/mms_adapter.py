"""Meta MMS-1B-all. A different system from Whisper and IndicConformer."""

from __future__ import annotations

import gc
import time

from src.errors import UnsupportedLanguage
from src.languages import MMS_CODES
from src.models.registry import ModelSpec, Transcription


class MmsAdapter:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self.model = None
        self.processor = None
        self.device = "cpu"
        self.model_version = spec.hf_id
        self.dtype = None
        self.peak_gpu_mb: float | None = None
        self.load_note = ""
        self.loaded_lang: str | None = None

    def ensure_loaded(self) -> None:
        if self.model is not None:
            return
        import torch
        from config.settings import load_settings
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        from src.models.device import select_device
        from src.system.gpu import gpu_status

        self.device, self.load_note = select_device(self.spec, load_settings(), gpu_status())
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.processor = AutoProcessor.from_pretrained(self.spec.hf_id)
        self.model = Wav2Vec2ForCTC.from_pretrained(self.spec.hf_id, torch_dtype=self.dtype)
        self.model.to(self.device)
        self.model.eval()
        import transformers

        self.model_version = (
            f"{self.spec.hf_id} transformers={transformers.__version__} device={self.device}"
        )

    def transcribe(self, audio, sample_rate: int, language: str) -> Transcription:
        if language not in self.spec.languages:
            raise UnsupportedLanguage(
                f"{self.spec.display_name} does not support '{language}'. "
                "No substitute model was used."
            )
        self.ensure_loaded()
        import torch

        code = MMS_CODES[language]
        if self.loaded_lang != code:
            self.processor.tokenizer.set_target_lang(code)
            self.model.load_adapter(code)
            self.model.to(dtype=self.dtype)
            self.loaded_lang = code
        samples = _resample(audio, sample_rate)
        inputs = self.processor(samples, sampling_rate=16_000, return_tensors="pt")
        input_values = inputs.input_values.to(self.device, dtype=self.dtype)
        started = time.perf_counter()
        with torch.inference_mode():
            if self.device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            logits = self.model(input_values).logits
            if self.device == "cuda":
                self.peak_gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        elapsed = time.perf_counter() - started
        ids = torch.argmax(logits, dim=-1)
        text = self.processor.batch_decode(ids)[0].strip()
        return Transcription(
            text=text,
            inference_time_s=elapsed,
            device=self.device,
            peak_gpu_mb=self.peak_gpu_mb,
            model_version=self.model_version,
            notes=self.load_note,
        )

    def unload(self) -> None:
        self.model = None
        self.processor = None
        self.loaded_lang = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return


def _resample(audio, sample_rate: int):
    if sample_rate == 16_000:
        return audio
    import librosa

    return librosa.resample(audio, orig_sr=sample_rate, target_sr=16_000)
