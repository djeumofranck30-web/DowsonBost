"""Persist analyses, job tracking, notification settings and CV documents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from database import adapt_sql, connect, database_backend, existing_columns

APPLICATION_STATUSES = (
    "new",
    "saved",
    "applied",
    "interview",
    "offer",
    "rejected",
    "archived",
)

APPLICATION_METHODS = (
    "manual",
    "auto_email",
    "auto_prepared",
)

_APPLIED_HISTORY_STATUSES = ("applied", "interview", "offer")

AUTO_SEARCH_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "daily",
)

_ALERT_FREQUENCIES = ("after_search", "daily", "weekly")

_PERSISTENCE_SCHEMA_KEY = (
    "analyses_v1",
    "analysis_results_v1",
    "user_notification_settings_v1",
    "scheduled_runs_v1",
    "cv_documents_v1",
)
_persistence_initialized_for: tuple[str, ...] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def job_offer_key(job: dict[str, Any]) -> str:
    url = str(job.get("url") or "").strip()
    if url:
        payload = url
    else:
        payload = "|".join(
            str(job.get(field, "")).strip().lower()
            for field in ("title", "company", "location")
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def _create_analyses_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                cv_fingerprint TEXT NOT NULL,
                cv_text TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                criteria_json TEXT NOT NULL,
                user_profile_snapshot TEXT NOT NULL,
                target_job_title TEXT NOT NULL,
                search_plan_json TEXT NOT NULL,
                filter_stats_json TEXT NOT NULL,
                jobs_found INTEGER NOT NULL,
                jobs_raw INTEGER NOT NULL,
                search_strategy TEXT,
                search_query_used TEXT,
                job_provider TEXT NOT NULL,
                analysis_depth TEXT NOT NULL DEFAULT 'standard',
                status TEXT NOT NULL DEFAULT 'completed'
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS analyses_user_created_idx
            ON analyses (user_id, created_at DESC)
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            cv_fingerprint TEXT NOT NULL,
            cv_text TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            criteria_json TEXT NOT NULL,
            user_profile_snapshot TEXT NOT NULL,
            target_job_title TEXT NOT NULL,
            search_plan_json TEXT NOT NULL,
            filter_stats_json TEXT NOT NULL,
            jobs_found INTEGER NOT NULL,
            jobs_raw INTEGER NOT NULL,
            search_strategy TEXT,
            search_query_used TEXT,
            job_provider TEXT NOT NULL,
            analysis_depth TEXT NOT NULL DEFAULT 'standard',
            status TEXT NOT NULL DEFAULT 'completed',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS analyses_user_created_idx
        ON analyses (user_id, created_at DESC)
        """
    )


