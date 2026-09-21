"""Journal d'activité et alertes pour l'espace administrateur.

Toute action candidate (connexion, analyse, candidature, support…) est
enregistrée. Les incidents (échec d'analyse, blocage, quota IA / SerpAPI)
apparaissent comme alertes non lues jusqu'à ce qu'un administrateur les
marque comme lues.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from database import adapt_sql, connect, database_backend
from observability import get_logger
from persistence import utc_now_iso

logger = get_logger(__name__)

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
ALERT_SEVERITIES = (SEVERITY_WARNING, SEVERITY_ERROR)
DEDUP_MINUTES = 20

KIND_LABELS: dict[str, str] = {
    "user.register": "Inscription",
    "user.login": "Connexion",
    "user.login_failed": "Connexion refusée",
    "user.profile_update": "Profil mis à jour",
    "analysis.started": "Analyse lancée",
    "analysis.completed": "Analyse terminée",
    "analysis.failed": "Analyse en échec",
    "analysis.blocked": "Analyse bloquée",
    "llm.quota": "Limite IA",
    "llm.switch": "Bascule IA",
    "search.quota": "Limite recherche",
    "apply.sent": "Candidature envoyée",
    "apply.failed": "Candidature en échec",
    "support.message": "Message support",
}

KIND_GROUPS: dict[str, tuple[str, ...]] = {
    "incidents": (
        "analysis.failed",
        "analysis.blocked",
        "llm.quota",
        "search.quota",
        "apply.failed",
        "user.login_failed",
    ),
    "comptes": ("user.register", "user.login", "user.profile_update"),
    "analyse": (
        "analysis.started",
        "analysis.completed",
        "analysis.failed",
        "analysis.blocked",
        "llm.quota",
        "llm.switch",
        "search.quota",
    ),
    "candidatures": ("apply.sent", "apply.failed"),
    "support": ("support.message",),
}


def ensure_admin_events_table(conn: Any | None = None) -> None:
    """Create the admin_events table if needed."""
    if conn is not None:
        _create_admin_events_table(conn)
        return
    with connect() as opened:
        _create_admin_events_table(opened)


def _create_admin_events_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_events (
                id SERIAL PRIMARY KEY,
                created_at TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                user_email TEXT NOT NULL DEFAULT '',
                user_name TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                title TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                payload_json TEXT,
                source TEXT NOT NULL DEFAULT 'app',
                read_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS admin_events_created_idx
            ON admin_events (created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS admin_events_unread_idx
            ON admin_events (severity, read_at, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS admin_events_user_idx
            ON admin_events (user_id, created_at DESC)
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_id INTEGER,
            user_email TEXT NOT NULL DEFAULT '',
            user_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT,
            source TEXT NOT NULL DEFAULT 'app',
            read_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS admin_events_created_idx
        ON admin_events (created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS admin_events_unread_idx
        ON admin_events (severity, read_at, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS admin_events_user_idx
        ON admin_events (user_id, created_at DESC)
        """
    )


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _payload_text(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)[:4000]
    except (TypeError, ValueError):
        return None


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_actor(
    user_id: int | None,
    user_email: str,
    user_name: str,
    actor: dict[str, Any] | None,
) -> tuple[int | None, str, str]:
    if actor:
        user_id = user_id or _as_int(actor.get("id") or actor.get("user_id"))
        user_email = user_email or str(actor.get("email") or "")
        user_name = user_name or str(actor.get("full_name") or actor.get("name") or "")
    if user_id and (not user_email or not user_name):
        try:
            from auth import get_user_by_id

            user = get_user_by_id(int(user_id)) or {}
            user_email = user_email or str(user.get("email") or "")
            user_name = user_name or str(user.get("full_name") or "")
        except Exception:  # noqa: BLE001
            pass
    if not user_id:
        try:
            from services.llm_usage import current_usage_user_id

            bound = current_usage_user_id()
            if bound:
                user_id = int(bound)
                if not user_email or not user_name:
                    from auth import get_user_by_id

                    user = get_user_by_id(int(user_id)) or {}
                    user_email = user_email or str(user.get("email") or "")
                    user_name = user_name or str(user.get("full_name") or "")
        except Exception:  # noqa: BLE001
            pass
    return user_id, _clip(user_email, 180).lower(), _clip(user_name, 180)


