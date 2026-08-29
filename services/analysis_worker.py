"""Process queued CV analyses with the same pipeline as the UI.

On Streamlit Cloud a daemon thread consumes the queue (no extra process).
On OVH later, run ``python scripts/run_analysis_worker.py`` on as many machines
as needed — claiming is atomic so several workers can share the table.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from observability import get_logger
from services.analysis_queue import (
    claim_next_analysis_job,
    complete_analysis_job,
    fail_analysis_job,
    update_analysis_job_progress,
)

_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_logger = get_logger(__name__)


def _job_user_profile(job: dict[str, Any]) -> dict[str, Any]:
    raw = job.get("user_profile_json") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _persist_success(job: dict[str, Any], analysis: dict[str, Any], notices: list[dict[str, str]]) -> int:
    from app import cap_results_to_requested_best
    from auth import get_user_by_id
    from email_service import email_configured, maybe_send_analysis_alert
    from persistence import (
        get_notification_settings,
        log_scheduled_run,
        mark_alert_sent,
        mark_auto_search_completed,
        save_analysis,
        upsert_active_cv_document,
    )

    user_id = int(job["user_id"])
    analysis["analysis_depth"] = str(job.get("analysis_depth") or "standard")
    if job.get("matching_top"):
        analysis["matching_top"] = int(job["matching_top"])
    analysis["results"] = cap_results_to_requested_best(
        list(analysis.get("results") or []),
        analysis,
    )
    analysis_id = save_analysis(
        user_id,
        analysis,
        cv_fingerprint=str(job.get("cv_fingerprint") or ""),
        analysis_depth=str(job.get("analysis_depth") or "standard"),
    )
    upsert_active_cv_document(
        user_id,
        str(job.get("cv_fingerprint") or ""),
        analysis.get("cv_text", ""),
        analysis.get("criteria"),
    )
    settings = get_notification_settings(user_id)
    if settings.get("email_alerts_enabled"):
        offers = [
            {
                "score": int(entry["match"].get("score_correspondance", 0)),
                "job": entry["job"],
            }
            for entry in analysis.get("results", [])
            if isinstance(entry, dict) and isinstance(entry.get("match"), dict)
        ]
        user = get_user_by_id(user_id) or {}
        sent, msg = maybe_send_analysis_alert(
            user.get("email", ""),
            user.get("full_name", ""),
            analysis.get("target_job_title", ""),
            offers,
            settings,
        )
        if sent:
            mark_alert_sent(user_id)
            notices.append({"level": "success", "text": f"Alerte e-mail envoyée — {msg}"})
        elif settings.get("alert_frequency") == "after_search" and not email_configured():
            notices.append(
                {
                    "level": "info",
                    "text": "Alertes e-mail activées — configurez RESEND_API_KEY ou SMTP dans secrets.",
                }
            )
    if str(job.get("trigger_source") or "") == "auto":
        mark_auto_search_completed(
            user_id,
            settings.get("auto_search_weekday", "daily"),
            int(settings.get("auto_search_hour", 8)),
        )
        log_scheduled_run(
            user_id,
            "success",
            analysis_id=analysis_id,
            trigger_source="app",
        )
    return int(analysis_id)


def _run_claimed_job(job: dict[str, Any]) -> None:
    from services.llm_usage import bind_usage_user_id
    from services.pipeline import run_cv_analysis_pipeline

    job_id = int(job["id"])
    profile = _job_user_profile(job)
    pdf_bytes = job.get("pdf_blob") or None
    cv_text = str(job.get("cv_text") or "").strip() or None
    bind_usage_user_id(int(job["user_id"]))

    def _progress(percent: int, label: str) -> None:
        try:
            update_analysis_job_progress(job_id, percent, label)
        except Exception:  # noqa: BLE001 — a stale pooler socket must not abort matching
            _logger.warning("Could not persist analysis progress for job %s", job_id, exc_info=True)

    try:
        analysis, notices = run_cv_analysis_pipeline(
            pdf_bytes,
            str(job.get("job_provider") or "all"),
            profile,
            matching_pool=int(job.get("matching_pool") or 0) or None,
            matching_top=int(job.get("matching_top") or 0) or None,
            cv_text_override=cv_text,
            extraction_method_override=str(job.get("extraction_method") or "native"),
            progress=_progress,
        )
        if not analysis:
            message = next(
                (item.get("text") for item in notices if item.get("level") in {"error", "warning"}),
                "Analyse vide",
            )
            fail_analysis_job(job_id, str(message), notices)
            if str(job.get("trigger_source") or "") == "auto":
                from persistence import log_scheduled_run

                log_scheduled_run(
                    int(job["user_id"]),
                    "failed",
                    error_message=str(message)[:500],
                    trigger_source="app",
                )
            return
        analysis_id = _persist_success(job, analysis, notices)
        complete_analysis_job(job_id, analysis_id=analysis_id, notices=notices)
    finally:
        bind_usage_user_id(None)


def process_next_analysis_job() -> bool:
    """Claim and run at most one job. Returns True if a ticket was processed."""
    job = claim_next_analysis_job()
    if not job:
        return False
    try:
        _run_claimed_job(job)
    except Exception as exc:  # noqa: BLE001
        _logger.exception("Analysis job %s failed", job.get("id"))
        fail_analysis_job(int(job["id"]), str(exc)[:800])
        if str(job.get("trigger_source") or "") == "auto":
            try:
                from persistence import log_scheduled_run

                log_scheduled_run(
                    int(job["user_id"]),
                    "failed",
                    error_message=str(exc)[:500],
                    trigger_source="app",
                )
            except Exception:  # noqa: BLE001
                pass
    return True


def run_analysis_worker_forever(*, idle_sleep: float = 0.1) -> None:
    """Blocking loop for a dedicated OVH / CLI worker process."""
    while True:
        try:
            processed = process_next_analysis_job()
        except Exception:  # noqa: BLE001
            _logger.exception("Analysis worker loop error")
            processed = False
        if not processed:
            time.sleep(max(0.05, float(idle_sleep)))


def ensure_embedded_analysis_worker() -> None:
    """Start one in-process consumer so Streamlit Cloud can drain the queue."""
    flag = os.getenv("ANALYSIS_WORKER_EMBEDDED", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return
    from config import export_streamlit_secrets_to_environ

    export_streamlit_secrets_to_environ()
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=run_analysis_worker_forever,
            name="analysis-worker",
            kwargs={"idle_sleep": 0.1},
            daemon=True,
        )
        _worker_thread.start()


def kick_embedded_analysis_worker() -> None:
    """Start the worker and try to claim a ticket immediately (no idle wait)."""
    ensure_embedded_analysis_worker()
    threading.Thread(
        target=process_next_analysis_job,
        name="analysis-kick",
        daemon=True,
    ).start()
