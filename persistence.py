"""Persist analyses, job tracking, notification settings and CV documents."""

from __future__ import annotations

import hashlib
import json
import re
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

_SAFE_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Child rows first so foreign keys never block the users row.
_USER_OWNED_TABLES = (
    "analysis_results",
    "scheduled_runs",
    "analyses",
    "cv_documents",
    "user_notification_settings",
    "password_reset_tokens",
    "user_connected_accounts",
    "llm_usage",
    "support_messages",
    "user_profile_photos",
)

_PERSISTENCE_SCHEMA_KEY = (
    "analyses_v1",
    "analysis_results_v1",
    "user_notification_settings_v1",
    "scheduled_runs_v1",
    "cv_documents_v1",
    "user_connected_accounts_v2",
    "llm_usage_v1",
    "support_messages_v1",
    "user_profile_photos_v1",
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


def _create_user_connected_accounts_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_connected_accounts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                account_email TEXT NOT NULL DEFAULT '',
                profile_url TEXT NOT NULL DEFAULT '',
                connected_at TEXT NOT NULL,
                UNIQUE (user_id, provider)
            )
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_connected_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            account_email TEXT NOT NULL DEFAULT '',
            profile_url TEXT NOT NULL DEFAULT '',
            connected_at TEXT NOT NULL,
            UNIQUE (user_id, provider),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def _migrate_user_connected_accounts_columns(conn: Any) -> None:
    cols = existing_columns(conn, "user_connected_accounts")
    if not cols or "profile_url" in cols:
        return
    if database_backend() == "postgres":
        conn.execute(
            "ALTER TABLE user_connected_accounts ADD COLUMN IF NOT EXISTS profile_url TEXT NOT NULL DEFAULT ''"
        )
        return
    conn.execute(
        "ALTER TABLE user_connected_accounts ADD COLUMN profile_url TEXT NOT NULL DEFAULT ''"
    )