def _create_analysis_results_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_results (
                id SERIAL PRIMARY KEY,
                analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                job_key TEXT NOT NULL,
                job_json TEXT NOT NULL,
                match_json TEXT NOT NULL,
                score INTEGER NOT NULL,
                application_status TEXT NOT NULL DEFAULT 'new',
                status_updated_at TEXT,
                notes TEXT NOT NULL DEFAULT '',
                cover_letter_text TEXT,
                adapted_cv_text TEXT,
                documents_generated_at TEXT,
                UNIQUE (analysis_id, job_key)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ar_user_status_score_idx
            ON analysis_results (user_id, application_status, score DESC)
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            job_key TEXT NOT NULL,
            job_json TEXT NOT NULL,
            match_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            application_status TEXT NOT NULL DEFAULT 'new',
            status_updated_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            cover_letter_text TEXT,
            adapted_cv_text TEXT,
            documents_generated_at TEXT,
            UNIQUE (analysis_id, job_key),
            FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS ar_user_status_score_idx
        ON analysis_results (user_id, application_status, score DESC)
        """
    )


def _create_user_notification_settings_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_notification_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                email_alerts_enabled INTEGER NOT NULL DEFAULT 0,
                alert_min_score INTEGER NOT NULL DEFAULT 70,
                alert_frequency TEXT NOT NULL DEFAULT 'after_search',
                last_alert_sent_at TEXT,
                auto_search_enabled INTEGER NOT NULL DEFAULT 0,
                auto_search_weekday TEXT NOT NULL DEFAULT 'daily',
                auto_search_hour INTEGER NOT NULL DEFAULT 8,
                auto_search_provider TEXT NOT NULL DEFAULT 'all',
                auto_search_depth TEXT NOT NULL DEFAULT 'standard',
                last_auto_search_at TEXT,
                next_auto_search_at TEXT
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_notification_settings (
            user_id INTEGER PRIMARY KEY,
            email_alerts_enabled INTEGER NOT NULL DEFAULT 0,
            alert_min_score INTEGER NOT NULL DEFAULT 70,
            alert_frequency TEXT NOT NULL DEFAULT 'after_search',
            last_alert_sent_at TEXT,
            auto_search_enabled INTEGER NOT NULL DEFAULT 0,
            auto_search_weekday TEXT NOT NULL DEFAULT 'daily',
            auto_search_hour INTEGER NOT NULL DEFAULT 8,
            auto_search_provider TEXT NOT NULL DEFAULT 'all',
            auto_search_depth TEXT NOT NULL DEFAULT 'standard',
            last_auto_search_at TEXT,
            next_auto_search_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def _create_scheduled_runs_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_runs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL,
                error_message TEXT,
                trigger_source TEXT NOT NULL DEFAULT 'cron'
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            analysis_id INTEGER,
            error_message TEXT,
            trigger_source TEXT NOT NULL DEFAULT 'cron',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE SET NULL
        )
        """
    )


def _create_cv_documents_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cv_documents (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                fingerprint TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                criteria_json TEXT,
                uploaded_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE (user_id, fingerprint)
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cv_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            criteria_json TEXT,
            uploaded_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE (user_id, fingerprint),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def _migrate_analysis_results_columns(conn: Any) -> None:
    cols = existing_columns(conn, "analysis_results")
    if "application_method" in cols:
        return
    if database_backend() == "postgres":
        conn.execute(
            "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS application_method TEXT"
        )
    else:
        conn.execute("ALTER TABLE analysis_results ADD COLUMN application_method TEXT")


def init_persistence_tables() -> None:
    """Create persistence tables once per process."""
    global _persistence_initialized_for
    if _persistence_initialized_for == _PERSISTENCE_SCHEMA_KEY:
        return
    with connect() as conn:
        _create_analyses_table(conn)
        _create_analysis_results_table(conn)
        _migrate_analysis_results_columns(conn)
        _create_user_notification_settings_table(conn)
        _create_scheduled_runs_table(conn)
        _create_cv_documents_table(conn)
        _ = existing_columns(conn, "analyses")
    _persistence_initialized_for = _PERSISTENCE_SCHEMA_KEY


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default if default is not None else {}


def save_analysis(
    user_id: int,
    analysis: dict[str, Any],
    *,
    cv_fingerprint: str,
    analysis_depth: str = "standard",
) -> int:
    """Persist a completed analysis and its job results. Returns analysis id."""
    init_persistence_tables()
    created_at = utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            adapt_sql(
                """
                INSERT INTO analyses (
                    user_id, created_at, cv_fingerprint, cv_text, extraction_method,
                    criteria_json, user_profile_snapshot, target_job_title,
                    search_plan_json, filter_stats_json, jobs_found, jobs_raw,
                    search_strategy, search_query_used, job_provider, analysis_depth, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            ),
            (
                user_id,
                created_at,
                cv_fingerprint,
                analysis.get("cv_text", ""),
                analysis.get("extraction_method", "native"),
                _json_dumps(analysis.get("criteria", {})),
                _json_dumps(analysis.get("user_profile", {})),
                analysis.get("target_job_title", ""),
                _json_dumps(analysis.get("search_plan", {})),
                _json_dumps(analysis.get("filter_stats", {})),
                int(analysis.get("jobs_found", 0)),
                int(analysis.get("jobs_raw", 0)),
                analysis.get("search_strategy"),
                analysis.get("search_query_used"),
                analysis.get("job_provider", ""),
                analysis_depth,
                "completed",
            ),
        )
        analysis_id = int(getattr(cur, "lastrowid", 0) or 0)
        if database_backend() == "postgres":
            row = conn.execute(
                adapt_sql(
                    "SELECT id FROM analyses WHERE user_id = ? AND created_at = ? ORDER BY id DESC LIMIT 1"
                ),
                (user_id, created_at),
            ).fetchone()
            analysis_id = int(row["id"]) if row else analysis_id

        for entry in analysis.get("results", []):
            job = entry.get("job") or {}
            match = entry.get("match") or {}
            score = int(match.get("score_correspondance", 0))
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO analysis_results (
                        analysis_id, user_id, job_key, job_json, match_json, score,
                        application_status, status_updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    analysis_id,
                    user_id,
                    job_offer_key(job),
                    _json_dumps(job),
                    _json_dumps(match),
                    score,
                    "new",
                    created_at,
                ),
            )

    analysis["analysis_id"] = analysis_id
    analysis["saved_at"] = created_at
    return analysis_id


def upsert_active_cv_document(
    user_id: int,
    fingerprint: str,
    extracted_text: str,
    criteria: dict[str, Any] | None = None,
) -> None:
    """Store the latest CV text for scheduled searches."""
    init_persistence_tables()
    uploaded_at = utc_now_iso()
    criteria_json = _json_dumps(criteria or {})
    with connect() as conn:
        conn.execute(
            adapt_sql("UPDATE cv_documents SET is_active = 0 WHERE user_id = ?"),
            (user_id,),
        )
        existing = conn.execute(
            adapt_sql(
                "SELECT id FROM cv_documents WHERE user_id = ? AND fingerprint = ? LIMIT 1"
            ),
            (user_id, fingerprint),
        ).fetchone()
        if existing:
            conn.execute(
                adapt_sql(
                    """
                    UPDATE cv_documents
                    SET extracted_text = ?, criteria_json = ?, uploaded_at = ?, is_active = 1
                    WHERE user_id = ? AND fingerprint = ?
                    """
                ),
                (extracted_text, criteria_json, uploaded_at, user_id, fingerprint),
            )
        else:
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO cv_documents (
                        user_id, fingerprint, extracted_text, criteria_json, uploaded_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, 1)
                    """
                ),
                (user_id, fingerprint, extracted_text, criteria_json, uploaded_at),
            )