def _row_to_event(row: Any) -> dict[str, Any]:
    mapping = dict(row)
    kind = str(mapping.get("kind") or "")
    severity = str(mapping.get("severity") or SEVERITY_INFO)
    return {
        "id": int(mapping["id"]),
        "created_at": str(mapping.get("created_at") or ""),
        "user_id": _as_int(mapping.get("user_id")),
        "user_email": str(mapping.get("user_email") or ""),
        "user_name": str(mapping.get("user_name") or ""),
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, kind),
        "severity": severity,
        "title": str(mapping.get("title") or ""),
        "message": str(mapping.get("message") or ""),
        "payload": _parse_payload(mapping.get("payload_json")),
        "source": str(mapping.get("source") or "app"),
        "read_at": str(mapping.get("read_at") or "") or None,
        "unread": not mapping.get("read_at") and severity in ALERT_SEVERITIES,
    }


def _has_unread_duplicate(
    conn: Any,
    *,
    kind: str,
    user_id: int | None,
    title: str,
) -> bool:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=DEDUP_MINUTES)
    ).replace(microsecond=0).isoformat()
    if user_id:
        row = conn.execute(
            adapt_sql(
                """
                SELECT id FROM admin_events
                WHERE kind = ? AND title = ? AND user_id = ?
                  AND read_at IS NULL AND created_at >= ?
                LIMIT 1
                """
            ),
            (kind, title, int(user_id), cutoff),
        ).fetchone()
    else:
        row = conn.execute(
            adapt_sql(
                """
                SELECT id FROM admin_events
                WHERE kind = ? AND title = ? AND user_id IS NULL
                  AND read_at IS NULL AND created_at >= ?
                LIMIT 1
                """
            ),
            (kind, title, cutoff),
        ).fetchone()
    return bool(row)


def record_admin_event(
    kind: str,
    *,
    title: str = "",
    message: str = "",
    severity: str = SEVERITY_INFO,
    user_id: int | None = None,
    user_email: str = "",
    user_name: str = "",
    actor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "app",
    dedupe: bool | None = None,
) -> int | None:
    """Persist one activity row. Never raises to the caller."""
    try:
        ensure_admin_events_table()
        kind_id = _clip(kind, 64) or "event"
        level = (severity or SEVERITY_INFO).strip().lower()
        if level not in {SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_ERROR}:
            level = SEVERITY_INFO
        heading = _clip(title, 180) or KIND_LABELS.get(kind_id, kind_id)
        body = _clip(message, 800)
        uid, email, name = _resolve_actor(user_id, user_email, user_name, actor)
        should_dedupe = (level in ALERT_SEVERITIES) if dedupe is None else bool(dedupe)
        with connect() as conn:
            if should_dedupe and _has_unread_duplicate(
                conn, kind=kind_id, user_id=uid, title=heading
            ):
                return None
            values = (
                utc_now_iso(),
                uid,
                email,
                name,
                kind_id,
                level,
                heading,
                body,
                _payload_text(payload),
                _clip(source, 32) or "app",
            )
            if database_backend() == "postgres":
                row = conn.execute(
                    """
                    INSERT INTO admin_events (
                        created_at, user_id, user_email, user_name, kind, severity,
                        title, message, payload_json, source
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    values,
                ).fetchone()
                return int(row["id"]) if row else None
            cursor = conn.execute(
                """
                INSERT INTO admin_events (
                    created_at, user_id, user_email, user_name, kind, severity,
                    title, message, payload_json, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid or 0) or None
    except Exception:  # noqa: BLE001 — tracking must never break the product
        logger.warning("Could not record admin event %s", kind, exc_info=True)
        return None


def list_admin_events(
    *,
    limit: int = 80,
    kinds: list[str] | None = None,
    severity: str | None = None,
    unread_only: bool = False,
    user_id: int | None = None,
    query: str = "",
) -> list[dict[str, Any]]:
    ensure_admin_events_table()
    clauses: list[str] = []
    params: list[Any] = []
    if kinds:
        placeholders = ", ".join("?" for _ in kinds)
        clauses.append(f"kind IN ({placeholders})")
        params.extend(kinds)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if unread_only:
        clauses.append("read_at IS NULL")
        clauses.append("severity IN (?, ?)")
        params.extend(ALERT_SEVERITIES)
    if user_id:
        clauses.append("user_id = ?")
        params.append(int(user_id))
    needle = query.strip()
    if needle:
        like = f"%{needle.lower()}%"
        clauses.append(
            "(LOWER(user_email) LIKE ? OR LOWER(user_name) LIKE ? "
            "OR LOWER(title) LIKE ? OR LOWER(message) LIKE ? OR LOWER(kind) LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT * FROM admin_events
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
    """
    params.append(max(1, min(int(limit), 400)))
    with connect() as conn:
        rows = conn.execute(adapt_sql(sql), tuple(params)).fetchall()
    return [_row_to_event(row) for row in rows]


def list_admin_alerts(*, limit: int = 60, unread_only: bool = False) -> list[dict[str, Any]]:
    ensure_admin_events_table()
    clauses = ["severity IN (?, ?)"]
    params: list[Any] = list(ALERT_SEVERITIES)
    if unread_only:
        clauses.append("read_at IS NULL")
    sql = f"""
        SELECT * FROM admin_events
        WHERE {' AND '.join(clauses)}
        ORDER BY CASE WHEN read_at IS NULL THEN 0 ELSE 1 END,
                 created_at DESC, id DESC
        LIMIT ?
    """
    params.append(max(1, min(int(limit), 200)))
    with connect() as conn:
        rows = conn.execute(adapt_sql(sql), tuple(params)).fetchall()
    return [_row_to_event(row) for row in rows]


def unread_admin_alert_count() -> int:
    ensure_admin_events_table()
    with connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT COUNT(*) AS n FROM admin_events
                WHERE read_at IS NULL AND severity IN (?, ?)
                """
            ),
            ALERT_SEVERITIES,
        ).fetchone()
    try:
        return int(row["n"] if row is not None else 0)
    except (TypeError, ValueError, KeyError):
        return 0


