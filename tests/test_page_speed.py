"""Faster page loads: compact cards, fewer queries, no blocking webfonts."""

from __future__ import annotations

import inspect
from pathlib import Path

from constants import JOB_CARDS_PER_PAGE, PROFILE_PHOTO_SIDEBAR_PX
from persistence import (
    analysis_to_session_dict,
    count_user_applications,
    get_analysis,
    get_analysis_apply_context,
    get_analysis_result,
    list_dashboard_results,
    list_user_applications,
    record_application,
    save_analysis,
    save_generated_documents,
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
    assert JOB_CARDS_PER_PAGE == 25
    assert "JOB_CARDS_PER_PAGE" in source
    assert "_paged_items(" in source
    assert 'f"job_open_{result_id or rank}"' in source
    assert 't("job.toggle_details")' in source
    assert "get_analysis_apply_context" in source
    assert source.count("list_dashboard_results(") == 1
    assert "connected_accounts=" in source
    assert 'key="profile_section"' in source
    assert 'key="applications_channel"' in source
    assert "_hydrate_analysis_result" in source
    assert "get_analysis_results_by_ids" in source
    assert "cached_sidebar_photo_data_url" in source
    assert 'key="sidebar_job_provider"' in source


def test_job_provider_widget_is_analysis_page_only():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_app = source.split("def render_app()", 1)[1].split("def main()", 1)[0]
    assert render_app.index('if page == "analysis":') < render_app.index(
        'key="sidebar_job_provider"'
    )
    assert render_app.count('key="sidebar_job_provider"') == 1


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
    assert "fastReruns = true" in config


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


def _save_heavy_analysis(email: str) -> tuple[int, int]:
    ok, msg = register_user("Jane Doe", email, "Secret123!", **_register_kwargs())
    assert ok, msg
    ok_login, _, user = authenticate_user(email, "Secret123!")
    assert ok_login
    user_id = int(user["id"])
    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "CV Jane " * 40,
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
                    "job": {
                        "title": "Dev",
                        "company": "Acme",
                        "location": "Paris",
                        "url": "https://example.com/1",
                        "description": "LONG JOB DESCRIPTION " * 80,
                    },
                    "match": {
                        "score_correspondance": 88,
                        "score_competences": 90,
                        "synthese_ats": "Bon match",
                        "analyse_competences": {"presentes": ["Python"] * 20},
                    },
                }
            ],
        },
        cv_fingerprint=f"speed-{email}",
    )
    stored = get_analysis(user_id, analysis_id)
    result_id = stored["results"][0]["result_id"]
    save_generated_documents(
        user_id,
        result_id,
        cover_letter_text="LETTRE " * 200,
        adapted_cv_text="CV ADAPTE " * 200,
    )
    return user_id, analysis_id


def test_dashboard_list_skips_documents_and_job_body(sqlite_db):
    source = inspect.getsource(list_dashboard_results)
    assert "cover_letter_text" not in source
    assert "adapted_cv_text" not in source
    assert "ar.job_json," not in source.replace(" ", "")
    assert "ar.match_json," not in source.replace(" ", "")

    user_id, analysis_id = _save_heavy_analysis("jane.list@example.com")
    rows = list_dashboard_results(user_id, analysis_id=analysis_id)
    assert len(rows) == 1
    entry = rows[0]
    assert "cover_letter_text" not in entry
    assert "adapted_cv_text" not in entry
    assert "description" not in entry["job"]
    assert "analyse_competences" not in entry["match"]
    assert entry["job"]["company"] == "Acme"
    assert entry["job"]["title"] == "Dev"
    assert entry["match"]["score_correspondance"] == 88
    assert entry["match"]["synthese_ats"] == "Bon match"

    full = get_analysis_result(user_id, entry["result_id"])
    assert full is not None
    assert "LONG JOB DESCRIPTION" in full["job"]["description"]
    assert full["cover_letter_text"].startswith("LETTRE")
    assert full["adapted_cv_text"].startswith("CV ADAPTE")


def test_session_analysis_omits_heavy_result_payloads(sqlite_db):
    user_id, analysis_id = _save_heavy_analysis("jane.session@example.com")
    stored = get_analysis(user_id, analysis_id)
    session = analysis_to_session_dict(stored)
    result = session["results"][0]
    assert "cover_letter_text" not in result
    assert "adapted_cv_text" not in result
    assert "description" not in result["job"]
    assert result["job"]["company"] == "Acme"
    assert "analyse_competences" not in result["match"]


def test_application_list_skips_documents_until_hydrated(sqlite_db):
    source = inspect.getsource(list_user_applications)
    assert "cover_letter_text" not in source
    assert "adapted_cv_text" not in source

    user_id, analysis_id = _save_heavy_analysis("jane.apps@example.com")
    stored = get_analysis(user_id, analysis_id)
    result_id = stored["results"][0]["result_id"]
    record_application(user_id, result_id, "manual", status="applied")
    applications = list_user_applications(user_id)
    assert len(applications) == 1
    assert "cover_letter_text" not in applications[0]
    assert applications[0]["job"]["company"] == "Acme"
    assert "description" not in applications[0]["job"]


def test_sqlite_reuses_thread_connection(sqlite_db):
    from database import connect

    ids = []
    with connect() as conn:
        ids.append(id(conn))
    with connect() as conn:
        ids.append(id(conn))
    assert ids[0] == ids[1]


def test_sidebar_photo_payload_is_smaller_than_profile_photo(sqlite_db):
    from PIL import Image
    from io import BytesIO

    from services.profile_photo import profile_photo_data_url, save_profile_photo

    ok, msg = register_user(
        "Jane Doe", "jane.photo.speed@example.com", "Secret123!", **_register_kwargs()
    )
    assert ok, msg
    ok_login, _, user = authenticate_user("jane.photo.speed@example.com", "Secret123!")
    assert ok_login
    image = Image.new("RGB", (80, 80), color=(14, 116, 144))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    ok, reason = save_profile_photo(int(user["id"]), buffer.getvalue(), "image/png")
    assert ok, reason
    full = profile_photo_data_url(int(user["id"]))
    small = profile_photo_data_url(int(user["id"]), size_px=PROFILE_PHOTO_SIDEBAR_PX)
    assert full and small
    assert len(small) < len(full)
