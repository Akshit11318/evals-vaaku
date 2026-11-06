"""Start a worker process so the dashboard stays responsive."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from config.settings import Settings

from src.storage.db import Store


def launch(store: Store, settings: Settings, experiment_id: str) -> int:
    log_path = settings.output_dir / "logs" / f"{experiment_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("ab")
    env = os.environ.copy()
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    process = subprocess.Popen(
        [sys.executable, "-m", "src.experiments.worker", experiment_id],
        cwd=str(settings.root),
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    handle.close()
    store.set_runtime(experiment_id, pid=process.pid, log_path=str(log_path), status="running")
    return process.pid


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_process(pid: int | None) -> None:
    if not pid_alive(pid):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)


def reconcile(store: Store) -> None:
    for experiment in store.list_by_status("running"):
        if not pid_alive(experiment.get("pid")):
            store.set_runtime(
                experiment["id"],
                status="failed",
                error="The worker process is no longer running. Read the run log.",
            )