def _create_support_messages_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS support_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                sender_role TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT,
                admin_id INTEGER,
                admin_email TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS support_messages_user_created_idx
            ON support_messages (user_id, created_at ASC, id ASC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS support_messages_unread_idx
            ON support_messages (user_id, sender_role, read_at)
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            admin_id INTEGER,
            admin_email TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS support_messages_user_created_idx
        ON support_messages (user_id, created_at ASC, id ASC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS support_messages_unread_idx
        ON support_messages (user_id, sender_role, read_at)
        """
        )


def _create_user_profile_photos_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile_photos (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                mime_type TEXT NOT NULL,
                image_data BYTEA NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile_photos (
            user_id INTEGER PRIMARY KEY,
            mime_type TEXT NOT NULL,
            image_data BLOB NOT NULL,
            updated_at TEXT NOT NULL,
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
        _create_user_connected_accounts_table(conn)
        _migrate_user_connected_accounts_columns(conn)
        _create_support_messages_table(conn)
        _create_user_profile_photos_table(conn)
        from services.llm_usage import ensure_llm_usage_table

        ensure_llm_usage_table()
        _ = existing_columns(conn, "analyses")
    _persistence_initialized_for = _PERSISTENCE_SCHEMA_KEY


def _table_exists(conn: Any, table: str) -> bool:
    if not _SAFE_TABLE_NAME.match(table):
        return False
    if database_backend() == "postgres":
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        ).fetchone()
        return bool(row)
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _tables_with_user_id_column(conn: Any) -> list[str]:
    names: list[str] = []
    if database_backend() == "postgres":
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'user_id'
            """
        ).fetchall()
        for row in rows:
            name = str(row["table_name"])
            if _SAFE_TABLE_NAME.match(name):
                names.append(name)
        return names
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for row in rows:
        name = str(row["name"])
        if not _SAFE_TABLE_NAME.match(name):
            continue
        if "user_id" in existing_columns(conn, name):
            names.append(name)
    return names


def delete_all_user_data(conn: Any, user_id: int) -> None:
    """Erase every row owned by this user. Caller must then delete the users row."""
    deleted: set[str] = set()
    for table in _USER_OWNED_TABLES:
        if not _table_exists(conn, table):
            continue
        conn.execute(adapt_sql(f"DELETE FROM {table} WHERE user_id = ?"), (user_id,))
        deleted.add(table)
    for table in _tables_with_user_id_column(conn):
        if table in deleted or table == "users":
            continue
        conn.execute(adapt_sql(f"DELETE FROM {table} WHERE user_id = ?"), (user_id,))


def _delete_users_by_id_or_email(conn: Any, user_id: int, email: str) -> None:
    conn.execute(adapt_sql("DELETE FROM users WHERE id = ?"), (user_id,))
    cleaned = (email or "").strip()
    if cleaned:
        conn.execute(
            adapt_sql("DELETE FROM users WHERE LOWER(email) = LOWER(?)"),
            (cleaned,),
        )


def release_user_identity(conn: Any, user_id: int, email: str) -> None:
    """Remove owned rows and the users identity so the e-mail can be registered again."""
    delete_all_user_data(conn, user_id)
    try:
        _delete_users_by_id_or_email(conn, user_id, email)
    except Exception:
        if database_backend() != "sqlite":
            raise
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            delete_all_user_data(conn, user_id)
            _delete_users_by_id_or_email(conn, user_id, email)
        finally:
            conn.execute("PRAGMA foreign_keys = ON")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default if default is not None else {}


_JSON_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _sql_json_text(column: str, key: str) -> str:
    """SQL snippet that reads a top-level JSON string field on SQLite and Postgres."""
    if not _JSON_KEY_RE.match(key) or not _JSON_KEY_RE.match(column.replace(".", "_")):
        raise ValueError("invalid json extract identifier")
    if database_backend() == "postgres":
        return f"({column}::json)->>'{key}'"
    return f"json_extract({column}, '$.{key}')"


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def job_card_preview(job: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only the fields needed to render a collapsed job card."""
    data = job or {}
    return {
        "title": data.get("title") or "",
        "company": data.get("company") or "",
        "location": data.get("location") or "",
        "url": data.get("url") or "",
        "source": data.get("source") or "",
        "published_at": data.get("published_at") or "",
        "contract_type": data.get("contract_type") or "",
        "inferred_contract": data.get("inferred_contract") or "",
    }


def match_card_preview(
    match: dict[str, Any] | None,
    *,
    score: int | None = None,
) -> dict[str, Any]:
    """Keep ATS scores and summary; drop skill/experience blobs until details open."""
    data = match or {}
    preview_score = _optional_int(data.get("score_correspondance"))
    if preview_score is None:
        preview_score = int(score or 0)

    def _score_field(key: str) -> int:
        value = _optional_int(data.get(key))
        return preview_score if value is None else value

    return {
        "score_correspondance": preview_score,
        "score_competences": _score_field("score_competences"),
        "score_experiences": _score_field("score_experiences"),
        "score_titre": _score_field("score_titre"),
        "score_localisation": _score_field("score_localisation"),
        "synthese_ats": data.get("synthese_ats") or "",
        "titre_cv_recommande": data.get("titre_cv_recommande") or "",
    }


def _job_preview_from_row(row: Any) -> dict[str, Any]:
    return {
        "title": row["job_title"] or "",
        "company": row["job_company"] or "",
        "location": row["job_location"] or "",
        "url": row["job_url"] or "",
        "source": row["job_source"] or "",
        "published_at": row["job_published_at"] or "",
        "contract_type": row["job_contract_type"] or "",
        "inferred_contract": row["job_inferred_contract"] or "",
    }


def _match_preview_from_row(row: Any) -> dict[str, Any]:
    score = int(row["score"] or 0)

    def _score_field(column: str) -> int:
        value = _optional_int(row[column])
        return score if value is None else value

    return {
        "score_correspondance": score,
        "score_competences": _score_field("match_score_competences"),
        "score_experiences": _score_field("match_score_experiences"),
        "score_titre": _score_field("match_score_titre"),
        "score_localisation": _score_field("match_score_localisation"),
        "synthese_ats": row["match_synthese_ats"] or "",
        "titre_cv_recommande": row["match_titre_cv_recommande"] or "",
    }


def _analysis_result_select_preview_sql() -> str:
    job = "ar.job_json"
    match = "ar.match_json"
    return f"""
        {_sql_json_text(job, "title")} AS job_title,
        {_sql_json_text(job, "company")} AS job_company,
        {_sql_json_text(job, "location")} AS job_location,
        {_sql_json_text(job, "url")} AS job_url,
        {_sql_json_text(job, "source")} AS job_source,
        {_sql_json_text(job, "published_at")} AS job_published_at,
        {_sql_json_text(job, "contract_type")} AS job_contract_type,
        {_sql_json_text(job, "inferred_contract")} AS job_inferred_contract,
        {_sql_json_text(match, "score_competences")} AS match_score_competences,
        {_sql_json_text(match, "score_experiences")} AS match_score_experiences,
        {_sql_json_text(match, "score_titre")} AS match_score_titre,
        {_sql_json_text(match, "score_localisation")} AS match_score_localisation,
        {_sql_json_text(match, "synthese_ats")} AS match_synthese_ats,
        {_sql_json_text(match, "titre_cv_recommande")} AS match_titre_cv_recommande
    """


def _row_to_analysis_result(row: Any) -> dict[str, Any]:
    return {
        "result_id": row["result_id"],
        "analysis_id": row["analysis_id"],
        "job_key": row["job_key"] if "job_key" in row.keys() else "",
        "job": _json_loads(row["job_json"], {}),
        "match": _json_loads(row["match_json"], {}),
        "score": row["score"],
        "application_status": row["application_status"],
        "status_updated_at": row["status_updated_at"],
        "notes": row["notes"] or "",
        "cover_letter_text": row["cover_letter_text"],
        "adapted_cv_text": row["adapted_cv_text"],
        "documents_generated_at": row["documents_generated_at"]
        if "documents_generated_at" in row.keys()
        else None,
    }


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


_ACCOUNT_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SITE_USERNAME_RE = re.compile(r"^[\w.+-]{3,80}$")
MIN_SITE_PASSWORD_LEN = 8


def _normalize_site_login(account_login: str) -> str:
    raw = (account_login or "").strip()
    if "@" in raw:
        return raw.lower()
    return raw


def _is_valid_site_login(account_login: str) -> bool:
    if not account_login:
        return False
    if "@" in account_login:
        return bool(_ACCOUNT_EMAIL_RE.match(account_login))
    return bool(_SITE_USERNAME_RE.match(account_login))


def _is_complete_site_password(site_password: str) -> bool:
    return len((site_password or "").strip()) >= MIN_SITE_PASSWORD_LEN


def _normalize_profile_url(profile_url: str) -> str:
    return (profile_url or "").strip()[:500]


def list_connected_job_accounts(user_id: int) -> list[dict[str, Any]]:
    init_persistence_tables()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT provider, account_email, profile_url, connected_at
                FROM user_connected_accounts
                WHERE user_id = ?
                ORDER BY provider
                """
            ),
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_connected_job_account(user_id: int, provider: str) -> dict[str, Any] | None:
    init_persistence_tables()
    key = (provider or "").strip().lower()
    if not key:
        return None
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT provider, account_email, profile_url, connected_at
                FROM user_connected_accounts
                WHERE user_id = ? AND provider = ?
                LIMIT 1
                """
            ),
            (user_id, key),
        ).fetchone()
    return dict(row) if row else None


def connect_job_account(
    user_id: int,
    provider: str,
    account_email: str,
    *,
    has_existing_account: bool = False,
    site_password: str = "",
    site_password_confirm: str | None = None,
    profile_url: str = "",
) -> tuple[bool, str]:
    """Link the candidate DowsonBost account to an existing job-board account.

    The job-board password is required to complete the link and is never stored.
    Incomplete or mismatched credentials fail the connection.
    """
    from i18n import t
    from job_providers import CONNECTABLE_JOB_PROVIDERS, job_board_display_name

    key = (provider or "").strip().lower()
    login = _normalize_site_login(account_email)
    url = _normalize_profile_url(profile_url)
    if key not in CONNECTABLE_JOB_PROVIDERS:
        return False, t("accounts.unknown_provider")
    name = job_board_display_name(key)
    if not has_existing_account:
        return False, t("accounts.not_created", name=name)
    if not _is_valid_site_login(login) or not _is_complete_site_password(site_password):
        return False, t("accounts.login_failed", name=name)
    if site_password_confirm is not None and site_password != site_password_confirm:
        return False, t("accounts.login_mismatch", name=name)
    init_persistence_tables()
    now = utc_now_iso()
    with connect() as conn:
        existing = conn.execute(
            adapt_sql(
                "SELECT id FROM user_connected_accounts WHERE user_id = ? AND provider = ?"
            ),
            (user_id, key),
        ).fetchone()
        if existing:
            conn.execute(
                adapt_sql(
                    """
                    UPDATE user_connected_accounts
                    SET account_email = ?, profile_url = ?, connected_at = ?
                    WHERE user_id = ? AND provider = ?
                    """
                ),
                (login, url, now, user_id, key),
            )
        else:
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO user_connected_accounts (
                        user_id, provider, account_email, profile_url, connected_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """
                ),
                (user_id, key, login, url, now),
            )
    return True, t("accounts.connected", name=job_board_display_name(key))


