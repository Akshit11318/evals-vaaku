"""Process entry for one experiment."""

from __future__ import annotations

import sys

from config.settings import load_settings

from src.experiments.runner import run_experiment
from src.logging_config import configure_logging
from src.storage.db import Store


def main(experiment_id: str) -> None:
    configure_logging()
    settings = load_settings()
    settings.ensure_dirs()
    store = Store(settings.db_path)
    store.init()
    run_experiment(store, experiment_id, settings)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m src.experiments.worker EXPERIMENT_ID")
    main(sys.argv[1])
