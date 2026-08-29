"""Postgres connection helpers — pooler reuse and error wrapping."""

from __future__ import annotations

import pytest

from database import (
    is_postgres_connection_error,
    postgres_client_connect_kwargs,
    postgres_conninfo,
    uses_transaction_pooler,
)


POOLER_URL = (
    "postgresql://postgres.abc:secret@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
)
DIRECT_URL = "postgresql://postgres:secret@db.abc.supabase.co:5432/postgres"


def test_uses_transaction_pooler_on_supabase_port():
    assert uses_transaction_pooler(POOLER_URL) is True
    assert uses_transaction_pooler(DIRECT_URL) is False
    assert uses_transaction_pooler("postgresql://u:p@pooler.example.com:5432/db") is True


def test_sql_errors_are_not_connection_failures():
    assert is_postgres_connection_error(ValueError("column boom does not exist")) is False
    assert is_postgres_connection_error(RuntimeError("undefined table analysis_jobs")) is False


def test_transport_errors_are_connection_failures():
    assert is_postgres_connection_error(
        RuntimeError("server closed the connection unexpectedly")
    )
    try:
        import psycopg

        assert is_postgres_connection_error(
            psycopg.OperationalError("connection refused")
        )
    except ImportError:
        pytest.skip("psycopg not installed")


def test_pooler_client_disables_prepared_statements():
    kwargs = postgres_client_connect_kwargs()
    assert kwargs["prepare_threshold"] == 0
    assert kwargs["autocommit"] is False


def test_conninfo_includes_keepalives():
    info = postgres_conninfo(POOLER_URL)
    assert "keepalives" in info
    assert "6543" in info
    assert "secret" in info


def test_query_errors_are_not_relabeled_as_connection_failures(monkeypatch):
    import database

    class FakeConn:
        closed = False

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            self.closed = True

    fake = FakeConn()

    def _acquire(_row_factory):
        database._pg_local.conn = fake
        return fake

    monkeypatch.setattr(database, "_configured", True)
    monkeypatch.setattr(database, "_backend", "postgres")
    monkeypatch.setattr(database, "_database_url", POOLER_URL)
    monkeypatch.setattr(database, "_acquire_postgres_connection", _acquire)

    with pytest.raises(ValueError, match="undefined_column"):
        with database.connect():
            raise ValueError("undefined_column")
    assert fake.closed is True


def test_operational_errors_are_labeled_connection_failures(monkeypatch):
    import database
    import psycopg

    class FakeConn:
        closed = False

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            self.closed = True

    fake = FakeConn()

    def _acquire(_row_factory):
        database._pg_local.conn = fake
        return fake

    monkeypatch.setattr(database, "_configured", True)
    monkeypatch.setattr(database, "_backend", "postgres")
    monkeypatch.setattr(database, "_database_url", POOLER_URL)
    monkeypatch.setattr(database, "_acquire_postgres_connection", _acquire)

    with pytest.raises(RuntimeError, match="Connexion PostgreSQL impossible"):
        with database.connect():
            raise psycopg.OperationalError("server closed the connection unexpectedly")
    assert fake.closed is True
