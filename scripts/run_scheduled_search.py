#!/usr/bin/env python3
"""Run scheduled job searches for all due users (cron / GitHub Actions)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_secrets_from_toml() -> None:
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.is_file():
        return
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    with secrets_path.open("rb") as handle:
        data = tomllib.load(handle)
    for key, value in data.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_secrets_from_toml()
    from auth import get_user_by_id, init_db
    from constants import ANALYSIS_DEPTH_POOL, ANALYSIS_DEPTH_TOP
    from database import configure_database
    from email_service import maybe_send_analysis_alert
    from observability import get_logger, setup_logging
    from persistence import (
        get_active_cv_document,
        get_notification_settings,
        get_users_due_for_auto_search,
        log_scheduled_run,
        mark_alert_sent,
        mark_auto_search_completed,
        save_analysis,
        upsert_active_cv_document,
    )
    from services.pipeline import run_cv_analysis_pipeline

    setup_logging()
    logger = get_logger(__name__)

    configure_database(
        os.environ.get("DATABASE_URL", ""),
        password=os.environ.get("DATABASE_PASSWORD", ""),
    )
    init_db()

    due_users = get_users_due_for_auto_search()
    if not due_users:
        print("No users due for auto search.")
        return 0

    for row in due_users:
        user_id = int(row["user_id"])
        user = get_user_by_id(user_id)
        if not user:
            continue
        cv_doc = get_active_cv_document(user_id)
        if not cv_doc:
            log_scheduled_run(
                user_id,
                "skipped",
                error_message="No active CV",
                trigger_source="cron",
            )
            print(f"User {user_id}: skipped (no CV)")
            continue

        depth = row.get("auto_search_depth", "standard")
        if depth not in ANALYSIS_DEPTH_POOL:
            depth = "standard"
        provider = row.get("auto_search_provider") or "all"

        log_scheduled_run(user_id, "running", trigger_source="cron")
        try:
            analysis, _notices = run_cv_analysis_pipeline(
                None,
                provider,
                user,
                matching_pool=ANALYSIS_DEPTH_POOL[depth],
                matching_top=ANALYSIS_DEPTH_TOP[depth],
                cv_text_override=cv_doc["extracted_text"],
                extraction_method_override="native",
            )
            if not analysis:
                log_scheduled_run(
                    user_id,
                    "failed",
                    error_message="Empty pipeline result",
                    trigger_source="cron",
                )
                print(f"User {user_id}: failed (empty result)")
                continue

            analysis_id = save_analysis(
                user_id,
                analysis,
                cv_fingerprint=cv_doc["fingerprint"],
                analysis_depth=depth,
            )
            upsert_active_cv_document(
                user_id,
                cv_doc["fingerprint"],
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
                ]
                sent, _msg = maybe_send_analysis_alert(
                    user.get("email", ""),
                    user.get("full_name", ""),
                    analysis.get("target_job_title", ""),
                    offers,
                    settings,
                )
                if sent:
                    mark_alert_sent(user_id)

            mark_auto_search_completed(
                user_id,
                row.get("auto_search_weekday", "daily"),
                int(row.get("auto_search_hour", 8)),
            )
            log_scheduled_run(
                user_id,
                "success",
                analysis_id=analysis_id,
                trigger_source="cron",
            )
            print(f"User {user_id}: success (analysis #{analysis_id})")
        except Exception as exc:  # noqa: BLE001
            log_scheduled_run(
                user_id,
                "failed",
                error_message=str(exc)[:500],
                trigger_source="cron",
            )
            print(f"User {user_id}: error — {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