def get_active_cv_document(user_id: int) -> dict[str, Any] | None:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT fingerprint, extracted_text, criteria_json, uploaded_at
                FROM cv_documents
                WHERE user_id = ? AND is_active = 1
                ORDER BY uploaded_at DESC
                LIMIT 1
                """
            ),
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "fingerprint": row["fingerprint"],
        "extracted_text": row["extracted_text"],
        "criteria": _json_loads(row["criteria_json"], {}),
        "uploaded_at": row["uploaded_at"],
    }


def list_analyses(user_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    init_persistence_tables()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT id, created_at, target_job_title, jobs_found, jobs_raw,
                       job_provider, analysis_depth, cv_fingerprint
                FROM analyses
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """
            ),
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_analysis(user_id: int, analysis_id: int) -> dict[str, Any] | None:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT * FROM analyses WHERE id = ? AND user_id = ?"),
            (analysis_id, user_id),
        ).fetchone()
        if not row:
            return None
        results = conn.execute(
            adapt_sql(
                """
                SELECT id, job_key, job_json, match_json, score, application_status,
                       status_updated_at, notes, cover_letter_text, adapted_cv_text,
                       documents_generated_at
                FROM analysis_results
                WHERE analysis_id = ? AND user_id = ?
                ORDER BY score DESC
                """
            ),
            (analysis_id, user_id),
        ).fetchall()

    analysis = dict(row)
    analysis["criteria"] = _json_loads(analysis.pop("criteria_json", ""), {})
    analysis["user_profile"] = _json_loads(analysis.pop("user_profile_snapshot", ""), {})
    analysis["search_plan"] = _json_loads(analysis.pop("search_plan_json", ""), {})
    analysis["filter_stats"] = _json_loads(analysis.pop("filter_stats_json", ""), {})
    analysis["results"] = []
    for result_row in results:
        analysis["results"].append(
            {
                "result_id": result_row["id"],
                "job_key": result_row["job_key"],
                "job": _json_loads(result_row["job_json"], {}),
                "match": _json_loads(result_row["match_json"], {}),
                "application_status": result_row["application_status"],
                "status_updated_at": result_row["status_updated_at"],
                "notes": result_row["notes"] or "",
                "cover_letter_text": result_row["cover_letter_text"],
                "adapted_cv_text": result_row["adapted_cv_text"],
                "documents_generated_at": result_row["documents_generated_at"],
            }
        )
    return analysis


