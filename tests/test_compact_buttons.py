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
    assert 't("job.apply_manual_confirm")' in source
    assert 't("job.apply_auto")' in source
    assert 't("job.apply_manual_prepare")' not in source
    confirm_idx = source.index('t("job.apply_manual_confirm")')
    auto_idx = source.index('t("job.apply_auto")')
    assert auto_idx < confirm_idx


def test_dashboard_insight_locale_keys_exist():
    import json

    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        for key in (
            "dashboard.insights_title",
            "dashboard.chart_status",
            "dashboard.chart_scores",
            "dashboard.chart_count",
            "dashboard.quality_title",
            "dashboard.top_matches",
            "dashboard.band_high",
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


def test_dashboard_quality_summary_highlights_strong_matches():
    from app import dashboard_quality_summary

    summary = dashboard_quality_summary(
        [
            {
                "score": 88,
                "application_status": "applied",
                "job": {"title": "Backend", "company": "Acme", "location": "Paris"},
            },
            {
                "score": 40,
                "application_status": "new",
                "job": {"title": "Junior", "company": "Beta", "location": "Lyon"},
            },
            {
                "score": 91,
                "application_status": "saved",
                "job": {"title": "Lead", "company": "Nova", "location": "Lille"},
            },
        ]
    )
    assert summary["total"] == 3
    assert summary["high"] == 2
    assert summary["applied"] == 1
    assert summary["avg_score"] == 73.0
    assert summary["top"][0]["score"] == 91
    bands = {item["key"]: item["count"] for item in summary["bands"]}
    assert bands == {"high": 2, "mid": 0, "low": 1}


def test_theme_has_interactive_dashboard_panels():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert ".dash-chart-panel" in css
    assert ".stat-card:hover" in css
    assert ".dash-quality" in css
    assert ".dash-score-ring" in css