def mark_admin_events_read(event_ids: list[int] | None = None, *, all_unread: bool = False) -> int:
    """Mark alerts as read. Returns the number of updated rows."""
    ensure_admin_events_table()
    now = utc_now_iso()
    if all_unread:
        with connect() as conn:
            cursor = conn.execute(
                adapt_sql(
                    """
                    UPDATE admin_events
                    SET read_at = ?
                    WHERE read_at IS NULL AND severity IN (?, ?)
                    """
                ),
                (now, *ALERT_SEVERITIES),
            )
        return int(getattr(cursor, "rowcount", 0) or 0)
    ids = [int(item) for item in (event_ids or []) if int(item) > 0]
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    with connect() as conn:
        cursor = conn.execute(
            adapt_sql(
                f"""
                UPDATE admin_events
                SET read_at = ?
                WHERE id IN ({placeholders}) AND read_at IS NULL
                """
            ),
            (now, *ids),
        )
    return int(getattr(cursor, "rowcount", 0) or 0)


def classify_analysis_failure(error: str) -> tuple[str, str, str]:
    """Return (kind, severity, title) for a failed / empty analysis."""
    text = (error or "").strip()
    lower = text.lower()
    if any(
        token in lower
        for token in (
            "quota",
            "rate limit",
            "rate_limit",
            "insufficient_quota",
            "limite ia",
            "limite atteinte",
            "credit_balance",
            "resource_exhausted",
        )
    ):
        return "llm.quota", SEVERITY_ERROR, "Limite IA atteinte"
    if "serpapi" in lower or "serp api" in lower:
        return "search.quota", SEVERITY_WARNING, "Limite SerpAPI"
    if any(
        token in lower
        for token in (
            "déjà en cours",
            "deja en cours",
            "already",
            "pdf trop",
            "pdf_too_large",
            "missing_cv",
            "cv manquant",
            "bloqu",
        )
    ):
        return "analysis.blocked", SEVERITY_WARNING, "Analyse bloquée"
    if any(
        token in lower
        for token in ("analyse vide", "aucune offre", "no job", "empty")
    ):
        return "analysis.blocked", SEVERITY_WARNING, "Analyse sans résultat"
    return "analysis.failed", SEVERITY_ERROR, "Analyse en échec"


