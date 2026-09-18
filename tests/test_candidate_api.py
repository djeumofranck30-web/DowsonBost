"""Candidate FastAPI — Streamlit reads these routes instead of the database."""

from __future__ import annotations

from auth import authenticate_user, register_user
from persistence import record_application, save_analysis


def _register(email: str, name: str = "Jane Doe") -> dict:
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


def _client():
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)


def _token(client, email: str) -> str:
    return client.post(
        "/auth/login",
        json={"email": email, "password": "Secret123!"},
    ).json()["access_token"]


def test_login_returns_token_and_full_profile(sqlite_db):
    _register("jane.api@example.com")
    client = _client()
    response = client.post(
        "/auth/login",
        json={"email": "jane.api@example.com", "password": "Secret123!"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "jane.api@example.com"
    assert body["user"]["target_job_title"] == "Developer"
    assert "password_hash" not in body["user"]


def test_register_via_api_then_login(sqlite_db):
    client = _client()
    created = client.post(
        "/auth/register",
        json={
            "full_name": "Ali Martin",
            "email": "ali.api@example.com",
            "password": "Secret123!",
            "target_job_title": "Data Analyst",
            "selected_countries": ["France"],
            "admin_regions": ["Île-de-France"],
            "selected_departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
            "selected_cities": ["Paris"],
        },
    )
    assert created.status_code == 200, created.text
    login = client.post(
        "/auth/login",
        json={"email": "ali.api@example.com", "password": "Secret123!"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["full_name"] == "Ali Martin"


def test_workspace_requires_auth(sqlite_db):
    client = _client()
    assert client.get("/me/workspace").status_code == 401


def test_workspace_bundles_dashboard_payload(sqlite_db):
    user = _register("jane.workspace@example.com")
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
            "jobs_raw": 2,
            "search_strategy": "demo",
            "search_query_used": "Developer",
            "job_provider": "wttj",
            "results": [
                {
                    "job": {"title": "Dev", "company": "Acme", "url": "https://example.com/1"},
                    "match": {"score_correspondance": 88},
                }
            ],
        },
        cv_fingerprint="api-workspace",
    )
    stored = __import__("persistence", fromlist=["get_analysis"]).get_analysis(
        int(user["id"]), analysis_id
    )
    result_id = stored["results"][0]["result_id"]
    record_application(int(user["id"]), result_id, "manual", status="applied")

    client = _client()
    headers = {"Authorization": f"Bearer {_token(client, 'jane.workspace@example.com')}"}
    workspace = client.get("/me/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    body = workspace.json()
    assert body["profile"]["email"] == "jane.workspace@example.com"
    assert body["application_count"] == 1
    assert body["control_center"]["applied"] >= 1
    assert body["analyses"][0]["id"] == analysis_id
    assert body["analyses"][0]["job_provider"] == "wttj"

    dashboard = client.get(f"/analyses/{analysis_id}/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    rows = dashboard.json()["results"]
    assert rows[0]["job"]["company"] == "Acme"
    assert "description" not in rows[0]["job"]

    session = client.get(f"/analyses/{analysis_id}", headers=headers)
    assert session.status_code == 200
    assert session.json()["analysis_id"] == analysis_id
    assert session.json()["results"][0]["job"]["title"] == "Dev"


def test_record_application_and_status_via_api(sqlite_db):
    user = _register("jane.apply@example.com")
    analysis_id = save_analysis(
        int(user["id"]),
        {
            "cv_text": "CV",
            "criteria": {},
            "user_profile": {},
            "target_job_title": "Developer",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 1,
            "search_strategy": "demo",
            "search_query_used": "Developer",
            "job_provider": "wttj",
            "results": [
                {
                    "job": {"title": "Dev", "company": "Acme", "url": "https://example.com/2"},
                    "match": {"score_correspondance": 70},
                }
            ],
        },
        cv_fingerprint="api-apply",
    )
    stored = __import__("persistence", fromlist=["get_analysis"]).get_analysis(
        int(user["id"]), analysis_id
    )
    result_id = stored["results"][0]["result_id"]
    client = _client()
    headers = {"Authorization": f"Bearer {_token(client, 'jane.apply@example.com')}"}
    created = client.post(
        "/applications",
        headers=headers,
        json={"result_id": result_id, "channel": "manual", "status": "saved", "notes": "ok"},
    )
    assert created.status_code == 200, created.text
    patched = client.patch(
        f"/applications/{result_id}",
        headers=headers,
        json={"status": "applied", "notes": "envoyé"},
    )
    assert patched.status_code == 200, patched.text
    apps = client.get("/applications", headers=headers).json()["applications"]
    assert apps[0]["application_status"] == "applied"


def test_frontend_store_falls_back_without_http(sqlite_db):
    from services import frontend_store as store

    store._BACKEND_READY = False
    store.clear_access_token()
    ok, message = store.register_user(
        "Sam Store",
        "sam.store@example.com",
        "Secret123!",
        target_job_title="Developer",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, message
    logged, _, user = store.authenticate_user("sam.store@example.com", "Secret123!")
    assert logged and user is not None
    assert user["email"] == "sam.store@example.com"
    assert store.list_analyses(int(user["id"])) == []