def analysis_to_session_dict(stored: dict[str, Any]) -> dict[str, Any]:
    """Convert DB analysis row to the in-app analysis dict shape."""
    return {
        "analysis_id": stored["id"],
        "saved_at": stored["created_at"],
        "cv_text": stored["cv_text"],
        "extraction_method": stored["extraction_method"],
        "criteria": stored["criteria"],
        "user_profile": stored["user_profile"],
        "target_job_title": stored["target_job_title"],
        "search_plan": stored["search_plan"],
        "filter_stats": stored["filter_stats"],
        "jobs_found": stored["jobs_found"],
        "jobs_raw": stored["jobs_raw"],
        "search_strategy": stored.get("search_strategy"),
        "search_query_used": stored.get("search_query_used"),
        "job_provider": stored["job_provider"],
        "analysis_depth": stored.get("analysis_depth", "standard"),
        "results": [
            {
                "result_id": entry["result_id"],
                "job_key": entry["job_key"],
                "job": entry["job"],
                "match": entry["match"],
                "application_status": entry.get("application_status", "new"),
                "notes": entry.get("notes", ""),
                "cover_letter_text": entry.get("cover_letter_text"),
                "adapted_cv_text": entry.get("adapted_cv_text"),
            }
            for entry in stored["results"]
        ],
    }


