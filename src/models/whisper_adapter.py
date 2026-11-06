"""OpenAI Whisper Small and Whisper Medium behind one adapter."""

from __future__ import annotations

import gc
import time

from src.errors import UnsupportedLanguage
from src.languages import WHISPER_NAMES
from src.models.registry import ModelSpec, Transcription


class WhisperAdapter:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self.model = None
        self.processor = None
        self.device = "cpu"
        self.dtype = None
        self.model_version = spec.hf_id
        self.peak_gpu_mb: float | None = None
        self.load_note = ""

    def ensure_loaded(self) -> None:
        if self.model is not None:
            return
        import torch
        from config.settings import load_settings
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        from src.models.device import select_device
        from src.system.gpu import gpu_status

        self.device, self.load_note = select_device(self.spec, load_settings(), gpu_status())
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        # The adapter repo stores extra_special_tokens as a list. Current
        # transformers expects a dict there, so the processor comes from the base model.
        self.processor = AutoProcessor.from_pretrained(self.spec.hf_id)
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.spec.hf_id,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
        )
        if self.spec.adapter_id:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, self.spec.adapter_id)
        self.model.to(self.device)
        self.model.eval()
        import transformers

        adapter = f" adapter={self.spec.adapter_id}" if self.spec.adapter_id else ""
        self.model_version = f"{self.spec.hf_id}{adapter} transformers={transformers.__version__} device={self.device}"

    def transcribe(self, audio, sample_rate: int, language: str) -> Transcription:
        self._require_language(language)
        self.ensure_loaded()
        import torch

        audio = _resample(audio, sample_rate)
        language_name = WHISPER_NAMES.get(language, language)
        inputs = self.processor(audio, sampling_rate=16_000, return_tensors="pt")
        features = inputs.input_features.to(self.device, dtype=self.dtype)
        prompt = self.processor.get_decoder_prompt_ids(language=language_name, task="transcribe")
        started = time.perf_counter()
        with torch.inference_mode():
            if self.device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            generated = self.model.generate(
                input_features=features,
                forced_decoder_ids=prompt,
                max_new_tokens=225,
            )
            if self.device == "cuda":
                self.peak_gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        elapsed = time.perf_counter() - started
        text = self.processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
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
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return

    def _require_language(self, language: str) -> None:
        if language not in self.spec.languages:
            raise UnsupportedLanguage(
                f"{self.spec.display_name} does not support '{language}'. "
                "No substitute model was used."
            )


def _resample(audio, sample_rate: int):
    if sample_rate == 16_000:
        return audio
    import librosa

    return librosa.resample(audio, orig_sr=sample_rate, target_sr=16_000)
