"""Candidate IA maps Digibrain-style spaces onto DowsonBost pages."""

from __future__ import annotations

import json
from pathlib import Path

from constants import (
    ADMIN_PAGE_PATH,
    EVENTS_TAB_KEYS,
    NAV_PAGE_KEYS,
    canonical_nav_page,
    events_tab_for,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_nav_spaces_match_overview_diagnostic_events_admin():
    assert NAV_PAGE_KEYS == ("dashboard", "analysis", "events", "support", "profile")
    assert NAV_PAGE_KEYS[0] == "dashboard"
    assert "applications" not in NAV_PAGE_KEYS
    assert "history" not in NAV_PAGE_KEYS
    assert EVENTS_TAB_KEYS == ("applications", "history")
    assert ADMIN_PAGE_PATH == "pages/dashboard.py"
    assert canonical_nav_page("applications") == "events"
    assert canonical_nav_page("history") == "events"
    assert canonical_nav_page("overview") == "dashboard"
    assert canonical_nav_page("diagnostic") == "analysis"
    assert canonical_nav_page("support") == "support"
    assert canonical_nav_page("unknown") is None
    assert events_tab_for("applications") == "applications"
    assert events_tab_for("history") == "history"
    assert events_tab_for("events", fallback=None) is None
    assert events_tab_for("dashboard") == "applications"


def test_app_wires_events_admin_context_and_account():
    source = _read("app.py")
    render_app = source.split("def render_app()", 1)[1].split("def main()", 1)[0]
    assert "def render_events_page(" in source
    assert "def render_sidebar_workspace_context(" in source
    assert "_render_overview_kpis(" in source
    assert "_render_overview_shortcuts(" in source
    assert 'if page == "events":' in render_app
    assert "render_events_page(user)" in render_app
    assert 'if page == "applications":' not in render_app
    assert 'if page == "history":' not in render_app
    assert "render_sidebar_workspace_context(user)" in render_app
    assert 't("nav.menu")' in render_app
    assert 't("nav.account")' in render_app
    assert 't("nav.admin")' in render_app
    assert "st.page_link(ADMIN_PAGE_PATH" in render_app
    assert "user_is_admin(user)" in render_app
    assert 'key="logout_button"' in render_app
    assert 'key="sidebar_change_context"' in source
    assert '_request_navigation("applications")' in source
    assert "canonical_nav_page(" in source
    assert "events_tab_for(" in source
    assert render_app.index('if page == "analysis":') < render_app.index(
        'key="sidebar_job_provider"'
    )


def test_theme_has_events_admin_and_context_styles():
    theme = _read("ui/theme.py")
    assert '"events": "🗓️"' in theme
    assert '"admin": "🛡️"' in theme
    assert ".workspace-context" in theme
    assert ".overview-kpi-grid" in theme


def test_information_architecture_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads(_read(f"locales/{locale}.json"))
        for key in (
            "nav.dashboard",
            "nav.analysis",
            "nav.events",
            "nav.applications",
            "nav.history",
            "nav.menu",
            "nav.account",
            "nav.admin",
            "hero.events.title",
            "hero.events.subtitle",
            "hero.events.badge",
            "events.tabs_label",
            "overview.shortcuts_title",
            "overview.go_diagnostic",
            "overview.go_events",
            "overview.go_profile",
            "overview.kpi_analyses",
            "overview.kpi_applications",
            "overview.kpi_latest",
            "workspace.context_title",
            "workspace.change_context",
            "workspace.no_target",
        ):
            assert key in data, f"missing {key} in {locale}.json"
            assert str(data[key]).strip()
    fr = json.loads(_read("locales/fr.json"))
    assert fr["nav.dashboard"] == "Synthèse"
    assert fr["nav.events"] == "Événements"
    assert fr["hero.analysis.badge"] == "Diagnostic"
    assert fr["nav.admin"] == "Administration"
    en = json.loads(_read("locales/en.json"))
    assert en["nav.dashboard"] == "Overview"
    assert en["nav.events"] == "Events"
