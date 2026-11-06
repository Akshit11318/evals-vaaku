"""Score one sample at a time. A model failure does not erase other models."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import Settings

from src.audio.io import load_mono, validate_audio_file
from src.audio.perturb import materialize, stable_seed
from src.datasets.catalog import load_samples
from src.errors import DatasetError
from src.evaluation.aggregate import pack_results
from src.evaluation.entities import evaluate_entities
from src.evaluation.metrics import score_pair
from src.experiments.config import ExperimentConfig
from src.experiments.validate import expand_conditions
from src.models.registry import build_adapter
from src.redact import scrub
from src.storage.db import Store, utcnow

LOGGER = logging.getLogger("vaku.runner")


def run_experiment(
    store: Store,
    experiment_id: str,
    settings: Settings,
    adapter_factory=build_adapter,
) -> None:
    experiment = store.get(experiment_id)
    if experiment is None:
        raise DatasetError(f"Run {experiment_id} does not exist.")
    config = ExperimentConfig.from_dict(experiment["config"])
    store.set_runtime(experiment_id, status="running", started_at=utcnow(), error=None)
    failures = 0
    load_errors: list[str] = []
    try:
        samples, note = load_samples(config.dataset_id, settings, config)
        problems = _validate_samples(samples)
        if problems:
            raise DatasetError("Audio check failed:\n" + "\n".join(problems[:30]))
        conditions = expand_conditions(config)
        total = len(samples) * len(config.models) * len(conditions)
        store.set_runtime(experiment_id, progress_total=total, note=note)
        done = 0
        for model_id in config.models:
            try:
                adapter = adapter_factory(model_id)
                adapter.ensure_loaded()
            except Exception as exc:
                message = scrub(f"{model_id} failed to load: {exc}")
                load_errors.append(message)
                LOGGER.exception("model load failed: %s", model_id)
                for sample in samples:
                    for condition in conditions:
                        _record_failure(
                            store,
                            experiment_id,
                            sample,
                            model_id,
                            condition,
                            message,
                            settings,
                        )
                        failures += 1
                        done += 1
                        store.set_runtime(
                            experiment_id,
                            progress_current=done,
                            current_model=model_id,
                            current_sample=sample.sample_id,
                        )
                continue
            try:
                for sample in samples:
                    for condition in conditions:
                        if store.has_prediction(
                            experiment_id, sample.sample_id, model_id, condition["condition"]
                        ):
                            done += 1
                            store.set_runtime(experiment_id, progress_current=done)
                            continue
                        store.set_runtime(
                            experiment_id,
                            current_model=model_id,
                            current_sample=f"{sample.sample_id} · {condition['condition']}",
                        )
                        try:
                            _score_one(
                                store,
                                settings,
                                experiment_id,
                                adapter,
                                sample,
                                condition,
                                config,
                            )
                        except Exception as exc:
                            LOGGER.exception(
                                "sample failed experiment=%s model=%s sample=%s",
                                experiment_id,
                                model_id,
                                sample.sample_id,
                            )
                            _record_failure(
                                store,
                                experiment_id,
                                sample,
                                model_id,
                                condition,
                                scrub(str(exc)),
                                settings,
                            )
                            failures += 1
                        done += 1
                        store.set_runtime(experiment_id, progress_current=done)
            finally:
                adapter.unload()
        rows = store.list_predictions(experiment_id)
        payload = pack_results(rows)
        store.save_metrics(
            experiment_id, {key: value for key, value in payload.items() if key != "rows"}
        )
        if not store.any_success(experiment_id):
            store.set_runtime(
                experiment_id,
                status="failed",
                finished_at=utcnow(),
                error=scrub("; ".join(load_errors) or "Every sample failed."),
                current_model=None,
                current_sample=None,
            )
            return
        warning = None
        if load_errors:
            warning = "; ".join(load_errors)
        elif failures:
            warning = f"{failures} sample rows failed. The rest were scored."
        store.set_runtime(
            experiment_id,
            status="completed",
            finished_at=utcnow(),
            error=warning,
            current_model=None,
            current_sample=None,
        )
    except Exception as exc:
        LOGGER.exception("experiment failed: %s", experiment_id)
        store.set_runtime(
            experiment_id,
            status="failed",
            finished_at=utcnow(),
            error=scrub(str(exc)),
            current_model=None,
            current_sample=None,
        )


def _validate_samples(samples) -> list[str]:
    problems = []
    for sample in samples:
        if not str(sample.reference or "").strip():
            problems.append(f"{sample.sample_id}: empty reference")
        problems.extend(validate_audio_file(Path(sample.audio_path), sample.sample_id))
    return problems


def _score_one(store, settings, experiment_id, adapter, sample, condition, config) -> None:
    seed = stable_seed(config.seed, sample.sample_id, condition["condition"])
    dest = (
        settings.output_dir
        / "audio"
        / experiment_id
        / f"{sample.sample_id}_{condition['condition']}.wav"
    )
    audio_path = materialize(
        Path(sample.audio_path),
        dest,
        condition["parameters"],
        seed,
        settings.sample_rate,
    )
    audio, sample_rate, duration = load_mono(audio_path, settings.sample_rate)
    result = adapter.transcribe(audio, sample_rate, sample.language)
    scores = score_pair(sample.reference, result.text)
    entities = evaluate_entities(sample.reference, result.text, sample.metadata)
    rtf = None if duration <= 0 else result.inference_time_s / duration
    store.insert_prediction(
        _row(
            experiment_id,
            sample,
            adapter.spec.model_id,
            result.model_version,
            result.device,
            result.text,
            condition,
            seed,
            str(audio_path),
            scores,
            entities,
            result.inference_time_s,
            duration,
            rtf,
            result.peak_gpu_mb,
            None,
            result.notes,
        )
    )


def _record_failure(store, experiment_id, sample, model_id, condition, message, settings) -> None:
    if store.has_prediction(experiment_id, sample.sample_id, model_id, condition["condition"]):
        return
    store.insert_prediction(
        _row(
            experiment_id,
            sample,
            model_id,
            None,
            None,
            None,
            condition,
            None,
            sample.audio_path,
            {},
            {},
            None,
            None,
            None,
            None,
            message,
            None,
        )
    )


def _row(
    experiment_id,
    sample,
    model_id,
    model_version,
    device,
    prediction,
    condition,
    seed,
    audio_path,
    scores,
    entities,
    inference_time_s,
    duration,
    rtf,
    peak_gpu_mb,
    error,
    notes,
) -> dict:
    return {
        "experiment_id": experiment_id,
        "sample_id": sample.sample_id,
        "dataset": sample.dataset,
        "language": sample.language,
        "model_id": model_id,
        "model_version": model_version,
        "device": device,
        "reference": sample.reference,
        "prediction": prediction,
        "audio_condition": condition["condition"],
        "transform_json": json.dumps({"parameters": condition["parameters"], "seed": seed}),
        "seed": seed,
        "audio_path": audio_path,
        "wer_raw": scores.get("wer_raw"),
        "cer_raw": scores.get("cer_raw"),
        "wer": scores.get("wer"),
        "cer": scores.get("cer"),
        "ser": scores.get("ser"),
        "substitutions": scores.get("substitutions"),
        "deletions": scores.get("deletions"),
        "insertions": scores.get("insertions"),
        "ref_words": scores.get("ref_words"),
        "ref_chars": scores.get("ref_chars"),
        "char_errors": scores.get("char_errors"),
        "inference_time_s": inference_time_s,
        "audio_duration_s": duration,
        "rtf": rtf,
        "peak_gpu_mb": peak_gpu_mb,
        "entity_json": json.dumps(entities),
        "alignment_json": json.dumps(scores.get("alignment") or []),
        "error": error,
        "notes": notes,
        "created_at": utcnow(),
    }