def list_dashboard_results(
    user_id: int,
    *,
    analysis_id: int | None = None,
    status_filter: str | None = None,
    min_score: int = 0,
    max_score: int = 100,
    company_query: str = "",
    sort_by: str = "score_desc",
    limit: int = 200,
) -> list[dict[str, Any]]:
    init_persistence_tables()
    clauses = ["ar.user_id = ?", "ar.score >= ?", "ar.score <= ?"]
    params: list[Any] = [user_id, min_score, max_score]
    if analysis_id is not None:
        clauses.append("ar.analysis_id = ?")
        params.append(analysis_id)
    if status_filter and status_filter != "all":
        clauses.append("ar.application_status = ?")
        params.append(status_filter)
    if company_query.strip():
        clauses.append("LOWER(ar.job_json) LIKE ?")
        params.append(f"%{company_query.strip().lower()}%")

    order_map = {
        "score_desc": "ar.score DESC, a.created_at DESC",
        "score_asc": "ar.score ASC, a.created_at DESC",
        "date_desc": "a.created_at DESC, ar.score DESC",
        "date_asc": "a.created_at ASC, ar.score DESC",
        "company_asc": "ar.job_json ASC",
    }
    order_sql = order_map.get(sort_by, order_map["score_desc"])
    where_sql = " AND ".join(clauses)

    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT ar.id AS result_id, ar.analysis_id, ar.job_key, ar.job_json,
                       ar.match_json, ar.score, ar.application_status, ar.status_updated_at,
                       ar.notes, ar.cover_letter_text, ar.adapted_cv_text,
                       ar.documents_generated_at, a.created_at AS analysis_created_at,
                       a.target_job_title, a.job_provider
                FROM analysis_results ar
                JOIN analyses a ON a.id = ar.analysis_id
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ?
                """
            ),
            (*params, limit),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        job = _json_loads(row["job_json"], {})
        results.append(
            {
                "result_id": row["result_id"],
                "analysis_id": row["analysis_id"],
                "job_key": row["job_key"],
                "job": job,
                "match": _json_loads(row["match_json"], {}),
                "score": row["score"],
                "application_status": row["application_status"],
                "status_updated_at": row["status_updated_at"],
                "notes": row["notes"] or "",
                "cover_letter_text": row["cover_letter_text"],
                "adapted_cv_text": row["adapted_cv_text"],
                "documents_generated_at": row["documents_generated_at"],
                "analysis_created_at": row["analysis_created_at"],
                "target_job_title": row["target_job_title"],
                "job_provider": row["job_provider"],
            }
        )
    return results


def update_application_status(
    user_id: int,
    result_id: int,
    status: str,
    *,
    notes: str | None = None,
) -> bool:
    if status not in APPLICATION_STATUSES:
        return False
    init_persistence_tables()
    updated_at = utc_now_iso()
    with connect() as conn:
        if notes is None:
            cur = conn.execute(
                adapt_sql(
                    """
                    UPDATE analysis_results
                    SET application_status = ?, status_updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """
                ),
                (status, updated_at, result_id, user_id),
            )
        else:
            cur = conn.execute(
                adapt_sql(
                    """
                    UPDATE analysis_results
                    SET application_status = ?, status_updated_at = ?, notes = ?
                    WHERE id = ? AND user_id = ?
                    """
                ),
                (status, updated_at, notes, result_id, user_id),
            )
        return bool(getattr(cur, "rowcount", 0))


def record_application(
    user_id: int,
    result_id: int,
    method: str,
    *,
    status: str = "applied",
    notes: str | None = None,
) -> bool:
    """Persist how the user applied (manual vs automatic)."""
    if method not in APPLICATION_METHODS:
        return False
    if status not in APPLICATION_STATUSES:
        return False
    init_persistence_tables()
    updated_at = utc_now_iso()
    with connect() as conn:
        if notes is None:
            cur = conn.execute(
                adapt_sql(
                    """
                    UPDATE analysis_results
                    SET application_status = ?, status_updated_at = ?, application_method = ?
                    WHERE id = ? AND user_id = ?
                    """
                ),
                (status, updated_at, method, result_id, user_id),
            )
        else:
            cur = conn.execute(
                adapt_sql(
                    """
                    UPDATE analysis_results
                    SET application_status = ?, status_updated_at = ?, notes = ?,
                        application_method = ?
                    WHERE id = ? AND user_id = ?
                    """
                ),
                (status, updated_at, notes, method, result_id, user_id),
            )
        return bool(getattr(cur, "rowcount", 0))


def list_user_applications(user_id: int) -> list[dict[str, Any]]:
    """List job offers the user applied to (manual or automatic)."""
    init_persistence_tables()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT ar.id AS result_id, ar.analysis_id, ar.application_status,
                       ar.application_method, ar.status_updated_at, ar.notes,
                       ar.score, ar.job_json, ar.match_json,
                       a.target_job_title, a.created_at AS analysis_created_at
                FROM analysis_results ar
                INNER JOIN analyses a ON a.id = ar.analysis_id
                WHERE ar.user_id = ?
                  AND (
                    ar.application_method IS NOT NULL
                    OR ar.application_status IN (?, ?, ?)
                  )
                ORDER BY COALESCE(ar.status_updated_at, a.created_at) DESC
                """
            ),
            (user_id, *_APPLIED_HISTORY_STATUSES),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        job = _json_loads(row["job_json"], {})
        match = _json_loads(row["match_json"], {})
        method = row["application_method"]
        status = row["application_status"]
        if method in ("auto_email", "auto_prepared"):
            channel = "automatic"
        elif method == "manual" or status in _APPLIED_HISTORY_STATUSES:
            channel = "manual"
        else:
            continue
        results.append(
            {
                "result_id": row["result_id"],
                "analysis_id": row["analysis_id"],
                "application_status": status,
                "application_method": method,
                "channel": channel,
                "status_updated_at": row["status_updated_at"],
                "notes": row["notes"] or "",
                "score": row["score"],
                "job": job,
                "match": match,
                "target_job_title": row["target_job_title"],
                "analysis_created_at": row["analysis_created_at"],
            }
        )
    return results


