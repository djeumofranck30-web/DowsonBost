"""Candidate dashboard and profile layout."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dashboard_and_profile_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads(_read(f"locales/{locale}.json"))
        for key in (
            "dashboard.empty_title",
            "dashboard.empty_text",
            "dashboard.empty_cta",
            "dashboard.filters_title",
            "profile.tab_search",
            "profile.tab_accounts",
            "profile.tab_alerts",
            "profile.tab_security",
            "profile.geo_section",
            "profile.password_section",
            "profile.current_password",
            "profile.new_password",
            "profile.confirm_password",
            "profile.change_password",
            "profile.password_mismatch",
            "profile.photo.title",
            "profile.photo.upload",
            "profile.photo.remove",
            "profile.delete_kicker",
            "profile.delete_title",
            "profile.delete_button",
        ):
            assert key in data, f"missing {key} in {locale}.json"
            assert str(data[key]).strip()


def test_theme_contains_dashboard_and_profile_layout_classes():
    css = _read("ui/theme.py")
    for class_name in (
        "stat-card-grid",
        "stat-card",
        "empty-panel",
        "dash-meta-pills",
        "dash-meta-pill",
        "job-card-head",
        "job-score-badge",
        "score-chip",
        "profile-chip-row",
        "profile-chip",
        "filter-bar-title",
        "profile-divider",
        "sidebar-avatar-ring",
        "danger-zone",
        "danger-zone-kicker",
        "danger-zone-title",
    ):
        assert f".{class_name}" in css, class_name


def test_dashboard_page_uses_compact_layout():
    source = _read("app.py")
    assert "empty-panel" in source
    assert "stat-card-grid" in source
    assert "job-card-head" in source
    assert "job-score-badge" in source
    assert "score-chip" in source
    assert 'st.radio(' in source
    assert 'profile_section' in source
    assert 't("profile.tab_search")' in source
    assert 't("profile.password_section")' in source
    assert "render_connected_accounts_section(profile)" in source
    assert "render_notification_settings(user, job_provider)" in source
    assert "render_delete_account_section(user)" in source
    assert "danger-zone" in source
    assert 'key="logout_button"' in source
    assert "st-key-logout_button" in _read("ui/theme.py")
    assert "height: 100vh !important" in _read("ui/theme.py")
    assert "dashboard_empty_cta" in source
    assert "_render_profile_photo_editor" in source
    assert "sidebar-avatar-ring" in source


def test_profile_and_dashboard_do_not_double_the_page_hero():
    source = _read("app.py")
    profile_branch = source.split('if page == "profile":', 1)[1].split("if page ==", 1)[0]
    dashboard_branch = source.split('if page == "dashboard":', 1)[1].split(
        "render_page_hero(", 1
    )[0]
    assert "render_page_hero" not in profile_branch
    assert "render_page_hero" not in dashboard_branch
    assert "render_dashboard_page(user)" in dashboard_branch
    assert "render_profile_page(user, job_provider)" in profile_branch