def connect_all_job_accounts(
    user_id: int,
    account_email: str,
    *,
    has_existing_account: bool = False,
    site_password: str = "",
) -> tuple[bool, str, int]:
    """Link every supported job board with the same login (skip already linked)."""
    from i18n import t
    from job_providers import CONNECTABLE_JOB_PROVIDERS

    if not has_existing_account:
        return False, t("accounts.not_created_all"), 0
    login = _normalize_site_login(account_email)
    if not _is_valid_site_login(login) or not _is_complete_site_password(site_password):
        return False, t("accounts.login_failed_all"), 0
    already = {row["provider"] for row in list_connected_job_accounts(user_id)}
    linked_now = 0
    for provider in CONNECTABLE_JOB_PROVIDERS:
        if provider in already:
            continue
        ok, _message = connect_job_account(
            user_id,
            provider,
            login,
            has_existing_account=True,
            site_password=site_password,
        )
        if ok:
            linked_now += 1
    if linked_now == 0 and already:
        return True, t("accounts.already_all_connected"), 0
    return True, t("accounts.connected_all", count=linked_now, email=login), linked_now


def disconnect_job_account(user_id: int, provider: str) -> tuple[bool, str]:
    from i18n import t
    from job_providers import job_board_display_name

    key = (provider or "").strip().lower()
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                "DELETE FROM user_connected_accounts WHERE user_id = ? AND provider = ?"
            ),
            (user_id, key),
        )
    return True, t("accounts.disconnected", name=job_board_display_name(key))


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


