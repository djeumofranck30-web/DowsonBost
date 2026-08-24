"""Structured logging for backend services, cron jobs, and API."""

from __future__ import annotations

import logging
import sys
from typing import Any


_CONFIGURED = False


def setup_logging(*, level: int = logging.INFO, json_logs: bool = False) -> None:
    """Configure root logger once (safe to call multiple times)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        formatter = logging.Formatter(
            '{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a named event with optional structured fields."""
    if fields:
        detail = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info("%s | %s", event, detail)
    else:
        logger.info(event)
