"""Admin activity journal and incident alerts."""

from __future__ import annotations

from auth import authenticate_user, register_user
from services.admin import dashboard_html, platform_overview
from services.admin_events import (
    list_admin_alerts,
    list_admin_events,
    mark_admin_events_read,
    record_admin_event,
    record_llm_quota,
    unread_admin_alert_count,
)
from services.analysis_queue import enqueue_analysis_job, fail_analysis_job
from services.support import send_user_support_message


def _register(email: str = "jane@example.com", name: str = "Jane Doe"):
    ok, msg = register_user(
        name,
        email,
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
    ok_login, _, user = authenticate_user(email, "Secret123!")
    assert ok_login and user is not None
    return user


def test_register_and_login_are_logged(sqlite_db):
    user = _register()
    kinds = {item["kind"] for item in list_admin_events(limit=50)}
    assert "user.register" in kinds
    assert "user.login" in kinds
    who = next(item for item in list_admin_events(limit=50) if item["kind"] == "user.register")
    assert who["user_email"] == "jane@example.com"
    assert who["user_id"] == int(user["id"])
    assert unread_admin_alert_count() == 0


def test_failed_login_creates_warning_alert(sqlite_db):
    _register()
    ok, _, user = authenticate_user("jane@example.com", "WrongPass1!")
    assert not ok
    assert user is None
    alerts = list_admin_alerts(unread_only=True)
    assert any(item["kind"] == "user.login_failed" for item in alerts)
    assert unread_admin_alert_count() >= 1


def test_analysis_failure_notifies_admin(sqlite_db):
    user = _register()
    job_id, err = enqueue_analysis_job(
        int(user["id"]),
        {"full_name": "Jane Doe", "email": "jane@example.com"},
        job_provider="wttj",
        analysis_depth="standard",
        cv_fingerprint="fp-fail",
        cv_text="CV Jane développeuse Python",
    )
    assert err == ""
    assert job_id
    fail_analysis_job(int(job_id), "Quota Groq atteint (rate limit)")
    alerts = list_admin_alerts(unread_only=True)
    quota = next(item for item in alerts if item["kind"] == "llm.quota")
    assert quota["severity"] == "error"
    assert quota["unread"] is True
    assert "Jane" in quota["user_name"] or quota["user_email"] == "jane@example.com"
    overview = platform_overview()
    assert overview["kpis"]["alerts_unread"] >= 1
    assert any(item["kind"] == "llm.quota" for item in overview["activity"]["alerts"])
    assert any(item["kind"] == "analysis.started" for item in overview["activity"]["events"])


def test_analysis_block_when_already_running(sqlite_db):
    user = _register()
    first, err = enqueue_analysis_job(
        int(user["id"]),
        {"full_name": "Jane Doe", "email": "jane@example.com"},
        job_provider="wttj",
        analysis_depth="standard",
        cv_fingerprint="fp-1",
        cv_text="CV Jane",
    )
    assert err == "" and first
    second, err2 = enqueue_analysis_job(
        int(user["id"]),
        {"full_name": "Jane Doe", "email": "jane@example.com"},
        job_provider="wttj",
        analysis_depth="standard",
        cv_fingerprint="fp-2",
        cv_text="CV Jane encore",
    )
    assert err2 == "already"
    assert second == first
    blocked = [item for item in list_admin_alerts() if item["kind"] == "analysis.blocked"]
    assert blocked
    assert "déjà" in blocked[0]["message"].lower() or "cours" in blocked[0]["message"].lower()


def test_llm_quota_is_deduped_while_unread(sqlite_db):
    _register()
    record_llm_quota(provider="groq", reason="quota / rate limit")
    record_llm_quota(provider="groq", reason="quota / rate limit")
    alerts = [item for item in list_admin_alerts(unread_only=True) if item["kind"] == "llm.quota"]
    assert len(alerts) == 1
    mark_admin_events_read(all_unread=True)
    assert unread_admin_alert_count() == 0
    record_llm_quota(provider="groq", reason="quota / rate limit")
    assert unread_admin_alert_count() == 1


def test_support_message_is_in_activity_feed(sqlite_db):
    user = _register()
    ok, msg, saved = send_user_support_message(int(user["id"]), "Bonjour, l'analyse est bloquée.")
    assert ok, msg
    assert saved
    events = [item for item in list_admin_events() if item["kind"] == "support.message"]
    assert events
    assert "bloquée" in events[0]["message"]


def test_mark_single_alert_read(sqlite_db):
    record_admin_event(
        "analysis.failed",
        title="Analyse en échec",
        message="Timeout pipeline",
        severity="error",
        user_email="pat@example.com",
        user_name="Pat",
        dedupe=False,
    )
    alerts = list_admin_alerts(unread_only=True)
    assert alerts
    updated = mark_admin_events_read([int(alerts[0]["id"])])
    assert updated == 1
    assert unread_admin_alert_count() == 0


def test_overview_html_includes_alert_board(sqlite_db):
    _register()
    fail_like = record_admin_event(
        "analysis.failed",
        title="Analyse en échec",
        message="Aucune offre après matching",
        severity="error",
        user_email="jane@example.com",
        user_name="Jane Doe",
        dedupe=False,
    )
    assert fail_like
    html = dashboard_html(platform_overview(), embedded=True)
    assert "Analyse en échec" in html
    assert "alerts_unread" in html
    assert "id=\"overview-alerts\"" in html
    assert "id=\"queue-board\"" in html
