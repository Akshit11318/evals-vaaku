"""Runtime configuration. Values come from the environment and an optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    output_dir: Path
    db_path: Path
    log_level: str
    dashboard_token: str
    dashboard_auth_disabled: bool
    dashboard_host: str
    dashboard_port: int
    allow_cpu_fallback: bool
    prefer_gpu: bool
    whisper_small_min_free_mb: int
    whisper_medium_min_free_mb: int
    indic_min_free_mb: int
    mms_min_free_mb: int
    indic_decoder: str
    hf_token: str
    sample_rate: int
    max_samples: int

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "audio").mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    output_dir = _path("OUTPUT_DIR", ROOT / "outputs")
    return Settings(
        root=ROOT,
        data_dir=_path("DATA_DIR", ROOT / "data"),
        output_dir=output_dir,
        db_path=_path("DB_PATH", output_dir / "benchmark.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        dashboard_token=os.getenv("DASHBOARD_TOKEN", ""),
        dashboard_auth_disabled=os.getenv("DASHBOARD_AUTH_DISABLED", "0") == "1",
        dashboard_host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
        dashboard_port=int(os.getenv("DASHBOARD_PORT", "8787")),
        allow_cpu_fallback=os.getenv("ALLOW_CPU_FALLBACK", "1") == "1",
        prefer_gpu=os.getenv("PREFER_GPU", "1") == "1",
        whisper_small_min_free_mb=int(os.getenv("WHISPER_SMALL_MIN_FREE_MB", "1200")),
        whisper_medium_min_free_mb=int(os.getenv("WHISPER_MEDIUM_MIN_FREE_MB", "3500")),
        indic_min_free_mb=int(os.getenv("INDIC_CONFORMER_MIN_FREE_MB", "4000")),
        mms_min_free_mb=int(os.getenv("MMS_MIN_FREE_MB", "4500")),
        indic_decoder=os.getenv("INDIC_DECODER", "rnnt"),
        hf_token=os.getenv("HF_TOKEN", ""),
        sample_rate=16_000,
        max_samples=int(os.getenv("MAX_SAMPLES", "200")),
    )
