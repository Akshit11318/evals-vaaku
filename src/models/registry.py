"""The models the bench can score. Weights load only when a run asks for them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transcription:
    text: str
    inference_time_s: float
    device: str
    peak_gpu_mb: float | None
    model_version: str
    notes: str = ""


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    hf_id: str
    family: str
    languages: frozenset[str]
    min_free_mb: int
    license_name: str
    note: str
    adapter_id: str | None = None


WHISPER_LANGUAGES = frozenset({"te", "ta", "hi", "kn", "ml", "en"})
INDIC_LANGUAGES = frozenset(
    {
        "as",
        "bn",
        "brx",
        "doi",
        "gu",
        "hi",
        "kn",
        "kok",
        "ks",
        "mai",
        "ml",
        "mni",
        "mr",
        "ne",
        "or",
        "pa",
        "sa",
        "sat",
        "sd",
        "ta",
        "te",
        "ur",
    }
)
MMS_LANGUAGES = frozenset({"te", "ta", "hi", "kn", "ml", "en"})

MODEL_SPECS: dict[str, ModelSpec] = {
    "whisper-small": ModelSpec(
        model_id="whisper-small",
        display_name="Whisper Small",
        hf_id="openai/whisper-small",
        family="whisper",
        languages=WHISPER_LANGUAGES,
        min_free_mb=1200,
        license_name="Apache-2.0",
        note="Multilingual Whisper. Target languages te, ta, hi, kn, ml are in the official language list. English is included for the pipeline demo only.",
    ),
    "whisper-medium": ModelSpec(
        model_id="whisper-medium",
        display_name="Whisper Medium",
        hf_id="openai/whisper-medium",
        family="whisper",
        languages=WHISPER_LANGUAGES,
        min_free_mb=3500,
        license_name="Apache-2.0",
        note="Same language list as Whisper Small. Needs more GPU memory. It is not loaded unless this run selects it.",
    ),
    "vaakku": ModelSpec(
        model_id="vaakku",
        display_name="Vaakku",
        hf_id="openai/whisper-small",
        family="whisper",
        languages=frozenset({"te", "ta", "hi", "kn", "ml"}),
        min_free_mb=1500,
        license_name="Apache-2.0",
        note="LoRA on Whisper Small for te, ta, hi, kn, ml. English is not in this adapter.",
        adapter_id="rudra11/vaakku-whisper-small",
    ),
    "mms": ModelSpec(
        model_id="mms",
        display_name="Meta MMS",
        hf_id="facebook/mms-1b-all",
        family="mms",
        languages=MMS_LANGUAGES,
        min_free_mb=4500,
        license_name="CC-BY-NC 4.0",
        note="Independent third system. Adapter codes: tel, tam, hin, kan, mal. CC-BY-NC applies to the weights.",
    ),
}


def build_adapter(model_id: str):
    spec = MODEL_SPECS.get(model_id)
    if spec is None:
        raise KeyError(f"Unknown model '{model_id}'.")
    if spec.family == "whisper":
        from src.models.whisper_adapter import WhisperAdapter

        return WhisperAdapter(spec)
    if spec.family == "indic-conformer":
        from src.models.indic_conformer import IndicConformerAdapter

        return IndicConformerAdapter(spec)
    if spec.family == "mms":
        from src.models.mms_adapter import MmsAdapter

        return MmsAdapter(spec)
    raise KeyError(model_id)
