"""Device choice for one model. A shortfall never swaps in a different model."""

from __future__ import annotations

from config.settings import Settings

from src.errors import ModelLoadError


def memory_floor_mb(spec, settings: Settings) -> int:
    overrides = {
        "whisper-small": settings.whisper_small_min_free_mb,
        "whisper-medium": settings.whisper_medium_min_free_mb,
        "indic-conformer": settings.indic_min_free_mb,
        "mms": settings.mms_min_free_mb,
    }
    return int(overrides.get(spec.model_id, spec.min_free_mb))


def select_device(spec, settings: Settings, gpu: dict) -> tuple[str, str]:
    needed = memory_floor_mb(spec, settings)
    if settings.prefer_gpu and gpu.get("available"):
        free = float(gpu.get("free_mb") or 0)
        if free >= needed:
            name = gpu.get("name") or "CUDA"
            return "cuda", f"Using {name} with {free:.0f} MB free."
        if not settings.allow_cpu_fallback:
            raise ModelLoadError(
                f"{spec.display_name} needs about {needed} MB free GPU memory; "
                f"{free:.0f} MB is free. Refusing to load. Set ALLOW_CPU_FALLBACK=1 to run "
                "this same model on CPU. No other model was substituted."
            )
        return (
            "cpu",
            f"GPU free memory is {free:.0f} MB, below {needed} MB for {spec.model_id}. "
            "ALLOW_CPU_FALLBACK=1, so this model will run on CPU. "
            "No other model was substituted.",
        )
    if settings.prefer_gpu and not gpu.get("available"):
        if not settings.allow_cpu_fallback:
            raise ModelLoadError(
                f"CUDA is not available, so {spec.model_id} was not loaded. "
                "Set ALLOW_CPU_FALLBACK=1 to run this same model on CPU. "
                "No other model was substituted."
            )
        reason = gpu.get("error") or "CUDA is not available"
        return "cpu", f"{reason} ALLOW_CPU_FALLBACK=1, so {spec.model_id} will run on CPU."
    return "cpu", "PREFER_GPU=0, so this model runs on CPU."
