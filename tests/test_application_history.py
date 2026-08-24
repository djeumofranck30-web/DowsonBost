"""Tests for application history persistence."""

from __future__ import annotations

from auth import authenticate_user, init_db, register_user
import persistence
from persistence import (
    get_analysis,
    init_persistence_tables,
    list_user_applications,
    record_application,
    save_analysis,
    update_application_status,
)


def _reset_persistence() -> None:
    persistence._persistence_initialized_for = None


def _register_test_user() -> int:
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Dev Python",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok_login, _, user = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login and user is not None
    return int(user["id"])


def test_list_user_applications_groups_manual_and_automatic(sqlite_db):
    _reset_persistence()
    init_db()
    init_persistence_tables()
    user_id = _register_test_user()

    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "CV",
            "criteria": {},
            "user_profile": {"full_name": "Jane Doe"},
            "target_job_title": "Dev Python",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 2,
            "jobs_raw": 2,
            "job_provider": "adzuna",
            "results": [
                {
                    "job": {
                        "title": "Backend Dev",
                        "company": "Acme",
                        "location": "Paris",
                        "url": "https://example.com/1",
                        "description": "",
                    },
                    "match": {"score_correspondance": 82},
                },
                {
                    "job": {
                        "title": "Data Engineer",
                        "company": "Beta",
                        "location": "Lyon",
                        "url": "https://example.com/2",
                        "description": "",
                    },
                    "match": {"score_correspondance": 75},
                },
            ],
        },
        cv_fingerprint="fp1",
    )

    stored = get_analysis(user_id, analysis_id)
    assert stored is not None
    result_ids = [entry["result_id"] for entry in stored["results"]]

    assert record_application(user_id, result_ids[0], "auto_email", status="applied")
    assert record_application(user_id, result_ids[1], "manual", status="applied")

    applications = list_user_applications(user_id)
    assert len(applications) == 2
    auto = [entry for entry in applications if entry["channel"] == "automatic"]
    manual = [entry for entry in applications if entry["channel"] == "manual"]
    assert len(auto) == 1
    assert len(manual) == 1
    assert auto[0]["application_method"] == "auto_email"
    assert manual[0]["application_method"] == "manual"


def test_legacy_applied_status_without_method_is_manual(sqlite_db):
    _reset_persistence()
    init_db()
    init_persistence_tables()
    user_id = _register_test_user()

    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "CV",
            "criteria": {},
            "user_profile": {"full_name": "Jane Doe"},
            "target_job_title": "Analyst",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 1,
            "job_provider": "adzuna",
            "results": [
                {
                    "job": {
                        "title": "Analyst",
                        "company": "Corp",
                        "location": "Remote",
                        "url": "https://example.com/3",
                        "description": "",
                    },
                    "match": {"score_correspondance": 70},
                }
            ],
        },
        cv_fingerprint="fp2",
    )
    stored = get_analysis(user_id, analysis_id)
    assert stored is not None
    result_id = stored["results"][0]["result_id"]
    assert update_application_status(user_id, result_id, "applied", notes="Legacy")

    applications = list_user_applications(user_id)
    assert len(applications) == 1
    assert applications[0]["channel"] == "manual"
    assert applications[0]["application_method"] is None
