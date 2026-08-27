"""Support chat is wired into candidate nav, locales, and admin inbox."""

from __future__ import annotations

import json
from pathlib import Path

from constants import NAV_PAGE_KEYS

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_support_is_in_candidate_navigation():
    assert "support" in NAV_PAGE_KEYS
    app = _read("app.py")
    assert "def render_support_page" in app
    assert 'if page == "support":' in app
    theme = _read("ui/theme.py")
    assert '"support": "💬"' in theme
    assert ".support-thread" in theme
    assert ".support-bubble.user" in theme


def test_support_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads(_read(f"locales/{locale}.json"))
        for key in (
            "nav.support",
            "hero.support.title",
            "hero.support.subtitle",
            "support.hint",
            "support.send",
            "support.empty",
        ):
            assert key in data, f"missing {key} in {locale}.json"
            assert str(data[key]).strip()


def test_admin_dashboard_has_per_user_inbox():
    dash = _read("pages/dashboard.py")
    assert "def _render_admin_support" in dash
    assert "admin_support_conversations" in dash
    assert "send_admin_support_reply" in dash
    assert "admin_support_send" in dash
    html = _read("admin/static/index.html")
    assert 'data-tab="support"' in html
    assert "tab-support" in html
    assert "/api/admin/support/conversations" in html
