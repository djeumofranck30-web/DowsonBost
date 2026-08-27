"""Admin dashboard backend tests."""

from __future__ import annotations

from auth import authenticate_admin, authenticate_user, register_user, user_is_admin
from persistence import save_analysis
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


def _admin_session(email: str = "boss@example.com", user_id: int = 0) -> dict:
    return {
        "id": user_id,
        "email": email,
        "full_name": "Administrateur",
        "is_admin": True,
        "admin_authenticated": True,
    }


def test_get_admin_accounts_from_env(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_ACCOUNTS", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", "one@example.com, two@example.com")
    monkeypatch.setenv("ADMIN_PASSWORDS", '["pass-one", "pass-two"]')
    from config import get_admin_accounts, get_admin_emails

    assert get_admin_emails() == frozenset({"one@example.com", "two@example.com"})
    assert get_admin_accounts() == [
        ("one@example.com", "pass-one"),
        ("two@example.com", "pass-two"),
    ]


def test_emails_without_passwords_are_not_admins(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    monkeypatch.delenv("ADMIN_PASSWORDS", raising=False)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_ACCOUNTS", raising=False)
    from config import get_admin_accounts

    assert get_admin_accounts() == []


def test_admin_secret_login_does_not_need_a_user_account(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    ok, msg, admin = authenticate_admin("boss@example.com", "AdminPass123!")
    assert ok, msg
    assert admin is not None
    assert user_is_admin(admin)
    assert admin["email"] == "boss@example.com"


def test_wrong_admin_password_is_rejected(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    ok, msg, admin = authenticate_admin("boss@example.com", "bad")
    assert not ok
    assert admin is None
    assert "incorrect" in msg.lower()


def test_regular_user_is_not_admin_even_with_listed_email(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "jane@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    user = _register("jane@example.com")
    assert not user_is_admin(user)


def test_overview_includes_users_and_tokens(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
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
    assert overview["kpis"]["users_total"] == 1
    assert overview["kpis"]["tokens_total"] == 150
    jane = next(item for item in overview["users"] if item["email"] == "jane@example.com")
    assert jane["tokens_consumed"] == 150
    assert overview["support"]["unread"] == 0
    spaces = overview["support"]["conversations"]
    assert {item["email"] for item in spaces} == {"jane@example.com"}
    assert spaces[0]["has_messages"] is False
    listed = list_registered_users()
    assert {row["email"] for row in listed} == {"jane@example.com"}
    assert overview["kpis"]["matches_total"] == 0
    assert overview["analysis"]["kpis"]["matches_total"] == 0
    assert overview["analysis"]["recent_runs"] == []
    assert overview["analysis"]["top_matches"] == []


def test_overview_surfaces_analysis_results(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    member = _register("jane@example.com")
    save_analysis(
        int(member["id"]),
        {
            "cv_text": "CV Jane",
            "criteria": {},
            "user_profile": {"full_name": "Jane Doe"},
            "target_job_title": "Développeuse Python",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 2,
            "jobs_raw": 8,
            "job_provider": "wttj",
            "results": [
                {
                    "job": {
                        "title": "Backend engineer",
                        "company": "Acme",
                        "location": "Paris",
                        "url": "https://example.com/1",
                    },
                    "match": {"score_correspondance": 88},
                },
                {
                    "job": {
                        "title": "Data analyst",
                        "company": "Nova",
                        "location": "Lyon",
                        "url": "https://example.com/2",
                    },
                    "match": {"score_correspondance": 41},
                },
            ],
        },
        cv_fingerprint="dash-quality",
    )
    overview = platform_overview()
    assert overview["kpis"]["analyses_total"] == 1
    assert overview["kpis"]["matches_total"] == 2
    assert overview["kpis"]["high_matches"] == 1
    assert overview["kpis"]["avg_score"] == 64.5
    bands = {item["key"]: item["count"] for item in overview["analysis"]["score_bands"]}
    assert bands == {"high": 1, "mid": 0, "low": 1}
    assert overview["analysis"]["recent_runs"][0]["target_job_title"] == "Développeuse Python"
    assert overview["analysis"]["top_matches"][0]["job_title"] == "Backend engineer"
    assert overview["analysis"]["top_matches"][0]["score"] == 88
    assert overview["analysis"]["by_title"][0]["title"] == "Développeuse Python"


def test_admin_cannot_delete_linked_self(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    admin_user = _register("boss@example.com", "Boss")
    ok, msg = admin_delete_user(
        _admin_session(user_id=int(admin_user["id"])),
        int(admin_user["id"]),
    )
    assert not ok
    assert "propre compte" in msg.lower()


def test_admin_can_delete_member(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    member = _register("jane@example.com")
    ok, msg = admin_delete_user(_admin_session(), int(member["id"]))
    assert ok, msg
    emails = {row["email"] for row in list_registered_users()}
    assert "jane@example.com" not in emails


def test_member_cannot_delete_via_admin_helper(sqlite_db):
    member = _register("other@example.com", "Other")
    ok, msg = admin_delete_user(int(member["id"]), int(member["id"]))
    assert not ok
    assert "administrateurs" in msg.lower()


def test_dashboard_html_injects_payload(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    _register("jane@example.com")
    html = dashboard_html(platform_overview(), embedded=True)
    assert "Chart.js" in html or "chart.js" in html.lower()
    assert "window.__DOWSONBOST_ADMIN__" in html
    assert "users_total" in html
    assert '"embedded": true' in html
    assert "data-tab=\"support\"" in html
    assert "id=\"recent-runs\"" in html
    assert "id=\"top-matches\"" in html
    assert "id=\"kpi-avg-score\"" in html
    assert "chart-score-bands" in html
    assert "chart-quality" in html
    assert "renderAnalysisBoard" in html


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
