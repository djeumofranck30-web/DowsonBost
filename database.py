"""Database connection layer — SQLite (local) or PostgreSQL (production)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SQLITE_PATH = Path(__file__).parent / "data" / "users.db"

_backend: str = "sqlite"
_database_url: str = ""
_configured = False


def configure_database(url: str = "") -> str:
    """Select SQLite (default) or PostgreSQL when DATABASE_URL is set."""
    global _backend, _database_url, _configured
    url = (url or os.getenv("DATABASE_URL", "")).strip()
    _database_url = url
    if url.startswith(("postgres://", "postgresql://")):
        _backend = "postgres"
    else:
        _backend = "sqlite"
    _configured = True
    return _backend


def ensure_configured() -> None:
    if not _configured:
        configure_database(os.getenv("DATABASE_URL", ""))


def database_backend() -> str:
    ensure_configured()
    return _backend


def database_status() -> tuple[str, str]:
    """Return (backend_label, message) for diagnostics."""
    ensure_configured()
    if _backend == "postgres":
        host = "PostgreSQL distant"
        try:
            from urllib.parse import urlparse

            parsed = urlparse(_database_url)
            if parsed.hostname:
                host = parsed.hostname
        except Exception:  # noqa: BLE001
            pass
        return "postgres", f"Base persistante PostgreSQL ({host}) — comptes conservés après déploiement."
    return "sqlite", (
        "SQLite local (data/users.db) — les comptes sont effacés à chaque redéploiement "
        "Streamlit Cloud. Ajoutez DATABASE_URL (Supabase/Neon) dans les secrets."
    )


def adapt_sql(sql: str) -> str:
    """Convert placeholders for the active backend."""
    if database_backend() == "postgres":
        return sql.replace("?", "%s")
    return sql


def is_unique_violation(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    try:
        from psycopg.errors import UniqueViolation

        return isinstance(exc, UniqueViolation)
    except ImportError:
        return False


def existing_columns(conn: Any, table: str = "users") -> set[str]:
    if database_backend() == "postgres":
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a DB connection for the configured backend."""
    ensure_configured()
    if database_backend() == "postgres":
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(_database_url, row_factory=dict_row) as conn:
            yield conn
    else:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
