"""CSV and JSON manifests. Audio paths resolve against the audio directory."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.datasets.types import AudioSample
from src.errors import DatasetError
from src.languages import canonicalize

MAX_ROWS = 5000
REQUIRED = ("sample_id", "audio_path", "reference", "language")


def load_manifest(
    manifest_path: Path, audio_dir: Path, language: str, limit: int
) -> list[AudioSample]:
    if not manifest_path.is_file():
        raise DatasetError(f"Manifest not found: {manifest_path}")
    if manifest_path.suffix.lower() == ".json":
        rows = _json_rows(manifest_path)
        provenance = rows.get("provenance")
        license_name = rows.get("license")
        samples = rows["samples"]
    else:
        provenance = str(manifest_path)
        license_name = "unspecified"
        samples = _csv_rows(manifest_path)
    if len(samples) > MAX_ROWS:
        raise DatasetError(
            f"Manifest has {len(samples)} rows. Pass a subset of at most {MAX_ROWS} rows."
        )
    wanted = canonicalize(language)
    chosen: list[AudioSample] = []
    for index, row in enumerate(samples, start=1):
        missing = [key for key in REQUIRED if not str(row.get(key) or "").strip()]
        if missing:
            raise DatasetError(f"Row {index} is missing {', '.join(missing)}.")
        row_language = canonicalize(str(row["language"]))
        if row_language is None:
            raise DatasetError(f"Row {index} has an unknown language '{row['language']}'.")
        if wanted and row_language != wanted:
            continue
        audio_path = Path(str(row["audio_path"]))
        if not audio_path.is_absolute():
            audio_path = audio_dir / audio_path
        chosen.append(
            AudioSample(
                sample_id=str(row["sample_id"]),
                audio_path=str(audio_path),
                reference=str(row["reference"]),
                language=row_language,
                dataset="custom",
                speaker_id=(str(row["speaker_id"]) if row.get("speaker_id") else None),
                metadata={
                    "entities": row.get("entities") or [],
                    "license": license_name,
                    "provenance": provenance,
                    "language": row_language,
                },
            )
        )
    if not chosen:
        raise DatasetError(
            f"No samples for language '{language}' in {manifest_path}. "
            "This is not an empty successful dataset."
        )
    return _speaker_take(chosen, limit)


def manifest_languages(manifest_path: Path) -> list[str]:
    if not manifest_path.is_file():
        return []
    if manifest_path.suffix.lower() == ".json":
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = payload.get("samples") or []
    else:
        with manifest_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    found = []
    for row in rows:
        code = canonicalize(str(row.get("language") or ""))
        if code and code not in found:
            found.append(code)
    return found


def _json_rows(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "samples" not in payload:
        raise DatasetError("JSON manifest needs a 'samples' list.")
    return payload


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetError("CSV manifest has no header.")
        missing = [key for key in REQUIRED if key not in reader.fieldnames]
        if missing:
            raise DatasetError(f"CSV manifest is missing columns: {', '.join(missing)}.")
        return list(reader)


def _speaker_take(samples: list[AudioSample], limit: int) -> list[AudioSample]:
    speakers = [sample.speaker_id for sample in samples if sample.speaker_id]
    if not speakers:
        return samples[:limit]
    picked: list[AudioSample] = []
    seen: set[str] = set()
    for sample in samples:
        speaker = sample.speaker_id or sample.sample_id
        if speaker in seen:
            continue
        seen.add(speaker)
        picked.append(sample)
        if len(picked) >= limit:
            break
    return picked