def get_analysis_apply_context(user_id: int, analysis_id: int) -> dict[str, Any] | None:
    """Load only the CV and profile snapshot needed for apply actions."""
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT cv_text, user_profile_snapshot
                FROM analyses
                WHERE id = ? AND user_id = ?
                """
            ),
            (analysis_id, user_id),
        ).fetchone()
    if not row:
        return None
    return {
        "cv_text": row["cv_text"] or "",
        "user_profile": _json_loads(row["user_profile_snapshot"], {}),
    }


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
                "job": job_card_preview(entry.get("job")),
                "match": match_card_preview(
                    entry.get("match"),
                    score=entry.get("match", {}).get("score_correspondance")
                    if isinstance(entry.get("match"), dict)
                    else None,
                ),
                "application_status": entry.get("application_status", "new"),
                "notes": entry.get("notes", ""),
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
    company_sql = _sql_json_text("ar.job_json", "company")
    if company_query.strip():
        clauses.append(f"LOWER(COALESCE({company_sql}, '')) LIKE ?")
        params.append(f"%{company_query.strip().lower()}%")

    order_map = {
        "score_desc": "ar.score DESC, a.created_at DESC",
        "score_asc": "ar.score ASC, a.created_at DESC",
        "date_desc": "a.created_at DESC, ar.score DESC",
        "date_asc": "a.created_at ASC, ar.score DESC",
        "company_asc": f"LOWER(COALESCE({company_sql}, '')) ASC",
    }
    order_sql = order_map.get(sort_by, order_map["score_desc"])
    where_sql = " AND ".join(clauses)
    preview_sql = _analysis_result_select_preview_sql()

    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT ar.id AS result_id, ar.analysis_id, ar.job_key,
                       ar.score, ar.application_status, ar.status_updated_at,
                       ar.notes, ar.documents_generated_at, a.created_at AS analysis_created_at,
                       a.target_job_title, a.job_provider,
                       {preview_sql}
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
        results.append(
            {
                "result_id": row["result_id"],
                "analysis_id": row["analysis_id"],
                "job_key": row["job_key"],
                "job": _job_preview_from_row(row),
                "match": _match_preview_from_row(row),
                "score": row["score"],
                "application_status": row["application_status"],
                "status_updated_at": row["status_updated_at"],
                "notes": row["notes"] or "",
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
                f"""
                SELECT ar.id AS result_id, ar.analysis_id, ar.application_status,
                       ar.application_method, ar.status_updated_at, ar.notes,
                       ar.score, a.target_job_title, a.created_at AS analysis_created_at,
                       {_analysis_result_select_preview_sql()}
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
                "job": _job_preview_from_row(row),
                "match": _match_preview_from_row(row),
                "target_job_title": row["target_job_title"],
                "analysis_created_at": row["analysis_created_at"],
            }
        )
    return results


