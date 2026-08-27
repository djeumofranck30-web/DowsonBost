"""Admin REST API tests."""

from __future__ import annotations

from auth import authenticate_user, register_user
from services.llm_usage import record_llm_usage


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


def _client():
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)


def test_admin_overview_requires_auth(sqlite_db):
    client = _client()
    response = client.get("/api/admin/overview")
    assert response.status_code == 401


def test_admin_overview_rejects_member(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    _register("jane@example.com")
    client = _client()
    token = client.post(
        "/auth/login",
        json={"email": "jane@example.com", "password": "Secret123!"},
    ).json()["access_token"]
    response = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_overview_and_delete(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    member = _register("jane@example.com")
    record_llm_usage(provider="gemini", total_tokens=80, user_id=int(member["id"]))
    client = _client()
    token = client.post(
        "/api/admin/login",
        json={"email": "boss@example.com", "password": "AdminPass123!"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    overview = client.get("/api/admin/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["kpis"]["users_total"] == 1
    assert body["kpis"]["tokens_total"] == 80
    assert "support" in body
    assert "analysis" in body
    assert "matches_total" in body["kpis"]
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "DowsonBost" in dashboard.text
    deleted = client.delete(f"/api/admin/users/{member['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    remaining = client.get("/api/admin/users", headers=headers).json()
    assert remaining == []
