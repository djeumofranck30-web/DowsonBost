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
            "dashboard.quality_title",
            "overview.shortcuts_title",
            "overview.go_diagnostic",
            "nav.events",
            "hero.events.title",
            "workspace.context_title",
            "dashboard.metric_avg_score",
            "dashboard.top_matches",
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
            "profile.freelance_mode",
            "profile.freelance_locked_help",
            "profile.search_mode",
            "profile.search_mode.emploi",
            "profile.search_mode.freelance",
            "profile.daily_rate",
            "profile.portfolio_url",
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
        "dash-quality",
        "dash-score-ring",
        "dash-top-match",
        "overview-kpi-grid",
        "workspace-context",
    ):
        assert f".{class_name}" in css, class_name


def test_dashboard_page_uses_compact_layout():
    source = _read("app.py")
    assert "empty-panel" in source
    assert "stat-card-grid" in source
    assert "dash-quality" in source
    assert "dashboard_quality_summary" in source
    assert "_render_dashboard_quality_board" in source
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
    assert "sidebar-flex-spacer" in source
    theme = _read("ui/theme.py")
    assert "st-key-logout_button" in theme
    assert "height: 100vh !important" in theme
    logout_css = theme.split('[class*="st-key-logout_button"]', 1)[1]
    assert "margin-top: auto !important" in logout_css
    assert "bottom: 0" in logout_css.split("[data-testid=", 1)[0]
    assert "dashboard_empty_cta" in source
    assert "_render_profile_photo_editor" in source
    assert "sidebar-avatar-ring" in source


def test_profile_form_keeps_only_skills_for_analysis():
    source = _read("app.py")
    body = source[
        source.index("skills_text = st.text_area(") : source.index(
            "profile.published_since"
        )
    ]
    assert 't("profile.skills")' in body
    assert 't("profile.diplomas")' not in body
    assert 't("profile.experiences")' not in body
    assert 't("profile.portfolio_url")' not in body
    assert "st.text_input(" not in body


def test_freelance_fields_stay_locked_until_checked():
    source = _read("app.py")
    radio_at = source.index('key=f"{widget_prefix}_search_mode"')
    form_at = source.index('with st.form("profile_form"):')
    assert radio_at < form_at
    freelance_block = source[radio_at:form_at]
    assert "disabled=not freelance_mode" in freelance_block
    assert freelance_block.count("disabled=not freelance_mode") >= 2
    assert 't("profile.daily_rate")' in freelance_block
    assert 't("profile.portfolio_url")' in freelance_block
    assert 't("profile.freelance_locked_help")' in freelance_block
    assert "disabled=freelance_mode" in source
    assert 'key=f"{widget_prefix}_contract"' in source
    assert 'contract_type = "Freelance"' in source
    assert "SEARCH_MODES" in source


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
    source = _read("app.py")
    assert "retain_multiselect_session(" in source
    assert "clear_profile_widget_keys(st.session_state" in source
    assert 'key=f"{widget_prefix}_target_job"' in source