def count_user_applications(user_id: int) -> int:
    """Count job offers the user applied to without loading JSON payloads."""
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT COUNT(*) AS total
                FROM analysis_results ar
                WHERE ar.user_id = ?
                  AND (
                    ar.application_method IS NOT NULL
                    OR ar.application_status IN (?, ?, ?)
                  )
                """
            ),
            (user_id, *_APPLIED_HISTORY_STATUSES),
        ).fetchone()
    return int((row["total"] if row else 0) or 0)


def get_application_result(user_id: int, result_id: int) -> dict[str, Any] | None:
    """Fetch one application entry with job, match, and generated documents."""
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT ar.id AS result_id, ar.analysis_id, ar.application_status,
                       ar.application_method, ar.status_updated_at, ar.notes,
                       ar.score, ar.job_json, ar.match_json,
                       ar.cover_letter_text, ar.adapted_cv_text,
                       a.target_job_title, a.created_at AS analysis_created_at
                FROM analysis_results ar
                INNER JOIN analyses a ON a.id = ar.analysis_id
                WHERE ar.user_id = ? AND ar.id = ?
                """
            ),
            (user_id, result_id),
        ).fetchone()
    if not row:
        return None
    method = row["application_method"]
    status = row["application_status"]
    if method in ("auto_email", "auto_prepared"):
        channel = "automatic"
    elif method == "manual" or status in _APPLIED_HISTORY_STATUSES:
        channel = "manual"
    else:
        return None
    return {
        "result_id": row["result_id"],
        "analysis_id": row["analysis_id"],
        "application_status": status,
        "application_method": method,
        "channel": channel,
        "status_updated_at": row["status_updated_at"],
        "notes": row["notes"] or "",
        "score": row["score"],
        "job": _json_loads(row["job_json"], {}),
        "match": _json_loads(row["match_json"], {}),
        "target_job_title": row["target_job_title"],
        "analysis_created_at": row["analysis_created_at"],
        "cover_letter_text": row["cover_letter_text"],
        "adapted_cv_text": row["adapted_cv_text"],
    }


