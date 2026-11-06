"""Which datasets can be selected. Unavailable sets stay visible with the reason."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from config.settings import Settings

from src.datasets.demo import demo_manifest, load_demo
from src.datasets.fleurs import load_fleurs
from src.datasets.manifest import load_manifest
from src.datasets.types import AudioSample
from src.errors import DatasetError
from src.languages import TARGET_LANGUAGES


@dataclass
class DatasetCard:
    dataset_id: str
    name: str
    languages: list[str]
    license_name: str
    provenance: str
    selectable: bool
    reason: str
    sample_count: int | None
    duration_s: float | None
    speaker_note: str


def list_datasets(settings: Settings) -> list[DatasetCard]:
    demo_count = 0
    demo_seconds = None
    path = demo_manifest(settings)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        demo_count = len(payload.get("samples") or [])
    return [
        DatasetCard(
            dataset_id="fleurs",
            name="FLEURS",
            languages=list(TARGET_LANGUAGES),
            license_name="CC BY 4.0",
            provenance="https://huggingface.co/datasets/google/fleurs",
            selectable=True,
            reason="Public. A run downloads only the selected test rows for one language.",
            sample_count=None,
            duration_s=None,
            speaker_note="No speaker ids in the Hugging Face release.",
        ),
        DatasetCard(
            dataset_id="demo",
            name="Pipeline demo",
            languages=["en"],
            license_name="espeak-ng GPL-3.0, synthetic English",
            provenance="local espeak-ng",
            selectable=demo_count > 0,
            reason="Synthetic English clips for a pipeline check. Not an Indic score.",
            sample_count=demo_count,
            duration_s=demo_seconds,
            speaker_note="One synthetic voice.",
        ),
        DatasetCard(
            dataset_id="custom",
            name="Custom manifest",
            languages=list(TARGET_LANGUAGES) + ["en"],
            license_name="Declared in the manifest",
            provenance="Local CSV or JSON",
            selectable=True,
            reason="Bring a CSV or JSON manifest and an audio directory.",
            sample_count=None,
            duration_s=None,
            speaker_note="Uses speaker_id when the column is present, one clip per speaker.",
        ),
        DatasetCard(
            dataset_id="indicvoices",
            name="IndicVoices",
            languages=list(TARGET_LANGUAGES),
            license_name="Gated on Hugging Face",
            provenance="https://huggingface.co/datasets/ai4bharat/IndicVoices",
            selectable=False,
            reason="Gated, and AI4Bharat trained Indic models on this collection. It is not a fair headline set until a held-out split is verified.",
            sample_count=None,
            duration_s=None,
            speaker_note="Speakers exist, but the set is not selectable.",
        ),
        DatasetCard(
            dataset_id="kathbath",
            name="Kathbath",
            languages=list(TARGET_LANGUAGES),
            license_name="Gated on Hugging Face",
            provenance="https://huggingface.co/datasets/ai4bharat/Kathbath",
            selectable=False,
            reason="Gated. Reported as IndicConformer training speech, so it is excluded from the headline score.",
            sample_count=None,
            duration_s=None,
            speaker_note="Not selectable.",
        ),
        DatasetCard(
            dataset_id="common_voice",
            name="Mozilla Common Voice",
            languages=["hi", "ta", "ml"],
            license_name="CC-0",
            provenance="https://huggingface.co/datasets/mozilla-foundation/common_voice_17_0",
            selectable=False,
            reason="Telugu and Kannada are missing or too small in the Vistaar tables, so a five-language average would be misleading.",
            sample_count=None,
            duration_s=None,
            speaker_note="Not selectable.",
        ),
    ]


def load_samples(dataset_id: str, settings: Settings, config) -> tuple[list[AudioSample], str]:
    if dataset_id == "fleurs":
        return load_fleurs(settings, config.language, config.limit, config.split)
    if dataset_id == "demo":
        return load_demo(settings, config.language, config.limit)
    if dataset_id == "custom":
        from pathlib import Path

        if not config.manifest_path or not config.audio_dir:
            raise DatasetError("A custom run needs a manifest path and an audio directory.")
        samples = load_manifest(
            Path(config.manifest_path),
            Path(config.audio_dir),
            config.language,
            config.limit,
        )
        note = "Custom manifest. Speaker-disjoint when speaker_id is present."
        return samples, note
    raise DatasetError(
        f"{dataset_id} is not available for a run. See the dataset list for the reason."
    )


def cards_as_dicts(settings: Settings) -> list[dict]:
    return [asdict(card) for card in list_datasets(settings)]