def record_user_registered(*, user_id: int | None = None, email: str, full_name: str) -> None:
    uid = user_id
    if uid is None and email:
        try:
            from auth import get_user_by_email

            user = get_user_by_email(email) or {}
            if user.get("id"):
                uid = int(user["id"])
                full_name = full_name or str(user.get("full_name") or "")
        except Exception:  # noqa: BLE001
            pass
    record_admin_event(
        "user.register",
        title="Nouveau compte",
        message=f"{full_name or email} s'est inscrit.",
        severity=SEVERITY_INFO,
        user_id=uid,
        user_email=email,
        user_name=full_name,
        source="auth",
        dedupe=False,
    )


def record_user_login(*, user_id: int, email: str = "", full_name: str = "") -> None:
    record_admin_event(
        "user.login",
        title="Connexion",
        message=f"{full_name or email or 'Un candidat'} s'est connecté.",
        severity=SEVERITY_INFO,
        user_id=user_id,
        user_email=email,
        user_name=full_name,
        source="auth",
        dedupe=False,
    )


def record_user_login_failed(*, email: str, reason: str = "") -> None:
    record_admin_event(
        "user.login_failed",
        title="Connexion refusée",
        message=_clip(reason, 240) or f"Tentative de connexion refusée pour {email or 'un e-mail inconnu'}.",
        severity=SEVERITY_WARNING,
        user_email=email,
        source="auth",
        payload={"reason": reason},
    )


def record_profile_update(*, user_id: int, email: str = "", full_name: str = "") -> None:
    record_admin_event(
        "user.profile_update",
        title="Profil mis à jour",
        message=f"{full_name or email or 'Un candidat'} a modifié son profil.",
        severity=SEVERITY_INFO,
        user_id=user_id,
        user_email=email,
        user_name=full_name,
        source="auth",
        dedupe=False,
    )


def record_analysis_started(
    *,
    user_id: int,
    job_id: int | None = None,
    depth: str = "",
    provider: str = "",
    actor: dict[str, Any] | None = None,
) -> None:
    extras = " · ".join(part for part in (depth, provider) if part)
    record_admin_event(
        "analysis.started",
        title="Analyse lancée",
        message=f"Matching {extras or 'standard'} mis en file.",
        severity=SEVERITY_INFO,
        user_id=user_id,
        actor=actor,
        payload={"job_id": job_id, "depth": depth, "provider": provider},
        source="analysis",
        dedupe=False,
    )


def record_analysis_blocked(
    *,
    user_id: int,
    reason: str,
    actor: dict[str, Any] | None = None,
) -> None:
    kind, severity, title = classify_analysis_failure(reason)
    if kind == "analysis.failed":
        kind, severity, title = (
            "analysis.blocked",
            SEVERITY_WARNING,
            "Analyse bloquée",
        )
    record_admin_event(
        kind,
        title=title,
        message=reason,
        severity=severity,
        user_id=user_id,
        actor=actor,
        source="analysis",
    )


def record_analysis_finished(
    *,
    job_id: int,
    user_id: int | None = None,
    analysis_id: int | None = None,
    success: bool,
    error: str = "",
    notices: list[dict[str, str]] | None = None,
) -> None:
    actor = None
    if user_id is None:
        try:
            from services.analysis_queue import get_analysis_job

            job = get_analysis_job(int(job_id))
            if job:
                user_id = int(job.get("user_id") or 0) or None
                profile = job.get("user_profile_json")
                if isinstance(profile, dict):
                    actor = profile
        except Exception:  # noqa: BLE001
            pass
    if success:
        record_admin_event(
            "analysis.completed",
            title="Analyse terminée",
            message="Matching CV / offres terminé.",
            severity=SEVERITY_INFO,
            user_id=user_id,
            actor=actor,
            payload={"job_id": job_id, "analysis_id": analysis_id},
            source="analysis",
            dedupe=False,
        )
        warning_notices = [
            item for item in (notices or [])
            if str(item.get("level") or "") in {"warning", "error"}
        ]
        for item in warning_notices[:4]:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            kind, severity, title = classify_analysis_failure(text)
            if kind == "analysis.failed":
                kind, severity = "llm.switch", SEVERITY_WARNING
                title = "Alerte pendant l'analyse"
            record_admin_event(
                kind,
                title=title,
                message=text,
                severity=severity,
                user_id=user_id,
                actor=actor,
                payload={"job_id": job_id, "notice": item},
                source="analysis",
            )
        return
    kind, severity, title = classify_analysis_failure(error)
    record_admin_event(
        kind,
        title=title,
        message=error or "Analyse impossible.",
        severity=severity,
        user_id=user_id,
        actor=actor,
        payload={"job_id": job_id, "notices": notices or []},
        source="analysis",
    )