def get_analysis_result(user_id: int, result_id: int) -> dict[str, Any] | None:
    """Load one job result with full job, match, and generated documents."""
    payloads = get_analysis_results_by_ids(user_id, [result_id])
    return payloads.get(int(result_id))


def get_analysis_results_by_ids(
    user_id: int,
    result_ids: list[int],
) -> dict[int, dict[str, Any]]:
    """Batch-load full analysis results for expanded cards or apply actions."""
    ids = [int(item) for item in result_ids if item]
    if not ids:
        return {}
    init_persistence_tables()
    placeholders = ", ".join("?" for _ in ids)
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                f"""
                SELECT ar.id AS result_id, ar.analysis_id, ar.job_key, ar.job_json,
                       ar.match_json, ar.score, ar.application_status, ar.status_updated_at,
                       ar.notes, ar.cover_letter_text, ar.adapted_cv_text,
                       ar.documents_generated_at
                FROM analysis_results ar
                WHERE ar.user_id = ? AND ar.id IN ({placeholders})
                """
            ),
            (user_id, *ids),
        ).fetchall()
    return {int(row["result_id"]): _row_to_analysis_result(row) for row in rows}


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


def _support_message_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "sender_role": str(row["sender_role"] or ""),
        "body": str(row["body"] or ""),
        "created_at": str(row["created_at"] or ""),
        "read_at": row["read_at"],
        "admin_id": int(row["admin_id"]) if row["admin_id"] is not None else None,
        "admin_email": str(row["admin_email"] or ""),
    }


def insert_support_message(
    user_id: int,
    sender_role: str,
    body: str,
    *,
    admin_id: int | None = None,
    admin_email: str = "",
) -> dict[str, Any]:
    init_persistence_tables()
    created_at = utc_now_iso()
    with connect() as conn:
        if database_backend() == "postgres":
            row = conn.execute(
                adapt_sql(
                    """
                    INSERT INTO support_messages
                        (user_id, sender_role, body, created_at, admin_id, admin_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    RETURNING id, user_id, sender_role, body, created_at, read_at, admin_id, admin_email
                    """
                ),
                (user_id, sender_role, body, created_at, admin_id, admin_email),
            ).fetchone()
            return _support_message_from_row(row)
        cur = conn.execute(
            adapt_sql(
                """
                INSERT INTO support_messages
                    (user_id, sender_role, body, created_at, admin_id, admin_email)
                VALUES (?, ?, ?, ?, ?, ?)
                """
            ),
            (user_id, sender_role, body, created_at, admin_id, admin_email),
        )
        msg_id = int(cur.lastrowid)
    return {
        "id": msg_id,
        "user_id": int(user_id),
        "sender_role": sender_role,
        "body": body,
        "created_at": created_at,
        "read_at": None,
        "admin_id": admin_id,
        "admin_email": admin_email,
    }


def list_support_thread(user_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
    init_persistence_tables()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT id, user_id, sender_role, body, created_at, read_at, admin_id, admin_email
                FROM support_messages
                WHERE user_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """
            ),
            (user_id, limit),
        ).fetchall()
    return [_support_message_from_row(row) for row in rows]


def count_unread_support_messages(user_id: int, *, incoming_role: str) -> int:
    """Unread messages in a thread whose sender_role matches incoming_role."""
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT COUNT(*) AS total
                FROM support_messages
                WHERE user_id = ? AND sender_role = ? AND read_at IS NULL
                """
            ),
            (user_id, incoming_role),
        ).fetchone()
    return int((row["total"] if row else 0) or 0)


