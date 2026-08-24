"""Versioned SQL migrations for SQLite and PostgreSQL."""

from __future__ import annotations

from pathlib import Path

from database import adapt_sql, connect, database_backend
from observability import get_logger

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "sql"


def _ensure_migration_table(conn) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT NOW()::TEXT
            )
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _applied_versions(conn) -> set[str]:
    rows = conn.execute(adapt_sql("SELECT version FROM schema_migrations")).fetchall()
    return {str(row["version"]) for row in rows}


def run_migrations() -> list[str]:
    """Apply pending SQL files from migrations/sql in lexical order."""
    applied_now: list[str] = []
    if not MIGRATIONS_DIR.is_dir():
        logger.warning("No migrations directory at %s", MIGRATIONS_DIR)
        return applied_now

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with connect() as conn:
        _ensure_migration_table(conn)
        done = _applied_versions(conn)
        for path in migration_files:
            version = path.stem
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            logger.info("Applying migration %s", version)
            conn.executescript(sql) if database_backend() != "postgres" else _exec_postgres_script(conn, sql)
            conn.execute(
                adapt_sql("INSERT INTO schema_migrations (version) VALUES (?)"),
                (version,),
            )
            applied_now.append(version)
        conn.commit()
    return applied_now


def _exec_postgres_script(conn, sql: str) -> None:
    for statement in _split_sql_statements(sql):
        if statement.strip():
            conn.execute(statement)


def _split_sql_statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]
