"""Password reset requires a short-lived e-mailed code."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from auth import (
    authenticate_user,
    complete_verified_password_reset,
    register_user,
    request_password_reset_code,
    reset_password,
    verify_password_reset_code,
)
from database import adapt_sql, connect


def _register():
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_reset_code_is_required_before_new_password(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")

    ok, msg = complete_verified_password_reset(1, "NewSecret456!")
    assert not ok

    ok, msg, expires_at = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    assert expires_at
    send.assert_called_once()
    assert send.call_args.args[0] == "jane@example.com"
    assert send.call_args.args[1] == "AB23K7NP"

    with connect() as conn:
        row = conn.execute(adapt_sql("SELECT code_hash FROM password_reset_codes")).fetchone()
    assert row is not None
    assert "AB23K7NP" not in str(row["code_hash"]).upper()

    ok, _, user_id = verify_password_reset_code("jane@example.com", "ZZZZZZZZ")
    assert not ok
    assert user_id is None

    ok, _, user_id = verify_password_reset_code("jane@example.com", "ab23k7np")
    assert ok
    assert user_id

    ok, msg = complete_verified_password_reset(int(user_id), "NewSecret456!")
    assert ok, msg
    assert authenticate_user("jane@example.com", "Secret123!")[0] is False
    assert authenticate_user("jane@example.com", "NewSecret456!")[0] is True


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_legacy_reset_password_cannot_bypass_code(configured, send, sqlite_db):
    _register()
    ok, msg = reset_password("jane@example.com", "Jane Doe", "HackedPass1!")
    assert not ok
    assert authenticate_user("jane@example.com", "Secret123!")[0] is True
    assert authenticate_user("jane@example.com", "HackedPass1!")[0] is False


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_password_cannot_change_until_code_is_verified(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, msg = complete_verified_password_reset(1, "NewSecret456!")
    assert not ok
    assert authenticate_user("jane@example.com", "Secret123!")[0] is True


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_code_accepts_spaces_and_mixed_case(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")
    ok, msg, _ = request_password_reset_code("  Jane@Example.com  ", "  Jane   Doe  ")
    assert ok, msg
    ok, _, user_id = verify_password_reset_code("jane@example.com", " ab-23 k7 np ")
    assert ok
    assert user_id


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_resend_invalidates_the_previous_code(configured, send, sqlite_db, monkeypatch):
    _register()
    codes = iter(["AB23K7NP", "ZX98Q3WM"])
    monkeypatch.setattr("auth._generate_reset_code", lambda: next(codes))
    monkeypatch.setattr("auth.PASSWORD_RESET_CODE_RESEND_COOLDOWN_SECONDS", 0)
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, _, user_id = verify_password_reset_code("jane@example.com", "AB23K7NP")
    assert not ok
    assert user_id is None
    ok, _, user_id = verify_password_reset_code("jane@example.com", "ZX98Q3WM")
    assert ok
    assert user_id


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_resend_is_rate_limited(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, msg, expires = request_password_reset_code("jane@example.com", "Jane Doe")
    assert not ok
    assert expires == ""
    assert send.call_count == 1


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_five_wrong_codes_lock_until_a_new_code_is_sent(configured, send, sqlite_db, monkeypatch):
    _register()
    codes = iter(["AB23K7NP", "ZX98Q3WM"])
    monkeypatch.setattr("auth._generate_reset_code", lambda: next(codes))
    monkeypatch.setattr("auth.PASSWORD_RESET_CODE_RESEND_COOLDOWN_SECONDS", 0)
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    for _ in range(5):
        ok, msg, user_id = verify_password_reset_code("jane@example.com", "ZZZZZZZZ")
        assert not ok
        assert user_id is None
    ok, msg, user_id = verify_password_reset_code("jane@example.com", "AB23K7NP")
    assert not ok
    assert user_id is None
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, _, user_id = verify_password_reset_code("jane@example.com", "ZX98Q3WM")
    assert ok
    assert user_id


@patch("email_service.send_password_reset_code_email", return_value=(False, "smtp down"))
@patch("email_service.email_configured", return_value=True)
def test_failed_email_does_not_leave_a_usable_code(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")
    ok, msg, expires = request_password_reset_code("jane@example.com", "Jane Doe")
    assert not ok
    assert expires == ""
    ok, _, user_id = verify_password_reset_code("jane@example.com", "AB23K7NP")
    assert not ok
    assert user_id is None


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_used_code_cannot_reset_password_twice(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "AB23K7NP")
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    ok, _, user_id = verify_password_reset_code("jane@example.com", "AB23K7NP")
    assert ok
    ok, msg = complete_verified_password_reset(int(user_id), "NewSecret456!")
    assert ok, msg
    ok, msg = complete_verified_password_reset(int(user_id), "AnotherPass1!")
    assert not ok
    assert authenticate_user("jane@example.com", "NewSecret456!")[0] is True
    assert authenticate_user("jane@example.com", "AnotherPass1!")[0] is False


@patch("email_service.send_password_reset_code_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_expired_reset_code_cannot_unlock_password(configured, send, sqlite_db, monkeypatch):
    _register()
    monkeypatch.setattr("auth._generate_reset_code", lambda: "ZX98Q3WM")
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert ok, msg
    past = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    with connect() as conn:
        conn.execute(adapt_sql("UPDATE password_reset_codes SET expires_at = ?"), (past,))
        conn.commit()
    ok, msg, user_id = verify_password_reset_code("jane@example.com", "ZX98Q3WM")
    assert not ok
    assert user_id is None
    assert "expir" in msg.lower() or "expir" in msg
    ok, msg = complete_verified_password_reset(1, "NewSecret456!")
    assert not ok
    assert authenticate_user("jane@example.com", "Secret123!")[0] is True


@patch("email_service.email_configured", return_value=True)
def test_name_mismatch_does_not_send_code(configured, sqlite_db):
    _register()
    with patch("email_service.send_password_reset_code_email") as send:
        ok, msg, expires = request_password_reset_code("jane@example.com", "Wrong Name")
    assert not ok
    assert expires == ""
    send.assert_not_called()


@patch("email_service.email_configured", return_value=False)
def test_reset_code_requires_email_service(configured, sqlite_db):
    _register()
    ok, msg, _ = request_password_reset_code("jane@example.com", "Jane Doe")
    assert not ok
    assert "e-mail" in msg.lower() or "email" in msg.lower()
