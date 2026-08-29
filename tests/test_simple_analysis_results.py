"""Analysis page shows a simple ranked list; dashboard keeps full ATS cards."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _analysis_results_fn() -> str:
    source = _read("app.py")
    start = source.index("def render_analysis_results(")
    end = source.index("def init_session_state(", start)
    return source[start:end]


def test_analysis_results_use_simple_rows_not_full_cards() -> None:
    body = _analysis_results_fn()
    assert "render_simple_job_row(" in body
    assert "render_job_card(" not in body
    assert "render_cv_profile_summary(" not in body
    assert "results.cv_text_expander" not in body
    assert "results.filter_stats" not in body
    assert "results.open_dashboard" in body
    assert '_request_navigation("dashboard")' in body
    assert "cap_results_to_requested_best(" in body
    assert "_paged_items(" not in body
    assert "for idx, entry in enumerate(results, start=1):" in body
    assert "visible_results" not in body
    assert "page_size=12" not in body


def test_dashboard_still_renders_full_job_cards() -> None:
    source = _read("app.py")
    start = source.index("def render_dashboard_page(")
    end = source.index("def render_notification_settings(", start)
    body = source[start:end]
    assert "render_job_card(" in body
    assert "enable_tracking=True" in body
    assert "render_simple_job_row(" not in body
    assert "matching_display_limit(" in body


def test_finished_analysis_selects_dashboard_analysis() -> None:
    source = _read("app.py")
    start = source.index("def _sync_analysis_job_into_session(")
    end = source.index("def _enqueue_user_analysis_error(", start)
    body = source[start:end]
    assert "dashboard_analysis_select" in body


def test_simple_results_locale_keys_exist() -> None:
    for locale in ("fr", "en"):
        data = json.loads(_read(f"locales/{locale}.json"))
        for key in (
            "results.simple_summary",
            "results.simple_hint",
            "results.open_dashboard",
            "results.simple_title",
            "results.simple_score",
        ):
            assert key in data, f"missing {key} in {locale}.json"
            assert str(data[key]).strip()
    assert "tableau de bord" in json.loads(_read("locales/fr.json"))[
        "results.simple_hint"
    ].lower()


def test_simple_job_row_styles_exist() -> None:
    css = _read("ui/theme.py")
    assert ".job-match-card-simple" in css
    assert "render_simple_job_row" in _read("app.py")
    assert "job-match-card-simple" in _read("app.py")
