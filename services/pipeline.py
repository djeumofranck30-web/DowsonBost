"""CV analysis pipeline entry point (lazy import from Streamlit app)."""

from __future__ import annotations

from typing import Any


def run_cv_analysis_pipeline(*args: Any, **kwargs: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Run the full CV analysis pipeline.

    The implementation still lives in ``app.py`` while the UI is migrated.
    Cron jobs and the REST API should import this module instead of ``app`` directly.
    """
    from app import run_cv_analysis_pipeline as _run_pipeline

    return _run_pipeline(*args, **kwargs)
