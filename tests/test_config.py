"""Config helper tests."""

from __future__ import annotations

from config import get_secret, normalize_secret


def test_normalize_secret_strips_quotes():
    assert normalize_secret('" abc "') == "abc"


def test_get_secret_prefers_env(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_KEY", "from-env")
    assert get_secret("TEST_SECRET_KEY") == "from-env"


def test_single_admin_email_and_password(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "SecretAdmin!")
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORDS", raising=False)
    monkeypatch.delenv("ADMIN_ACCOUNTS", raising=False)
    from config import get_admin_accounts

    assert get_admin_accounts() == [("boss@example.com", "SecretAdmin!")]
