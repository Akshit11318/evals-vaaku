"""The choices stored with every run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class ExperimentConfig:
    name: str
    dataset_id: str
    language: str
    limit: int
    models: list[str]
    conditions: list[str]
    snr_levels: list[int]
    speed_factors: list[float]
    volume_db: float = -6.0
    reverb_decay: float = 0.45
    mp3_bitrate: int = 64
    batch_size: int = 1
    seed: int = 13
    manifest_path: str | None = None
    audio_dir: str | None = None
    split: str = "test"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExperimentConfig:
        known = {item.name for item in fields(cls)}
        missing = [
            name
            for name in ("name", "dataset_id", "language", "limit", "models", "conditions")
            if name not in data
        ]
        if missing:
            raise TypeError(f"Missing {', '.join(missing)}.")
        payload = {key: value for key, value in data.items() if key in known}
        payload["models"] = list(payload.get("models") or [])
        payload["conditions"] = list(payload.get("conditions") or [])
        payload["snr_levels"] = [int(value) for value in payload.get("snr_levels") or []]
        payload["speed_factors"] = [float(value) for value in payload.get("speed_factors") or []]
        payload["limit"] = int(payload["limit"])
        payload["batch_size"] = int(payload.get("batch_size") or 1)
        payload["seed"] = int(payload.get("seed") or 13)
        return cls(**payload)
