"""Config helper tests."""

from __future__ import annotations

from config import get_secret, normalize_secret


def test_normalize_secret_strips_quotes():
    assert normalize_secret('" abc "') == "abc"


def test_get_secret_prefers_env(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_KEY", "from-env")
    assert get_secret("TEST_SECRET_KEY") == "from-env"
