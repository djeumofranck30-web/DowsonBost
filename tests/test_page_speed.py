"""Faster page loads: compact cards, fewer queries, no blocking webfonts."""

from __future__ import annotations

from pathlib import Path

from constants import JOB_CARDS_PER_PAGE
from persistence import (
    count_user_applications,
    get_analysis,
    get_analysis_apply_context,
    record_application,
    save_analysis,
)
from auth import authenticate_user, register_user

ROOT = Path(__file__).resolve().parents[1]


def _register_kwargs(**overrides):
    data = {
        "target_job_title": "Developer",
        "contract_type": "CDI",
        "experience_level": "confirme",
        "selected_countries": ["France"],
        "admin_regions": ["Île-de-France"],
        "selected_departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "selected_cities": ["Paris"],
    }
    data.update(overrides)
    return data


def test_job_cards_are_paginated_and_collapsed_by_default():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert JOB_CARDS_PER_PAGE == 8
    assert "JOB_CARDS_PER_PAGE" in source
    assert "_paged_items(" in source
    assert 'f"job_open_{result_id or rank}"' in source
    assert 't("job.toggle_details")' in source
    assert "get_analysis_apply_context" in source
    assert source.count("list_dashboard_results(") == 1
    assert "connected_accounts=" in source
    assert 'key="profile_section"' in source
    assert 'key="applications_channel"' in source


def test_theme_does_not_block_on_google_fonts():
    theme = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    admin = (ROOT / "admin/static/index.html").read_text(encoding="utf-8")
    chrome = (ROOT / "pages/dashboard.py").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in theme
    assert "fonts.googleapis.com" not in admin
    assert "fonts.googleapis.com" not in chrome
    assert "Plus Jakarta Sans" not in theme
    assert "#0E7490" in config


def test_heavy_pdf_libraries_are_imported_lazily():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    header, _, _ = source.partition("def extract_text_native")
    assert "import fitz" not in header
    assert "import pdfplumber" not in header
    assert "import fitz" in source
    assert "import pdfplumber" in source


def test_filter_dashboard_entries_keeps_matching_rows():
    from app import _filter_dashboard_entries, _status_counts_from_entries

    entries = [
        {
            "score": 80,
            "application_status": "saved",
            "job": {"company": "Acme"},
            "analysis_created_at": "2026-01-02",
        },
        {
            "score": 40,
            "application_status": "new",
            "job": {"company": "Globex"},
            "analysis_created_at": "2026-01-01",
        },
    ]
    filtered = _filter_dashboard_entries(
        entries,
        status_filter="saved",
        min_score=50,
        company_query="acme",
        sort_by="score_desc",
    )
    assert len(filtered) == 1
    assert filtered[0]["job"]["company"] == "Acme"
    counts = _status_counts_from_entries(entries)
    assert counts["all"] == 2
    assert counts["saved"] == 1
    assert counts["new"] == 1


def test_apply_context_skips_full_analysis_payload(sqlite_db):
    ok, msg = register_user("Jane Doe", "jane.speed@example.com", "Secret123!", **_register_kwargs())
    assert ok, msg
    ok_login, _, user = authenticate_user("jane.speed@example.com", "Secret123!")
    assert ok_login
    analysis_id = save_analysis(
        int(user["id"]),
        {
            "cv_text": "CV Jane",
            "criteria": {},
            "user_profile": {"full_name": "Jane Doe"},
            "target_job_title": "Developer",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 3,
            "search_strategy": "demo",
            "search_query_used": "Developer",
            "job_provider": "adzuna",
            "results": [
                {
                    "job": {"title": "Dev", "company": "Acme", "url": "https://example.com/1"},
                    "match": {"score_correspondance": 88},
                }
            ],
        },
        cv_fingerprint="speed-demo",
    )
    ctx = get_analysis_apply_context(int(user["id"]), analysis_id)
    assert ctx is not None
    assert ctx["cv_text"] == "CV Jane"
    assert ctx["user_profile"]["full_name"] == "Jane Doe"
    assert "results" not in ctx
    stored = get_analysis(int(user["id"]), analysis_id)
    result_id = stored["results"][0]["result_id"]
    record_application(int(user["id"]), result_id, "manual", status="applied")
    assert count_user_applications(int(user["id"])) == 1
