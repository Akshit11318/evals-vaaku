"""Bundled English clips. They check the pipeline. They are not an Indic score."""

from __future__ import annotations

import json

from config.settings import Settings

from src.datasets.types import AudioSample
from src.errors import DatasetError
from src.languages import canonicalize


def demo_manifest(settings: Settings):
    return settings.root / "data" / "demo" / "manifest.json"


def load_demo(settings: Settings, language: str, limit: int) -> tuple[list[AudioSample], str]:
    path = demo_manifest(settings)
    if not path.is_file():
        raise DatasetError("The pipeline demo manifest is missing.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    wanted = canonicalize(language)
    samples = []
    root = path.parent
    for row in payload["samples"]:
        if canonicalize(row["language"]) != wanted:
            continue
        samples.append(
            AudioSample(
                sample_id=row["sample_id"],
                audio_path=str(root / row["audio_path"]),
                reference=row["reference"],
                language=wanted or row["language"],
                dataset="demo",
                speaker_id=row.get("speaker_id"),
                metadata={
                    "license": payload.get("license"),
                    "provenance": payload.get("provenance"),
                    "language": wanted,
                    "entities": row.get("entities") or [],
                },
            )
        )
    if not samples:
        raise DatasetError(
            f"The pipeline demo has no clips for '{language}'. It only contains English."
        )
    note = (
        "Pipeline demo is synthetic English from espeak-ng. "
        "It checks that a run completes. It is not an Indic score."
    )
    return samples[:limit], note
