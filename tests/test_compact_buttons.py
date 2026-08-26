"""Compact button styling is applied globally."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_theme_compacts_streamlit_buttons():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "min-height: 2rem !important" in css
    assert ".stLinkButton a" in css
    assert '[data-testid^="stBaseLinkButton-"]' in css
    assert "padding: 0.22rem 0.75rem !important" in css


def test_admin_html_buttons_are_compact():
    html = (ROOT / "admin/static/index.html").read_text(encoding="utf-8")
    assert "padding: .32rem .75rem" in html
    assert "min-height: 2rem" in html


def test_application_actions_share_a_compact_row():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "pack_col1, pack_col2 = st.columns(2)" in source
    confirm_idx = source.index('t("job.apply_manual_confirm")')
    prepare_idx = source.index('t("job.apply_manual_prepare")')
    pack_idx = source.index("pack_col1, pack_col2 = st.columns(2)")
    assert pack_idx < confirm_idx < prepare_idx


def test_dashboard_insight_locale_keys_exist():
    import json

    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        for key in (
            "dashboard.insights_title",
            "dashboard.chart_status",
            "dashboard.chart_scores",
            "dashboard.chart_count",
        ):
            assert key in data, key


def test_dashboard_insight_rows_group_status_and_scores():
    from app import dashboard_insight_rows

    status_rows, score_rows = dashboard_insight_rows(
        [{"score": 88}, {"score": 40}, {"score": 91}],
        {
            "new": 1,
            "saved": 2,
            "applied": 0,
            "interview": 0,
            "offer": 0,
            "rejected": 0,
            "archived": 0,
        },
    )
    assert {"status": "Nouvelle", "count": 1} in status_rows
    assert {"status": "À postuler", "count": 2} in status_rows
    assert {"band": "0–49", "count": 1} in score_rows
    assert {"band": "75–89", "count": 1} in score_rows
    assert {"band": "90–100", "count": 1} in score_rows


def test_theme_has_interactive_dashboard_panels():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert ".dash-chart-panel" in css
    assert ".stat-card:hover" in css
