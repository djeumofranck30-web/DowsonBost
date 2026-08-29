"""Config helper tests."""

from __future__ import annotations

import types

from config import export_streamlit_secrets_to_environ, get_secret, normalize_secret


def test_normalize_secret_strips_quotes():
    assert normalize_secret('" abc "') == "abc"


def test_get_secret_prefers_env(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_KEY", "from-env")
    assert get_secret("TEST_SECRET_KEY") == "from-env"


def test_export_streamlit_secrets_to_environ(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake_st = types.SimpleNamespace(
        secrets={"OPENAI_API_KEY": "sk-test", "GROQ_API_KEY": "gsk-test"}
    )
    monkeypatch.setitem(__import__("sys").modules, "streamlit", fake_st)
    copied = export_streamlit_secrets_to_environ()
    assert copied >= 2
    assert get_secret("OPENAI_API_KEY") == "sk-test"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


def test_single_admin_email_and_password(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "SecretAdmin!")
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORDS", raising=False)
    monkeypatch.delenv("ADMIN_ACCOUNTS", raising=False)
    from config import get_admin_accounts

    assert get_admin_accounts() == [("boss@example.com", "SecretAdmin!")]
