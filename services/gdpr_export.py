"""GDPR data export — portable JSON of the candidate's own records."""

from __future__ import annotations

from typing import Any

from persistence import (
    get_active_cv_document,
    get_notification_settings,
    list_analyses,
    list_connected_job_accounts,
    list_user_applications,
    utc_now_iso,
)


def export_user_data(user: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-serialisable export without secrets (no password hash)."""
    user_id = int(user["id"])
    profile = {
        key: user.get(key)
        for key in (
            "id",
            "full_name",
            "email",
            "phone",
            "created_at",
            "target_job_title",
            "contract_type",
            "experience_level",
            "work_mode",
            "salary_min",
            "skills_text",
            "diplomas_text",
            "experiences_text",
            "daily_rate",
            "portfolio_url",
            "selected_countries",
            "home_city",
            "preferred_language",
        )
        if key in user or user.get(key) is not None
    }
    cv_doc = get_active_cv_document(user_id) or {}
    analyses = []
    for row in list_analyses(user_id, limit=50):
        analyses.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "target_job_title": row.get("target_job_title"),
                "jobs_found": row.get("jobs_found"),
                "job_provider": row.get("job_provider"),
                "analysis_depth": row.get("analysis_depth"),
            }
        )
    applications = []
    for entry in list_user_applications(user_id):
        job = entry.get("job") or {}
        applications.append(
            {
                "result_id": entry.get("result_id"),
                "status": entry.get("application_status"),
                "method": entry.get("application_method"),
                "score": entry.get("score"),
                "updated_at": entry.get("status_updated_at"),
                "title": job.get("title"),
                "company": job.get("company"),
                "url": job.get("url"),
            }
        )
    accounts = list_connected_job_accounts(user_id)
    settings = get_notification_settings(user_id)
    return {
        "exported_at": utc_now_iso(),
        "profile": profile,
        "cv": {
            "uploaded_at": cv_doc.get("uploaded_at"),
            "extracted_text": cv_doc.get("extracted_text") or "",
        },
        "notification_settings": {
            "email_alerts_enabled": bool(settings.get("email_alerts_enabled")),
            "auto_search_enabled": bool(settings.get("auto_search_enabled")),
            "auto_search_daily_limit": settings.get("auto_search_daily_limit"),
            "alert_min_score": settings.get("alert_min_score"),
        },
        "job_accounts": [
            {
                "provider": item.get("provider"),
                "account_email": item.get("account_email"),
                "profile_url": item.get("profile_url"),
            }
            for item in accounts
        ],
        "analyses": analyses,
        "applications": applications,
    }
