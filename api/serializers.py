"""JSON-safe payloads for the FastAPI backend."""

from __future__ import annotations

from typing import Any


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    return str(value)


def public_user(user: dict[str, Any] | None) -> dict[str, Any]:
    """Full candidate profile without password hashes."""
    if not user:
        return {}
    payload = dict(user)
    payload.pop("password_hash", None)
    payload.pop("admin_authenticated", None)
    return _json_safe(payload)


def public_analysis_summary(row: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "id": row.get("id"),
            "created_at": row.get("created_at"),
            "target_job_title": row.get("target_job_title"),
            "jobs_found": row.get("jobs_found"),
            "jobs_raw": row.get("jobs_raw"),
            "analysis_depth": row.get("analysis_depth"),
            "job_provider": row.get("job_provider"),
            "cv_fingerprint": row.get("cv_fingerprint"),
        }
    )


def public_analysis_job(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not job:
        return None
    return _json_safe(
        {
            "id": job.get("id"),
            "user_id": job.get("user_id"),
            "status": job.get("status"),
            "progress_percent": job.get("progress_percent") or 0,
            "progress_label": job.get("progress_label") or "",
            "analysis_id": job.get("analysis_id"),
            "cv_fingerprint": job.get("cv_fingerprint") or "",
            "error_message": job.get("error_message") or "",
            "notices_json": job.get("notices_json") or [],
            "job_provider": job.get("job_provider") or "",
            "analysis_depth": job.get("analysis_depth") or "standard",
            "created_at": job.get("created_at"),
            "finished_at": job.get("finished_at"),
        }
    )


def public_job_account(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload.pop("site_password", None)
    payload.pop("password", None)
    return _json_safe(payload)
