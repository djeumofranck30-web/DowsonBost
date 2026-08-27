"""Administration: registered accounts, token usage, and platform statistics."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auth import (
    _USER_SELECT_SQL,
    _row_to_user,
    delete_user_account,
    get_user_by_id,
    init_db,
    user_is_admin,
)
from config import get_admin_accounts
from database import adapt_sql, connect
from persistence import _sql_json_text, init_persistence_tables
from services.llm_usage import ensure_llm_usage_table
from services.support import admin_support_conversations, admin_support_unread

_APPLIED_STATUSES = ("applied", "interview", "offer")
_STATUS_LABELS = {
    "new": "Nouveau",
    "saved": "Sauvegardé",
    "applied": "Candidaté",
    "interview": "Entretien",
    "offer": "Offre",
    "rejected": "Refusé",
    "archived": "Archivé",
}
_SCORE_BANDS = (
    ("high", "Fort · 75–100", 75, 100),
    ("mid", "Correct · 50–74", 50, 74),
    ("low", "Faible · 0–49", 0, 49),
)

ACTIVE_USER_DAYS = 30
SERIES_DAYS = 30
ADMIN_INDEX_PATH = Path(__file__).resolve().parents[1] / "admin" / "static" / "index.html"


def _parse_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_recent(value: str, *, days: int = ACTIVE_USER_DAYS) -> bool:
    dt = _parse_iso(value)
    if dt is None:
        return False
    return datetime.now(timezone.utc) - dt <= timedelta(days=days)


def _scalar(row: Any, key: str, default: int = 0) -> int:
    if row is None:
        return default
    try:
        value = row[key]
    except Exception:  # noqa: BLE001
        try:
            value = row[0]
        except Exception:  # noqa: BLE001
            return default
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def count_admins() -> int:
    return len(get_admin_accounts())


def list_registered_users() -> list[dict[str, Any]]:
    """Every registered account with analysis and token totals."""
    init_db()
    ensure_llm_usage_table()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT {_USER_SELECT_SQL},
                    COALESCE(
                        (SELECT SUM(total_tokens) FROM llm_usage WHERE user_id = users.id),
                        0
                    ) AS tokens_consumed,
                    COALESCE(
                        (SELECT COUNT(*) FROM analyses WHERE user_id = users.id),
                        0
                    ) AS analyses_count
                FROM users
                ORDER BY created_at DESC
                """
            )
        ).fetchall()
    users: list[dict[str, Any]] = []
    for row in rows:
        user = _row_to_user(row, include_created=True)
        user["is_admin"] = str(user.get("email") or "").strip().lower() in {
            email for email, _password in get_admin_accounts()
        }
        user["tokens_consumed"] = _scalar(row, "tokens_consumed")
        user["analyses_count"] = _scalar(row, "analyses_count")
        user["is_active"] = _is_recent(user.get("last_login_at") or "") or _is_recent(
            user.get("created_at") or ""
        )
        users.append(user)
    return users


def public_user_record(user: dict[str, Any]) -> dict[str, Any]:
    """Safe payload for the admin UI (no secrets)."""
    countries = user.get("selected_countries") or []
    cities = user.get("selected_cities") or []
    return {
        "id": int(user["id"]),
        "full_name": user.get("full_name") or "",
        "email": user.get("email") or "",
        "phone": user.get("phone") or "",
        "created_at": user.get("created_at") or "",
        "last_login_at": user.get("last_login_at") or "",
        "is_admin": bool(user.get("is_admin")),
        "is_active": bool(user.get("is_active")),
        "target_job_title": user.get("target_job_title") or "",
        "contract_type": user.get("contract_type") or "",
        "experience_level": user.get("experience_level") or "",
        "country": user.get("country") or "",
        "countries": list(countries),
        "cities": list(cities),
        "preferred_language": user.get("preferred_language") or "fr",
        "tokens_consumed": int(user.get("tokens_consumed") or 0),
        "analyses_count": int(user.get("analyses_count") or 0),
    }


