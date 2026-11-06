"""Micro-averaged scores from stored prediction rows."""

from __future__ import annotations

from collections import defaultdict


def pack_results(rows: list[dict]) -> dict:
    measured = [row for row in rows if not row.get("error") and row.get("wer") is not None]
    return {
        "rows": rows,
        "by_model": _groups(measured, ("model_id",)),
        "by_language": _groups(measured, ("model_id", "language")),
        "by_dataset": _groups(measured, ("model_id", "dataset")),
        "by_condition": _groups(measured, ("model_id", "audio_condition")),
        "entities": _entities(measured),
    }


def _groups(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[tuple(row.get(key) for key in keys)].append(row)
    grouped = []
    for key, items in buckets.items():
        record = {name: value for name, value in zip(keys, key, strict=True)}
        record.update(_rates(items))
        grouped.append(record)
    return sorted(grouped, key=lambda item: (item.get("wer") is None, item.get("wer") or 0))


def _rates(items: list[dict]) -> dict:
    ref_words = sum(int(item.get("ref_words") or 0) for item in items)
    word_errors = sum(
        int(item.get("substitutions") or 0)
        + int(item.get("deletions") or 0)
        + int(item.get("insertions") or 0)
        for item in items
    )
    ref_chars = sum(int(item.get("ref_chars") or 0) for item in items)
    char_errors = sum(int(item.get("char_errors") or 0) for item in items)
    sentences = len(items)
    sentence_errors = sum(int(item.get("ser") or 0) for item in items)
    latencies = [
        float(item["inference_time_s"])
        for item in items
        if item.get("inference_time_s") is not None
    ]
    rtfs = [float(item["rtf"]) for item in items if item.get("rtf") is not None]
    peaks = [float(item["peak_gpu_mb"]) for item in items if item.get("peak_gpu_mb") is not None]
    return {
        "samples": sentences,
        "wer": None if ref_words == 0 else word_errors / ref_words,
        "cer": None if ref_chars == 0 else char_errors / ref_chars,
        "ser": None if sentences == 0 else sentence_errors / sentences,
        "substitutions": sum(int(item.get("substitutions") or 0) for item in items),
        "deletions": sum(int(item.get("deletions") or 0) for item in items),
        "insertions": sum(int(item.get("insertions") or 0) for item in items),
        "latency_s": None if not latencies else sum(latencies) / len(latencies),
        "rtf": None if not rtfs else sum(rtfs) / len(rtfs),
        "peak_gpu_mb": None if not peaks else max(peaks),
    }


def _entities(rows: list[dict]) -> dict:
    summary = {}
    for kind in ("phone", "time", "date", "name", "address"):
        applicable = []
        for row in rows:
            payload = (row.get("entity") or {}).get(kind) or {}
            if payload.get("applicable"):
                applicable.append(payload)
        if kind == "phone":
            summary[kind] = {
                "applicable": len(applicable),
                "exact_rate": _mean_flag(applicable, "exact"),
                "digit_accuracy": _mean_number(applicable, "digit_accuracy"),
            }
        else:
            summary[kind] = {
                "applicable": len(applicable),
                "exact_rate": _mean_flag(applicable, "exact"),
            }
    mixes = []
    for row in rows:
        payload = (row.get("entity") or {}).get("code_mix") or {}
        if payload.get("applicable"):
            mixes.append(payload)
    summary["code_mix"] = {
        "applicable": len(mixes),
        "latin_wer": _mean_number(mixes, "latin_wer"),
        "indic_wer": _mean_number(mixes, "indic_wer"),
    }
    return summary


def _mean_flag(items: list[dict], key: str) -> float | None:
    if not items:
        return None
    return sum(1 for item in items if item.get(key)) / len(items)


def _mean_number(items: list[dict], key: str) -> float | None:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)
