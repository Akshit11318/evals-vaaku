"""Reject a run before any model is loaded."""

from __future__ import annotations

import shutil
from pathlib import Path

from config.settings import Settings

from src.datasets.catalog import list_datasets
from src.experiments.config import ExperimentConfig
from src.models.registry import MODEL_SPECS

ALLOWED_CONDITIONS = {"clean", "noise", "speed", "volume", "reverb", "mp3"}
ALLOWED_SNR = {20, 10, 5}
ALLOWED_SPEED = {0.8, 1.2}


def validate_config(config: ExperimentConfig, settings: Settings) -> list[str]:
    errors: list[str] = []
    if not config.name.strip():
        errors.append("Give the run a name.")
    cards = {card.dataset_id: card for card in list_datasets(settings)}
    card = cards.get(config.dataset_id)
    if card is None or not card.selectable:
        reason = card.reason if card else "Unknown dataset."
        errors.append(f"{config.dataset_id} cannot be selected. {reason}")
    elif config.language not in card.languages:
        errors.append(f"{card.name} does not include {config.language}.")
    if config.dataset_id == "custom":
        if not config.manifest_path or not Path(config.manifest_path).is_file():
            errors.append("Custom manifest path is missing.")
        if not config.audio_dir or not Path(config.audio_dir).is_dir():
            errors.append("Custom audio directory is missing.")
    if config.split not in {"test", "validation"}:
        errors.append("Use the test or validation split.")
    if config.limit < 1 or config.limit > settings.max_samples:
        errors.append(f"Sample limit must be between 1 and {settings.max_samples}.")
    if not config.models:
        errors.append("Select at least one model.")
    unknown = [model for model in config.models if model not in MODEL_SPECS]
    if unknown:
        errors.append(f"Unknown model: {', '.join(unknown)}.")
    if len(set(config.models)) != len(config.models):
        errors.append("A model is selected twice.")
    unsupported = [
        model
        for model in config.models
        if model in MODEL_SPECS and config.language not in MODEL_SPECS[model].languages
    ]
    if unsupported:
        errors.append(
            f"{', '.join(unsupported)} does not support {config.language}. "
            "No other model will be substituted."
        )
    if not config.conditions:
        errors.append("Select at least one audio condition.")
    odd = [item for item in config.conditions if item not in ALLOWED_CONDITIONS]
    if odd:
        errors.append(f"Unknown audio condition: {', '.join(odd)}.")
    if "noise" in config.conditions:
        bad_snr = [level for level in config.snr_levels if level not in ALLOWED_SNR]
        if not config.snr_levels or bad_snr:
            errors.append("Noise uses SNR 20, 10, and 5 dB only.")
    if "speed" in config.conditions:
        bad_speed = [rate for rate in config.speed_factors if rate not in ALLOWED_SPEED]
        if not config.speed_factors or bad_speed:
            errors.append("Speed uses 0.8x and 1.2x only.")
    if config.batch_size < 1 or config.batch_size > 64:
        errors.append("Batch size must be from 1 to 64.")
    if config.volume_db < -24 or config.volume_db > 12:
        errors.append("Volume must be between -24 dB and 12 dB.")
    if config.reverb_decay < 0.1 or config.reverb_decay > 0.9:
        errors.append("Reverb decay must be between 0.1 and 0.9.")
    if config.mp3_bitrate not in {32, 64, 96, 128}:
        errors.append("MP3 bitrate must be 32, 64, 96, or 128.")
    if "mp3" in config.conditions and shutil.which("ffmpeg") is None:
        errors.append("MP3 compression needs ffmpeg on PATH.")
    return errors


def expand_conditions(config: ExperimentConfig) -> list[dict]:
    items: list[dict] = []
    for name in config.conditions:
        if name == "clean":
            items.append({"condition": "clean", "parameters": {"type": "clean"}})
        elif name == "noise":
            for snr in config.snr_levels:
                items.append(
                    {
                        "condition": f"noise_snr_{snr}",
                        "parameters": {"type": "noise", "snr_db": snr},
                    }
                )
        elif name == "speed":
            for rate in config.speed_factors:
                items.append(
                    {"condition": f"speed_{rate}", "parameters": {"type": "speed", "rate": rate}}
                )
        elif name == "volume":
            items.append(
                {
                    "condition": "volume",
                    "parameters": {"type": "volume", "gain_db": config.volume_db},
                }
            )
        elif name == "reverb":
            items.append(
                {
                    "condition": "reverb",
                    "parameters": {"type": "reverb", "decay": config.reverb_decay},
                }
            )
        elif name == "mp3":
            items.append(
                {"condition": "mp3", "parameters": {"type": "mp3", "bitrate": config.mp3_bitrate}}
            )
    return items
