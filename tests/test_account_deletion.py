"""Account deletion must erase the user and every related record."""

from __future__ import annotations

from auth import (
    authenticate_user,
    create_password_reset_token,
    delete_user_account,
    get_user_by_id,
    register_user,
)
from database import adapt_sql, connect
import persistence
from persistence import (
    connect_job_account,
    init_persistence_tables,
    list_analyses,
    list_user_applications,
    log_scheduled_run,
    record_application,
    save_analysis,
    save_notification_settings,
    upsert_active_cv_document,
)


def _reset_persistence() -> None:
    persistence._persistence_initialized_for = None


def _register_jane() -> int:
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
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


def _count_for_user(table: str, user_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            adapt_sql(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?"),
            (user_id,),
        ).fetchone()
    return int(row["n"])


def test_delete_unknown_user_fails(sqlite_db):
    ok, msg = delete_user_account(999_999)
    assert not ok
    assert msg


def test_delete_user_account_removes_all_personal_data(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()

    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "CV confidentiel de Jane",
            "criteria": {"poste": "Developer"},
            "user_profile": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "target_job_title": "Developer",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 1,
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
                }
            ],
        },
        cv_fingerprint="abc123",
    )
    stored = persistence.get_analysis(user_id, analysis_id)
    assert stored is not None
    result_id = stored["results"][0]["result_id"]
    assert record_application(user_id, result_id, "manual", status="applied")
    upsert_active_cv_document(user_id, "abc123", "CV confidentiel de Jane")
    save_notification_settings(user_id, {"email_alerts_enabled": True, "alert_min_score": 80})
    log_scheduled_run(user_id, "success", analysis_id=analysis_id, trigger_source="app")
    assert connect_job_account(user_id, "indeed", "jane@example.com")[0]
    ok_token, _, token = create_password_reset_token("jane@example.com")
    assert ok_token and token

    assert _count_for_user("analyses", user_id) == 1
    assert _count_for_user("analysis_results", user_id) == 1
    assert _count_for_user("cv_documents", user_id) == 1
    assert _count_for_user("user_notification_settings", user_id) == 1
    assert _count_for_user("scheduled_runs", user_id) == 1
    assert _count_for_user("password_reset_tokens", user_id) == 1
    assert _count_for_user("user_connected_accounts", user_id) == 1
    assert list_analyses(user_id)
    assert list_user_applications(user_id)

    ok, msg = delete_user_account(user_id)
    assert ok, msg

    assert get_user_by_id(user_id) is None
    ok_login, login_msg, logged_in = authenticate_user("jane@example.com", "Secret123!")
    assert not ok_login
    assert logged_in is None
    assert "e-mail" in login_msg.lower() or "email" in login_msg.lower()

    assert _count_for_user("analyses", user_id) == 0
    assert _count_for_user("analysis_results", user_id) == 0
    assert _count_for_user("cv_documents", user_id) == 0
    assert _count_for_user("user_notification_settings", user_id) == 0
    assert _count_for_user("scheduled_runs", user_id) == 0
    assert _count_for_user("password_reset_tokens", user_id) == 0
    assert _count_for_user("user_connected_accounts", user_id) == 0
    assert list_analyses(user_id) == []
    assert list_user_applications(user_id) == []

    ok_again, msg_again = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok_again, msg_again
    ok_login, _, new_user = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login and new_user is not None
    assert int(new_user["id"]) != user_id
    assert new_user["email"] == "jane@example.com"
    assert new_user["full_name"] == "Jane Doe"


def test_deleted_email_can_be_reused_with_new_password(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()
    assert delete_user_account(user_id)[0]

    ok, msg = register_user(
        "Jane Doe",
        "JANE@example.com",
        "NewSecret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok_old, _, _ = authenticate_user("jane@example.com", "Secret123!")
    assert not ok_old
    ok_new, _, user = authenticate_user("jane@example.com", "NewSecret123!")
    assert ok_new and user is not None
    assert int(user["id"]) != user_id
