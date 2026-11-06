"""SQLite store. Experiment state survives a dashboard restart."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.experiments.config import ExperimentConfig


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    current_model TEXT,
                    current_sample TEXT,
                    error TEXT,
                    note TEXT,
                    pid INTEGER,
                    log_path TEXT
                );
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    sample_id TEXT NOT NULL,
                    dataset TEXT NOT NULL,
                    language TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT,
                    device TEXT,
                    reference TEXT NOT NULL,
                    prediction TEXT,
                    audio_condition TEXT NOT NULL,
                    transform_json TEXT,
                    seed INTEGER,
                    audio_path TEXT,
                    wer_raw REAL,
                    cer_raw REAL,
                    wer REAL,
                    cer REAL,
                    ser INTEGER,
                    substitutions INTEGER,
                    deletions INTEGER,
                    insertions INTEGER,
                    ref_words INTEGER,
                    ref_chars INTEGER,
                    char_errors INTEGER,
                    inference_time_s REAL,
                    audio_duration_s REAL,
                    rtf REAL,
                    peak_gpu_mb REAL,
                    entity_json TEXT,
                    alignment_json TEXT,
                    error TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (experiment_id, sample_id, model_id, audio_condition)
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create(self, config: ExperimentConfig) -> str:
        import uuid

        experiment_id = uuid.uuid4().hex[:12]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO experiments (
                    id, name, config_json, status, created_at, progress_current, progress_total
                ) VALUES (?, ?, ?, 'queued', ?, 0, 0)
                """,
                (experiment_id, config.name, json.dumps(config.to_dict()), utcnow()),
            )
        return experiment_id

    def set_runtime(self, experiment_id: str, **fields) -> None:
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE experiments SET {columns} WHERE id = ?",
                (*fields.values(), experiment_id),
            )

    def get(self, experiment_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
        return _experiment(row) if row else None

    def list_experiments(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
        return [_experiment(row) for row in rows]

    def list_by_status(self, status: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM experiments WHERE status = ? ORDER BY created_at",
                (status,),
            ).fetchall()
        return [_experiment(row) for row in rows]

    def has_prediction(
        self, experiment_id: str, sample_id: str, model_id: str, condition: str
    ) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM predictions
                WHERE experiment_id = ? AND sample_id = ? AND model_id = ? AND audio_condition = ?
                """,
                (experiment_id, sample_id, model_id, condition),
            ).fetchone()
        return row is not None

    def insert_prediction(self, row: dict) -> None:
        columns = list(row)
        placeholders = ", ".join("?" for _ in columns)
        names = ", ".join(columns)
        with self.connect() as conn:
            conn.execute(
                f"INSERT OR IGNORE INTO predictions ({names}) VALUES ({placeholders})",
                [row[name] for name in columns],
            )

    def list_predictions(self, experiment_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE experiment_id = ? ORDER BY id",
                (experiment_id,),
            ).fetchall()
        return [_prediction(row) for row in rows]

    def get_prediction(self, prediction_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
            ).fetchone()
        return _prediction(row) if row else None

    def save_metrics(self, experiment_id: str, payload: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO metrics (experiment_id, payload_json, created_at) VALUES (?, ?, ?)",
                (experiment_id, json.dumps(payload), utcnow()),
            )

    def counts(self) -> dict:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM experiments GROUP BY status"
            ).fetchall()
            samples = conn.execute(
                "SELECT COUNT(DISTINCT sample_id) AS n FROM predictions"
            ).fetchone()
        by_status = {row["status"]: row["n"] for row in rows}
        return {
            "queued": by_status.get("queued", 0),
            "running": by_status.get("running", 0),
            "completed": by_status.get("completed", 0),
            "failed": by_status.get("failed", 0),
            "prediction_samples": samples["n"] if samples else 0,
        }

    def any_success(self, experiment_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM predictions WHERE experiment_id = ? AND error IS NULL LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return row is not None


def _experiment(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json"))
    total = item["progress_total"] or 0
    current = item["progress_current"] or 0
    item["progress_pct"] = 0 if total == 0 else round(100 * current / total, 1)
    return item


def _prediction(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["transform"] = json.loads(item.pop("transform_json") or "{}")
    item["entity"] = json.loads(item.pop("entity_json") or "{}")
    item["alignment"] = json.loads(item.pop("alignment_json") or "[]")
    return item