def save_generated_documents(
    user_id: int,
    result_id: int,
    *,
    cover_letter_text: str | None = None,
    adapted_cv_text: str | None = None,
) -> bool:
    init_persistence_tables()
    generated_at = utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            adapt_sql(
                """
                UPDATE analysis_results
                SET cover_letter_text = COALESCE(?, cover_letter_text),
                    adapted_cv_text = COALESCE(?, adapted_cv_text),
                    documents_generated_at = ?
                WHERE id = ? AND user_id = ?
                """
            ),
            (cover_letter_text, adapted_cv_text, generated_at, result_id, user_id),
        )
        return bool(getattr(cur, "rowcount", 0))


def get_notification_settings(user_id: int) -> dict[str, Any]:
    init_persistence_tables()
    defaults = {
        "user_id": user_id,
        "email_alerts_enabled": False,
        "alert_min_score": 70,
        "alert_frequency": "after_search",
        "last_alert_sent_at": None,
        "auto_search_enabled": False,
        "auto_search_weekday": "daily",
        "auto_search_hour": 8,
        "auto_search_provider": "all",
        "auto_search_depth": "standard",
        "last_auto_search_at": None,
        "next_auto_search_at": None,
    }
    with connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT * FROM user_notification_settings WHERE user_id = ?"),
            (user_id,),
        ).fetchone()
    if not row:
        return defaults
    data = dict(row)
    data["email_alerts_enabled"] = bool(data.get("email_alerts_enabled"))
    data["auto_search_enabled"] = bool(data.get("auto_search_enabled"))
    return data


def save_notification_settings(user_id: int, settings: dict[str, Any]) -> None:
    init_persistence_tables()
    weekday = settings.get("auto_search_weekday", "daily")
    if weekday not in AUTO_SEARCH_WEEKDAYS:
        weekday = "daily"
    hour = max(0, min(23, int(settings.get("auto_search_hour", 8))))
    frequency = settings.get("alert_frequency", "after_search")
    if frequency not in _ALERT_FREQUENCIES:
        frequency = "after_search"
    next_run = compute_next_auto_search_at(weekday, hour)

    with connect() as conn:
        existing = conn.execute(
            adapt_sql("SELECT user_id FROM user_notification_settings WHERE user_id = ?"),
            (user_id,),
        ).fetchone()
        values = (
            1 if settings.get("email_alerts_enabled") else 0,
            max(0, min(100, int(settings.get("alert_min_score", 70)))),
            frequency,
            1 if settings.get("auto_search_enabled") else 0,
            weekday,
            hour,
            str(settings.get("auto_search_provider", "all")),
            str(settings.get("auto_search_depth", "standard")),
            next_run,
            user_id,
        )
        if existing:
            conn.execute(
                adapt_sql(
                    """
                    UPDATE user_notification_settings SET
                        email_alerts_enabled = ?,
                        alert_min_score = ?,
                        alert_frequency = ?,
                        auto_search_enabled = ?,
                        auto_search_weekday = ?,
                        auto_search_hour = ?,
                        auto_search_provider = ?,
                        auto_search_depth = ?,
                        next_auto_search_at = ?
                    WHERE user_id = ?
                    """
                ),
                values,
            )
        else:
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO user_notification_settings (
                        email_alerts_enabled, alert_min_score, alert_frequency,
                        auto_search_enabled, auto_search_weekday, auto_search_hour,
                        auto_search_provider, auto_search_depth, next_auto_search_at,
                        user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                values,
            )


