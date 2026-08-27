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
from services.llm_usage import ensure_llm_usage_table
from services.support import admin_support_conversations, admin_support_unread

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


def platform_overview() -> dict[str, Any]:
    """KPI + chart series for the administration dashboard."""
    init_db()
    ensure_llm_usage_table()
    users = list_registered_users()
    active_users = sum(1 for user in users if user.get("is_active"))
    total_tokens = sum(int(user.get("tokens_consumed") or 0) for user in users)
    total_analyses = sum(int(user.get("analyses_count") or 0) for user in users)

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
        },
        "series": {
            "signups": signups,
            "analyses": analyses,
            "tokens": tokens,
        },
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
