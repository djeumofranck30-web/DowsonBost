"""Durable CV-analysis queue (SQLite / Postgres). No Redis required."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from constants import (
    ANALYSIS_DEPTH_POOL,
    ANALYSIS_DEPTH_TOP,
    ANALYSIS_JOB_MAX_PDF_BYTES,
    ANALYSIS_JOB_STALE_SECONDS,
)
from database import adapt_sql, connect, database_backend
from persistence import init_persistence_tables, utc_now_iso

ACTIVE_JOB_STATUSES = ("queued", "running")
JOB_STATUSES = ("queued", "running", "completed", "failed")


def _row_to_job(row: Any) -> dict[str, Any]:
    mapping = dict(row)
    blob = mapping.get("pdf_blob")
    if blob is not None and not isinstance(blob, (bytes, bytearray)):
        mapping["pdf_blob"] = bytes(blob)
    elif isinstance(blob, bytearray):
        mapping["pdf_blob"] = bytes(blob)
    return mapping


def get_analysis_job(job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    init_persistence_tables()
    clauses = ["id = ?"]
    params: list[Any] = [int(job_id)]
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(int(user_id))
    sql = f"SELECT * FROM analysis_jobs WHERE {' AND '.join(clauses)} LIMIT 1"
    with connect() as conn:
        row = conn.execute(adapt_sql(sql), tuple(params)).fetchone()
    return _row_to_job(row) if row else None


def get_active_analysis_job(user_id: int) -> dict[str, Any] | None:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT * FROM analysis_jobs
                WHERE user_id = ? AND status IN ('queued', 'running')
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            (int(user_id),),
        ).fetchone()
    return _row_to_job(row) if row else None


def get_latest_analysis_job(user_id: int) -> dict[str, Any] | None:
    init_persistence_tables()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT * FROM analysis_jobs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            (int(user_id),),
        ).fetchone()
    return _row_to_job(row) if row else None


def enqueue_analysis_job(
    user_id: int,
    user_profile: dict[str, Any],
    *,
    job_provider: str,
    analysis_depth: str,
    cv_fingerprint: str,
    pdf_bytes: bytes | None = None,
    cv_text: str | None = None,
    extraction_method: str = "native",
    trigger_source: str = "ui",
) -> tuple[int | None, str]:
    """Store a ticket. Returns (job_id, error). error 'already' if one is active."""
    init_persistence_tables()
    active = get_active_analysis_job(user_id)
    if active:
        return int(active["id"]), "already"

    depth = analysis_depth if analysis_depth in ANALYSIS_DEPTH_POOL else "standard"
    pdf = bytes(pdf_bytes) if pdf_bytes else None
    text = (cv_text or "").strip()
    if pdf and len(pdf) > ANALYSIS_JOB_MAX_PDF_BYTES:
        return None, "pdf_too_large"
    if not pdf and not text:
        return None, "missing_cv"

    now = utc_now_iso()
    values = (
        int(user_id),
        now,
        str(job_provider or "all"),
        depth,
        int(ANALYSIS_DEPTH_POOL[depth]),
        int(ANALYSIS_DEPTH_TOP[depth]),
        str(cv_fingerprint or ""),
        text or None,
        extraction_method or "native",
        pdf,
        json.dumps(user_profile, ensure_ascii=False),
        trigger_source if trigger_source in {"ui", "auto"} else "ui",
        "En file d'attente",
    )
    insert_sql = """
        INSERT INTO analysis_jobs (
            user_id, status, created_at, job_provider, analysis_depth,
            matching_pool, matching_top, cv_fingerprint, cv_text,
            extraction_method, pdf_blob, user_profile_json, trigger_source,
            progress_percent, progress_label
        ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """
    with connect() as conn:
        if database_backend() == "postgres":
            row = conn.execute(
                insert_sql.replace("?", "%s") + " RETURNING id",
                values,
            ).fetchone()
            job_id = int(row["id"]) if row else 0
        else:
            cursor = conn.execute(insert_sql, values)
            job_id = int(cursor.lastrowid or 0)
    if job_id <= 0:
        return None, "enqueue_failed"
    return job_id, ""


def update_analysis_job_progress(job_id: int, percent: int, label: str) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE analysis_jobs
                SET progress_percent = ?, progress_label = ?
                WHERE id = ? AND status = 'running'
                """
            ),
            (max(0, min(99, int(percent))), str(label or "")[:240], int(job_id)),
        )


def complete_analysis_job(
    job_id: int,
    *,
    analysis_id: int,
    notices: list[dict[str, str]],
) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE analysis_jobs
                SET status = 'completed',
                    finished_at = ?,
                    progress_percent = 100,
                    progress_label = ?,
                    analysis_id = ?,
                    notices_json = ?,
                    pdf_blob = NULL,
                    error_message = NULL
                WHERE id = ?
                """
            ),
            (
                utc_now_iso(),
                "Analyse terminée",
                int(analysis_id),
                json.dumps(notices, ensure_ascii=False),
                int(job_id),
            ),
        )


def fail_analysis_job(job_id: int, error: str, notices: list[dict[str, str]] | None = None) -> None:
    init_persistence_tables()
    with connect() as conn:
        conn.execute(
            adapt_sql(
                """
                UPDATE analysis_jobs
                SET status = 'failed',
                    finished_at = ?,
                    progress_percent = 100,
                    progress_label = ?,
                    error_message = ?,
                    notices_json = ?,
                    pdf_blob = NULL
                WHERE id = ?
                """
            ),
            (
                utc_now_iso(),
                "Analyse en échec",
                str(error or "Analyse impossible")[:800],
                json.dumps(notices or [], ensure_ascii=False),
                int(job_id),
            ),
        )


def _requeue_stale_jobs(conn: Any) -> None:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=ANALYSIS_JOB_STALE_SECONDS)
    ).replace(microsecond=0).isoformat()
    conn.execute(
        adapt_sql(
            """
            UPDATE analysis_jobs
            SET status = 'queued',
                started_at = NULL,
                progress_percent = 0,
                progress_label = 'Relancé après interruption'
            WHERE status = 'running'
              AND started_at IS NOT NULL
              AND started_at < ?
            """
        ),
        (cutoff,),
    )


def claim_next_analysis_job() -> dict[str, Any] | None:
    """Atomically take the oldest queued ticket. Safe for several workers."""
    init_persistence_tables()
    now = utc_now_iso()
    if database_backend() == "postgres":
        with connect() as conn:
            _requeue_stale_jobs(conn)
            row = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'running',
                    started_at = %s,
                    progress_percent = 1,
                    progress_label = 'Démarrage…'
                WHERE id = (
                    SELECT id FROM analysis_jobs
                    WHERE status = 'queued'
                    ORDER BY id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
                """,
                (now,),
            ).fetchone()
        return _row_to_job(row) if row else None

    with connect() as conn:
        _requeue_stale_jobs(conn)
        pending = conn.execute(
            "SELECT id FROM analysis_jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if not pending:
            return None
        job_id = int(pending["id"])
        updated = conn.execute(
            """
            UPDATE analysis_jobs
            SET status = 'running',
                started_at = ?,
                progress_percent = 1,
                progress_label = 'Démarrage…'
            WHERE id = ? AND status = 'queued'
            """,
            (now, job_id),
        )
        if int(getattr(updated, "rowcount", 0) or 0) == 0:
            return None
        row = conn.execute(
            "SELECT * FROM analysis_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return _row_to_job(row) if row else None