def compute_next_auto_search_at(weekday: str, hour: int, *, from_dt: datetime | None = None) -> str:
    """Compute next scheduled run (UTC) for weekday + hour."""
    reference = from_dt or datetime.now(timezone.utc)
    candidate = reference.replace(hour=hour, minute=0, second=0, microsecond=0)
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    if weekday == "daily":
        if candidate <= reference:
            candidate += timedelta(days=1)
        return candidate.isoformat()

    target = weekday_map.get(weekday, 0)
    days_ahead = (target - candidate.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate <= reference:
        candidate += timedelta(days=7)
    return candidate.isoformat()


def is_auto_search_due(settings: dict[str, Any]) -> bool:
    if not settings.get("auto_search_enabled"):
        return False
    next_at = settings.get("next_auto_search_at")
    if not next_at:
        return True
    try:
        due = datetime.fromisoformat(next_at)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= due
    except ValueError:
        return True


def mark_auto_search_completed(user_id: int, weekday: str, hour: int) -> None:
    init_persistence_tables()
    now = utc_now_iso()
    next_run = compute_next_auto_search_at(weekday, hour)
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE user_notification_settings
                SET last_auto_search_at = ?, next_auto_search_at = ?
                WHERE user_id = ?
                """
            ),
            (now, next_run, user_id),
        )


def log_scheduled_run(
    user_id: int,
    status: str,
    *,
    analysis_id: int | None = None,
    error_message: str = "",
    trigger_source: str = "cron",
) -> int:
    init_persistence_tables()
    started_at = utc_now_iso()
    finished_at = utc_now_iso() if status != "running" else None
    with connect() as conn:
        cur = conn.execute(
            adapt_sql(
                """
                INSERT INTO scheduled_runs (
                    user_id, started_at, finished_at, status, analysis_id,
                    error_message, trigger_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            ),
            (user_id, started_at, finished_at, status, analysis_id, error_message, trigger_source),
        )
        run_id = int(getattr(cur, "lastrowid", 0) or 0)
    return run_id


def get_users_due_for_auto_search() -> list[dict[str, Any]]:
    init_persistence_tables()
    now = utc_now_iso()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT uns.user_id, uns.auto_search_weekday, uns.auto_search_hour,
                       uns.auto_search_provider, uns.auto_search_depth, u.email, u.full_name
                FROM user_notification_settings uns
                JOIN users u ON u.id = uns.user_id
                WHERE uns.auto_search_enabled = 1
                  AND (uns.next_auto_search_at IS NULL OR uns.next_auto_search_at <= ?)
                """
            ),
            (now,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_high_score_results_since(
    user_id: int,
    min_score: int,
    since_iso: str | None,
) -> list[dict[str, Any]]:
    init_persistence_tables()
    clauses = ["ar.user_id = ?", "ar.score >= ?"]
    params: list[Any] = [user_id, min_score]
    if since_iso:
        clauses.append("a.created_at > ?")
        params.append(since_iso)
    where_sql = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT ar.score, ar.job_json, ar.match_json, a.created_at, a.target_job_title
                FROM analysis_results ar
                JOIN analyses a ON a.id = ar.analysis_id
                WHERE {where_sql}
                ORDER BY ar.score DESC
                LIMIT 20
                """
            ),
            tuple(params),
        ).fetchall()
    return [
        {
            "score": row["score"],
            "job": _json_loads(row["job_json"], {}),
            "match": _json_loads(row["match_json"], {}),
            "created_at": row["created_at"],
            "target_job_title": row["target_job_title"],
        }
        for row in rows
    ]


def mark_alert_sent(user_id: int) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE user_notification_settings
                SET last_alert_sent_at = ?
                WHERE user_id = ?
                """
            ),
            (utc_now_iso(), user_id),
        )


def dashboard_status_counts(user_id: int, *, analysis_id: int | None = None) -> dict[str, int]:
    init_persistence_tables()
    counts = {status: 0 for status in APPLICATION_STATUSES}
    clauses = ["user_id = ?"]
    params: list[Any] = [user_id]
    if analysis_id is not None:
        clauses.append("analysis_id = ?")
        params.append(analysis_id)
    where_sql = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT application_status, COUNT(*) AS total
                FROM analysis_results
                WHERE {where_sql}
                GROUP BY application_status
                """
            ),
            tuple(params),
        ).fetchall()
    for row in rows:
        counts[row["application_status"]] = int(row["total"])
    counts["all"] = sum(counts.values())
    return counts