def record_llm_quota(*, provider: str, reason: str = "", switched_to: str = "") -> None:
    label = (provider or "IA").strip() or "IA"
    if switched_to:
        message = f"{label} indisponible ({reason or 'quota'}) — bascule sur {switched_to}."
        kind = "llm.switch"
        severity = SEVERITY_WARNING
        title = f"Bascule IA · {label}"
    else:
        message = f"Limite atteinte sur {label}. {reason}".strip()
        kind = "llm.quota"
        severity = SEVERITY_ERROR
        title = f"Limite IA · {label}"
    record_admin_event(
        kind,
        title=title,
        message=message,
        severity=severity,
        payload={"provider": provider, "reason": reason, "switched_to": switched_to},
        source="llm",
    )


def record_search_quota(*, detail: str = "") -> None:
    record_admin_event(
        "search.quota",
        title="Limite SerpAPI",
        message=detail or "Quota SerpAPI atteint — la recherche continue sur les moteurs gratuits.",
        severity=SEVERITY_WARNING,
        source="search",
    )


def record_application_event(
    user_profile: dict[str, Any] | None,
    job: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> None:
    profile = user_profile or {}
    offer = job or {}
    outcome = result or {}
    company = str(offer.get("company") or "").strip()
    title = str(offer.get("title") or offer.get("job_title") or "").strip()
    offer_label = " · ".join(part for part in (title, company) if part) or "une offre"
    success = bool(outcome.get("success"))
    method = str(outcome.get("method") or "")
    if success:
        record_admin_event(
            "apply.sent",
            title="Candidature envoyée",
            message=f"Candidature envoyée pour {offer_label}.",
            severity=SEVERITY_INFO,
            actor=profile,
            payload={
                "method": method,
                "company": company,
                "title": title,
                "email_to": outcome.get("email_to") or "",
            },
            source="apply",
            dedupe=False,
        )
        return
    record_admin_event(
        "apply.failed",
        title="Candidature bloquée",
        message=str(outcome.get("message") or f"Candidature impossible pour {offer_label}."),
        severity=SEVERITY_WARNING,
        actor=profile,
        payload={
            "method": method,
            "company": company,
            "title": title,
        },
        source="apply",
    )


def record_support_message_event(
    *,
    user_id: int,
    preview: str,
    actor: dict[str, Any] | None = None,
) -> None:
    record_admin_event(
        "support.message",
        title="Message support",
        message=_clip(preview, 240) or "Nouveau message candidat.",
        severity=SEVERITY_INFO,
        user_id=user_id,
        actor=actor,
        source="support",
        dedupe=False,
    )


def admin_activity_payload(*, activity_limit: int = 80, alert_limit: int = 40) -> dict[str, Any]:
    """Bundle used by the admin overview (Streamlit + HTML SPA)."""
    alerts = list_admin_alerts(limit=alert_limit)
    unread = sum(1 for item in alerts if item.get("unread"))
    if unread == 0:
        unread = unread_admin_alert_count()
    events = list_admin_events(limit=activity_limit)
    counts: dict[str, int] = {}
    for item in events:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {
        "unread_alerts": unread,
        "alerts": alerts,
        "events": events,
        "kind_counts": [
            {"kind": kind, "label": KIND_LABELS.get(kind, kind), "count": count}
            for kind, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "kind_labels": KIND_LABELS,
    }