def admin_delete_user(actor: dict[str, Any] | int, target_id: int) -> tuple[bool, str]:
    """Delete a registered user from the admin space."""
    if isinstance(actor, int):
        return False, "Accès réservé aux administrateurs."
    if not user_is_admin(actor):
        return False, "Accès réservé aux administrateurs."
    actor_id = int(actor.get("id") or 0)
    if actor_id and actor_id == int(target_id):
        return False, "Vous ne pouvez pas supprimer votre propre compte depuis l'administration."
    target = get_user_by_id(int(target_id))
    if not target:
        return False, "Utilisateur introuvable."
    return delete_user_account(int(target_id))


def _day_counts(sql: str) -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(adapt_sql(sql)).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        day = str(row["day"] or "")[:10]
        if day:
            counts[day] = _scalar(row, "n")
    return counts


def _fill_series(counts: dict[str, int], *, days: int = SERIES_DAYS) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    series: list[dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        series.append(
            {
                "date": key,
                "label": day.strftime("%d/%m"),
                "value": int(counts.get(key, 0)),
            }
        )
    return series


def _round_score(value: Any) -> float:
    try:
        return round(float(value or 0), 1)
    except (TypeError, ValueError):
        return 0.0


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)


def analysis_insights() -> dict[str, Any]:
    """Matching quality, recent runs and top job results for the admin board."""
    init_persistence_tables()
    title_sql = _sql_json_text("ar.job_json", "title")
    company_sql = _sql_json_text("ar.job_json", "company")
    location_sql = _sql_json_text("ar.job_json", "location")
    applied_placeholders = ", ".join("?" for _ in _APPLIED_STATUSES)

    with connect() as conn:
        totals = conn.execute(
            adapt_sql(
                f"""
                SELECT COUNT(*) AS matches,
                       COALESCE(AVG(score), 0) AS avg_score,
                       SUM(CASE WHEN score >= 75 THEN 1 ELSE 0 END) AS high_matches,
                       SUM(CASE WHEN application_status IN ({applied_placeholders}) THEN 1 ELSE 0 END) AS applied
                FROM analysis_results
                """
            ),
            _APPLIED_STATUSES,
        ).fetchone()
        band_rows = conn.execute(
            adapt_sql(
                """
                SELECT CASE
                         WHEN score >= 75 THEN 'high'
                         WHEN score >= 50 THEN 'mid'
                         ELSE 'low'
                       END AS band,
                       COUNT(*) AS n
                FROM analysis_results
                GROUP BY 1
                """
            )
        ).fetchall()
        status_rows = conn.execute(
            adapt_sql(
                """
                SELECT application_status AS status, COUNT(*) AS n
                FROM analysis_results
                GROUP BY 1
                ORDER BY n DESC
                """
            )
        ).fetchall()
        quality_rows = conn.execute(
            adapt_sql(
                """
                SELECT substr(a.created_at, 1, 10) AS day,
                       COALESCE(AVG(ar.score), 0) AS avg_score,
                       COUNT(ar.id) AS n
                FROM analysis_results ar
                JOIN analyses a ON a.id = ar.analysis_id
                GROUP BY 1
                """
            )
        ).fetchall()
        recent_rows = conn.execute(
            adapt_sql(
                """
                SELECT a.id, a.created_at, a.target_job_title, a.jobs_found, a.job_provider,
                       u.full_name, u.email,
                       COUNT(ar.id) AS matches,
                       COALESCE(AVG(ar.score), 0) AS avg_score,
                       COALESCE(MAX(ar.score), 0) AS max_score,
                       SUM(CASE WHEN ar.score >= 75 THEN 1 ELSE 0 END) AS high_matches
                FROM analyses a
                JOIN users u ON u.id = a.user_id
                LEFT JOIN analysis_results ar ON ar.analysis_id = a.id
                GROUP BY a.id, a.created_at, a.target_job_title, a.jobs_found, a.job_provider,
                         u.full_name, u.email
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT 8
                """
            )
        ).fetchall()
        top_rows = conn.execute(
            adapt_sql(
                f"""
                SELECT ar.id AS result_id, ar.score, ar.application_status,
                       a.created_at, a.target_job_title,
                       u.full_name, u.email,
                       {title_sql} AS job_title,
                       {company_sql} AS job_company,
                       {location_sql} AS job_location
                FROM analysis_results ar
                JOIN analyses a ON a.id = ar.analysis_id
                JOIN users u ON u.id = ar.user_id
                ORDER BY ar.score DESC, a.created_at DESC, ar.id DESC
                LIMIT 8
                """
            )
        ).fetchall()
        title_rows = conn.execute(
            adapt_sql(
                """
                SELECT a.target_job_title AS title,
                       COUNT(DISTINCT a.id) AS runs,
                       COUNT(ar.id) AS matches,
                       COALESCE(AVG(ar.score), 0) AS avg_score
                FROM analyses a
                LEFT JOIN analysis_results ar ON ar.analysis_id = a.id
                WHERE TRIM(COALESCE(a.target_job_title, '')) != ''
                GROUP BY 1
                ORDER BY runs DESC, avg_score DESC
                LIMIT 5
                """
            )
        ).fetchall()

    matches_total = _scalar(totals, "matches")
    high_matches = _scalar(totals, "high_matches")
    applied_total = _scalar(totals, "applied")
    avg_score = _round_score(totals["avg_score"] if totals is not None else 0)
    band_counts = {str(row["band"] or ""): _scalar(row, "n") for row in band_rows}
    quality_avgs = {str(row["day"] or "")[:10]: _round_score(row["avg_score"]) for row in quality_rows}
    quality_counts = {str(row["day"] or "")[:10]: _scalar(row, "n") for row in quality_rows}
    quality_series = []
    today = datetime.now(timezone.utc).date()
    for offset in range(SERIES_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        quality_series.append(
            {
                "date": key,
                "label": day.strftime("%d/%m"),
                "value": quality_avgs.get(key, 0.0),
                "matches": quality_counts.get(key, 0),
            }
        )

    return {
        "kpis": {
            "matches_total": matches_total,
            "avg_score": avg_score,
            "high_matches": high_matches,
            "high_rate": _pct(high_matches, matches_total),
            "applied_total": applied_total,
            "applied_rate": _pct(applied_total, matches_total),
        },
        "score_bands": [
            {
                "key": key,
                "label": label,
                "count": int(band_counts.get(key, 0)),
                "pct": _pct(int(band_counts.get(key, 0)), matches_total),
            }
            for key, label, _lo, _hi in _SCORE_BANDS
        ],
        "status_mix": [
            {
                "status": str(row["status"] or "new"),
                "label": _STATUS_LABELS.get(str(row["status"] or "new"), str(row["status"] or "new")),
                "count": _scalar(row, "n"),
            }
            for row in status_rows
        ],
        "quality": quality_series,
        "recent_runs": [
            {
                "id": int(row["id"]),
                "created_at": str(row["created_at"] or ""),
                "full_name": str(row["full_name"] or ""),
                "email": str(row["email"] or ""),
                "target_job_title": str(row["target_job_title"] or ""),
                "jobs_found": _scalar(row, "jobs_found"),
                "matches": _scalar(row, "matches"),
                "avg_score": _round_score(row["avg_score"]),
                "max_score": _scalar(row, "max_score"),
                "high_matches": _scalar(row, "high_matches"),
                "job_provider": str(row["job_provider"] or ""),
            }
            for row in recent_rows
        ],
        "top_matches": [
            {
                "result_id": int(row["result_id"]),
                "score": _scalar(row, "score"),
                "status": str(row["application_status"] or "new"),
                "created_at": str(row["created_at"] or ""),
                "full_name": str(row["full_name"] or ""),
                "email": str(row["email"] or ""),
                "target_job_title": str(row["target_job_title"] or ""),
                "job_title": str(row["job_title"] or ""),
                "company": str(row["job_company"] or ""),
                "location": str(row["job_location"] or ""),
            }
            for row in top_rows
        ],
        "by_title": [
            {
                "title": str(row["title"] or ""),
                "runs": _scalar(row, "runs"),
                "matches": _scalar(row, "matches"),
                "avg_score": _round_score(row["avg_score"]),
            }
            for row in title_rows
        ],
    }


def platform_overview() -> dict[str, Any]:
    """KPI + chart series for the administration dashboard."""
    init_db()
    init_persistence_tables()
    ensure_llm_usage_table()
    users = list_registered_users()
    active_users = sum(1 for user in users if user.get("is_active"))
    total_tokens = sum(int(user.get("tokens_consumed") or 0) for user in users)
    total_analyses = sum(int(user.get("analyses_count") or 0) for user in users)
    insights = analysis_insights()

    signups = _fill_series(
        _day_counts(
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM users GROUP BY 1"
        )
    )
    analyses = _fill_series(
        _day_counts(
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM analyses GROUP BY 1"
        )
    )
    tokens = _fill_series(
        _day_counts(
            """
            SELECT substr(created_at, 1, 10) AS day,
                   COALESCE(SUM(total_tokens), 0) AS n
            FROM llm_usage
            GROUP BY 1
            """
        )
    )

    with connect() as conn:
        provider_rows = conn.execute(
            adapt_sql(
                """
                SELECT provider, COALESCE(SUM(total_tokens), 0) AS n
                FROM llm_usage
                GROUP BY provider
                ORDER BY n DESC
                """
            )
        ).fetchall()
        call_row = conn.execute(
            adapt_sql("SELECT COUNT(*) AS n FROM llm_usage")
        ).fetchone()

    tokens_by_user = sorted(
        (
            {
                "id": int(user["id"]),
                "name": user.get("full_name") or user.get("email") or "Utilisateur",
                "email": user.get("email") or "",
                "tokens": int(user.get("tokens_consumed") or 0),
            }
            for user in users
        ),
        key=lambda item: item["tokens"],
        reverse=True,
    )
    top_tokens = [item for item in tokens_by_user if item["tokens"] > 0][:12]
    if not top_tokens:
        top_tokens = tokens_by_user[:8]

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "kpis": {
            "users_total": len(users),
            "users_active": active_users,
            "tokens_total": total_tokens,
            "analyses_total": total_analyses,
            "llm_calls": _scalar(call_row, "n"),
            "admins": len(get_admin_accounts()),
            "matches_total": insights["kpis"]["matches_total"],
            "avg_score": insights["kpis"]["avg_score"],
            "high_matches": insights["kpis"]["high_matches"],
            "applied_total": insights["kpis"]["applied_total"],
        },
        "series": {
            "signups": signups,
            "analyses": analyses,
            "tokens": tokens,
            "quality": insights["quality"],
        },
        "analysis": insights,
        "tokens_by_user": top_tokens,
        "tokens_by_provider": [
            {"provider": str(row["provider"] or "unknown"), "tokens": _scalar(row, "n")}
            for row in provider_rows
        ],
        "users": [public_user_record(user) for user in users],
        "support": {
            "unread": admin_support_unread(),
            "conversations": admin_support_conversations(),
        },
    }


def dashboard_html(payload: dict[str, Any] | None = None, *, embedded: bool = False) -> str:
    """Return the admin SPA, optionally with data injected for Streamlit."""
    template = ADMIN_INDEX_PATH.read_text(encoding="utf-8")
    data = dict(payload or {})
    data["embedded"] = embedded
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace("/*__ADMIN_PAYLOAD__*/", f"window.__DOWSONBOST_ADMIN__ = {blob};")
