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


def test_disable_prepared_statements_sets_none_on_connection():
    from database import _disable_prepared_statements

    class FakeConn:
        prepare_threshold = 5

    conn = FakeConn()
    _disable_prepared_statements(conn)
    assert conn.prepare_threshold is None
    kwargs = postgres_client_connect_kwargs()
    # 0 would still PREPARE on the first query and break PgBouncer.
    assert kwargs["prepare_threshold"] is None
    assert kwargs["autocommit"] is False


def test_prepared_statement_conflict_is_not_a_bad_password():
    from database import _is_prepared_statement_conflict

    assert _is_prepared_statement_conflict(
        RuntimeError('prepared statement "_pg3_0" already exists')
    )
    assert not _is_prepared_statement_conflict(RuntimeError("syntax error"))


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


def test_query_operational_errors_are_not_relabeled(monkeypatch):
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

    with pytest.raises(psycopg.OperationalError, match="server closed"):
        with database.connect():
            raise psycopg.OperationalError("server closed the connection unexpectedly")
    assert fake.closed is True


def test_connect_open_failures_include_driver_message(monkeypatch):
    import database
    import psycopg

    monkeypatch.setattr(database, "_configured", True)
    monkeypatch.setattr(database, "_backend", "postgres")
    monkeypatch.setattr(database, "_database_url", POOLER_URL)

    def _acquire(_row_factory):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(database, "_acquire_postgres_connection", _acquire)

    with pytest.raises(RuntimeError, match="connection refused") as err:
        with database.connect():
            raise AssertionError("must not yield")
    assert "Connexion PostgreSQL impossible" in str(err.value)


def test_nested_pooler_connect_does_not_close_outer_connection(monkeypatch):
    import database

    class FakeConn:
        def __init__(self) -> None:
            self.closed = False
            self.commits = 0

        def commit(self) -> None:
            if self.closed:
                raise RuntimeError("the connection is closed")
            self.commits += 1

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    fake = FakeConn()
    acquires = {"n": 0}

    def _acquire(_row_factory):
        acquires["n"] += 1
        database._pg_local.conn = fake
        return fake

    monkeypatch.setattr(database, "_configured", True)
    monkeypatch.setattr(database, "_backend", "postgres")
    monkeypatch.setattr(database, "_database_url", POOLER_URL)
    monkeypatch.setattr(database, "_acquire_postgres_connection", _acquire)
    database._pg_local.depth = 0
    database._pg_local.conn = None

    with database.connect() as outer:
        with database.connect() as inner:
            assert inner is outer
            assert fake.closed is False
        assert fake.closed is False
        assert fake.commits == 0
    assert fake.closed is True
    assert fake.commits == 1
    assert acquires["n"] == 1


def test_format_database_exception_includes_cause():
    from database import format_database_exception

    try:
        raise RuntimeError("outer") from ValueError("inner boom")
    except RuntimeError as exc:
        text = format_database_exception(exc)
    assert "outer" in text
    assert "inner boom" in text
