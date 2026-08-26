"""Admin dashboard backend tests."""

from __future__ import annotations

from auth import authenticate_user, register_user, user_is_admin
from services.admin import admin_delete_user, dashboard_html, list_registered_users, platform_overview
from services.llm_usage import estimate_tokens, record_llm_usage


def _register(email: str, name: str = "Jane Doe"):
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


def test_get_admin_emails_from_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "one@example.com, two@example.com")
    from config import get_admin_emails

    assert get_admin_emails() == frozenset({"one@example.com", "two@example.com"})


def test_admin_email_is_promoted_on_login(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    user = _register("boss@example.com", "Boss")
    assert user_is_admin(user)
    assert user["is_admin"] is True
    assert user.get("last_login_at")


def test_regular_user_is_not_admin(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    user = _register("jane@example.com")
    assert not user_is_admin(user)


def test_overview_includes_users_and_tokens(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    admin = _register("boss@example.com", "Boss")
    member = _register("jane@example.com")
    record_llm_usage(
        provider="groq",
        model="test",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        user_id=int(member["id"]),
    )
    overview = platform_overview()
    assert overview["kpis"]["users_total"] == 2
    assert overview["kpis"]["tokens_total"] == 150
    emails = {item["email"] for item in overview["users"]}
    assert emails == {"boss@example.com", "jane@example.com"}
    jane = next(item for item in overview["users"] if item["email"] == "jane@example.com")
    assert jane["tokens_consumed"] == 150
    listed = list_registered_users()
    assert {row["email"] for row in listed} == emails
    assert admin["email"] == "boss@example.com"


def test_admin_cannot_delete_self(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    admin = _register("boss@example.com", "Boss")
    ok, msg = admin_delete_user(int(admin["id"]), int(admin["id"]))
    assert not ok
    assert "propre compte" in msg.lower()


def test_admin_can_delete_member(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    admin = _register("boss@example.com", "Boss")
    member = _register("jane@example.com")
    ok, msg = admin_delete_user(int(admin["id"]), int(member["id"]))
    assert ok, msg
    emails = {row["email"] for row in list_registered_users()}
    assert "jane@example.com" not in emails
    assert "boss@example.com" in emails


def test_cannot_delete_last_admin(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    admin = _register("boss@example.com", "Boss")
    other = _register("other@example.com", "Other")
    ok, msg = admin_delete_user(int(other["id"]), int(admin["id"]))
    assert not ok
    assert "administrateurs" in msg.lower()


def test_dashboard_html_injects_payload(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    _register("boss@example.com", "Boss")
    html = dashboard_html(platform_overview(), embedded=True)
    assert "Chart.js" in html or "chart.js" in html.lower()
    assert "window.__DOWSONBOST_ADMIN__" in html
    assert "users_total" in html
    assert '"embedded": true' in html


def test_estimate_tokens_minimum():
    assert estimate_tokens("") >= 1
    assert estimate_tokens("abcd" * 10) == 10


def test_config_tests_only_on_admin_dashboard():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app_src = (root / "app.py").read_text(encoding="utf-8")
    dash_src = (root / "pages" / "dashboard.py").read_text(encoding="utf-8")
    assert "def render_config_tests_panel" in app_src
    assert "render_config_tests_panel" in dash_src
    candidate_shell = app_src.split("def render_app()", 1)[1]
    assert "render_config_tests_panel" not in candidate_shell
    assert 't("app.config_tests")' not in candidate_shell
