"""Structured text logs for the server and the experiment worker."""

from __future__ import annotations

import logging

from config.settings import load_settings


def configure_logging() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
