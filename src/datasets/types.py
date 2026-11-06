"""A row the runner can score."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AudioSample:
    sample_id: str
    audio_path: str
    reference: str
    language: str
    dataset: str
    speaker_id: str | None = None
    duration_s: float | None = None
    metadata: dict = field(default_factory=dict)
