"""Pytest configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Force SQLite in-memory style tests via temp file
os.environ.setdefault("DATABASE_URL", "")


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    """Configure isolated SQLite database for a test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    from database import SQLITE_PATH

    monkeypatch.setattr("database.SQLITE_PATH", db_path)
    monkeypatch.setattr("database._configured", False)
    monkeypatch.setattr("database._config_key", None)
    monkeypatch.setattr("database._backend", "sqlite")
    from auth import _db_initialized_for
    import auth

    auth._db_initialized_for = None
    from database import configure_database

    configure_database("", password="")
    try:
        import services.llm_usage as llm_usage

        llm_usage._table_ready = False
    except Exception:
        pass
    import persistence

    persistence._persistence_initialized_for = None
    from auth import init_db

    init_db()
    yield db_path
