"""FLEURS official test split. Only the requested number of rows is saved."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import soundfile as sf
from config.settings import Settings

from src.datasets.types import AudioSample
from src.errors import DatasetError
from src.languages import FLEURS_CONFIGS


def load_fleurs(
    settings: Settings, language: str, limit: int, split: str
) -> tuple[list[AudioSample], str]:
    if language not in FLEURS_CONFIGS:
        raise DatasetError(f"FLEURS has no verified config for '{language}'.")
    if split not in {"test", "validation"}:
        raise DatasetError("FLEURS runs use the test or validation split.")
    try:
        from datasets import load_dataset
    except Exception as exc:
        raise DatasetError(f"The datasets library is not available ({exc}).") from exc

    config = FLEURS_CONFIGS[language]
    try:
        from datasets import Audio

        stream = load_dataset(
            "google/fleurs",
            config,
            split=split,
            streaming=True,
            token=settings.hf_token or None,
        )
        # datasets 4 decodes audio with torchcodec. Keep the file bytes and
        # write them with soundfile instead.
        stream = stream.cast_column("audio", Audio(decode=False))
    except Exception as exc:
        raise DatasetError(
            f"FLEURS {config} {split} could not be opened ({exc}). No empty dataset was returned."
        ) from exc

    cache = settings.data_dir / "cache" / "fleurs" / language / split
    cache.mkdir(parents=True, exist_ok=True)
    samples: list[AudioSample] = []
    try:
        for row in stream:
            if len(samples) >= limit:
                break
            samples.append(_row_to_sample(row, language, cache))
    except DatasetError:
        raise
    except Exception as exc:
        raise DatasetError(f"FLEURS row could not be saved ({exc}).") from exc
    if not samples:
        raise DatasetError(
            f"FLEURS {config} {split} returned no rows. This is not an empty successful dataset."
        )
    note = (
        "FLEURS official "
        f"{split} split, config {config}, license CC BY 4.0. "
        "Speaker ids are not in this release, so a speaker-disjoint cut was not applied. "
        f"Saved {len(samples)} clips. The rest of the corpus was not downloaded."
    )
    return samples, note


def _row_to_sample(row: dict, language: str, cache) -> AudioSample:
    reference = row.get("transcription") or row.get("raw_transcription")
    audio = row.get("audio") or {}
    sample_id = _sample_id(row, audio)
    if not reference or not str(reference).strip():
        raise DatasetError(f"FLEURS row {sample_id} has no transcription.")
    array, sample_rate = _audio_array(audio, sample_id)
    path = cache / f"{sample_id}.wav"
    if not path.exists():
        sf.write(str(path), array, sample_rate)
    return AudioSample(
        sample_id=sample_id,
        audio_path=str(path),
        reference=str(reference),
        language=language,
        dataset="fleurs",
        speaker_id=None,
        metadata={
            "raw_transcription": row.get("raw_transcription"),
            "gender": str(row.get("gender")),
            "license": "CC BY 4.0",
            "provenance": "https://huggingface.co/datasets/google/fleurs",
            "language": language,
        },
    )


def _sample_id(row: dict, audio: dict) -> str:
    source = str(audio.get("path") or "")
    stem = Path(source).stem
    if stem:
        return stem
    return str(row.get("id"))


def _audio_array(audio: dict, sample_id: str) -> tuple[np.ndarray, int]:
    array = audio.get("array")
    sample_rate = audio.get("sampling_rate")
    if array is not None and sample_rate:
        values = np.asarray(array, dtype=np.float32)
    else:
        raw = audio.get("bytes")
        source = audio.get("path")
        if raw is None and source and Path(str(source)).is_file():
            raw = Path(str(source)).read_bytes()
        if not raw:
            raise DatasetError(f"FLEURS row {sample_id} has no audio bytes.")
        values, sample_rate = _read_encoded_audio(raw, str(source or ""), sample_id)
    if values.ndim > 1:
        values = values.mean(axis=1).astype(np.float32)
    if values.size == 0 or not sample_rate:
        raise DatasetError(f"FLEURS row {sample_id} has empty audio.")
    return values, int(sample_rate)


def _read_encoded_audio(raw: bytes, source: str, sample_id: str) -> tuple[np.ndarray, int]:
    try:
        data, sample_rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        return np.asarray(data, dtype=np.float32), int(sample_rate)
    except Exception as first_error:
        import tempfile

        suffix = Path(source).suffix or ".wav"
        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        target = Path(handle.name)
        try:
            handle.write(raw)
            handle.close()
            import librosa

            data, sample_rate = librosa.load(str(target), sr=None, mono=True)
            return np.asarray(data, dtype=np.float32), int(sample_rate)
        except Exception as exc:
            raise DatasetError(
                f"FLEURS row {sample_id} audio could not be decoded ({exc})."
            ) from first_error
        finally:
            target.unlink(missing_ok=True)