def count_admin_unread_support() -> int:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT COUNT(*) AS total
                FROM support_messages
                WHERE sender_role = 'user' AND read_at IS NULL
                """
            )
        ).fetchone()
    return int((row["total"] if row else 0) or 0)


def mark_support_thread_read(user_id: int, *, incoming_role: str) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE support_messages
                SET read_at = ?
                WHERE user_id = ? AND sender_role = ? AND read_at IS NULL
                """
            ),
            (utc_now_iso(), user_id, incoming_role),
        )


def list_support_conversations() -> list[dict[str, Any]]:
    """One private chat space per registered candidate, newest activity first."""
    init_persistence_tables()
    with connect() as conn:
        rows = conn.execute(
            adapt_sql(
                """
                SELECT u.id AS user_id,
                       u.full_name,
                       u.email,
                       last_msg.body AS last_body,
                       last_msg.created_at AS last_at,
                       last_msg.sender_role AS last_role,
                       COALESCE(unread.total, 0) AS unread
                FROM users u
                LEFT JOIN (
                    SELECT user_id, MAX(id) AS last_id
                    FROM support_messages
                    GROUP BY user_id
                ) latest ON latest.user_id = u.id
                LEFT JOIN support_messages last_msg ON last_msg.id = latest.last_id
                LEFT JOIN (
                    SELECT user_id, COUNT(*) AS total
                    FROM support_messages
                    WHERE sender_role = 'user' AND read_at IS NULL
                    GROUP BY user_id
                ) unread ON unread.user_id = u.id
                ORDER BY COALESCE(unread.total, 0) DESC,
                         CASE WHEN last_msg.created_at IS NULL THEN 1 ELSE 0 END,
                         last_msg.created_at DESC,
                         LOWER(u.full_name) ASC
                """
            )
        ).fetchall()
    conversations: list[dict[str, Any]] = []
    for row in rows:
        last_body = str(row["last_body"] or "")
        last_at = str(row["last_at"] or "")
        conversations.append(
            {
                "user_id": int(row["user_id"]),
                "full_name": str(row["full_name"] or ""),
                "email": str(row["email"] or ""),
                "last_body": last_body,
                "last_at": last_at,
                "last_role": str(row["last_role"] or ""),
                "unread": int(row["unread"] or 0),
                "has_messages": bool(last_at),
            }
        )
    return conversations


def _photo_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    return bytes(value)


def upsert_user_profile_photo(user_id: int, mime_type: str, image_data: bytes) -> None:
    init_persistence_tables()
    updated_at = utc_now_iso()
    with connect() as conn:
        if database_backend() == "postgres":
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO user_profile_photos (user_id, mime_type, image_data, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (user_id) DO UPDATE SET
                        mime_type = EXCLUDED.mime_type,
                        image_data = EXCLUDED.image_data,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                (int(user_id), mime_type, image_data, updated_at),
            )
            return
        conn.execute(
            adapt_sql(
                """
                INSERT INTO user_profile_photos (user_id, mime_type, image_data, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mime_type = excluded.mime_type,
                    image_data = excluded.image_data,
                    updated_at = excluded.updated_at
                """
            ),
            (int(user_id), mime_type, image_data, updated_at),
        )


def get_user_profile_photo(user_id: int) -> dict[str, Any] | None:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT user_id, mime_type, image_data, updated_at
                FROM user_profile_photos
                WHERE user_id = ?
                """
            ),
            (int(user_id),),
        ).fetchone()
    if not row:
        return None
    data = _photo_bytes(row["image_data"])
    if not data:
        return None
    return {
        "user_id": int(row["user_id"]),
        "mime_type": str(row["mime_type"] or "image/jpeg"),
        "image_data": data,
        "updated_at": str(row["updated_at"] or ""),
    }


def delete_user_profile_photo(user_id: int) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql("DELETE FROM user_profile_photos WHERE user_id = ?"),
            (int(user_id),),
        )


def user_has_profile_photo(user_id: int) -> bool:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT 1 AS present FROM user_profile_photos WHERE user_id = ?"),
            (int(user_id),),
        ).fetchone()
    return bool(row)

