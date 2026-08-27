"""REST isolation for candidate and admin support chat."""

from __future__ import annotations

from auth import authenticate_user, register_user


def _register(email: str, name: str) -> dict:
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


def _user_token(client, email: str) -> str:
    return client.post(
        "/auth/login",
        json={"email": email, "password": "Secret123!"},
    ).json()["access_token"]


def test_support_api_requires_auth(sqlite_db):
    client = _client()
    assert client.get("/api/support/messages").status_code == 401
    assert client.post("/api/support/messages", json={"body": "hello"}).status_code == 401


def test_member_cannot_access_admin_support(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    _register("jane@example.com", "Jane Doe")
    client = _client()
    token = _user_token(client, "jane@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/support/conversations", headers=headers).status_code == 403
    assert client.post(
        "/api/admin/support/conversations/1",
        headers=headers,
        json={"body": "intrusion"},
    ).status_code == 403


def test_admin_reply_is_visible_only_to_that_candidate(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    jane = _register("jane@example.com", "Jane Doe")
    ali = _register("ali@example.com", "Ali Martin")
    client = _client()
    jane_headers = {"Authorization": f"Bearer {_user_token(client, 'jane@example.com')}"}
    ali_headers = {"Authorization": f"Bearer {_user_token(client, 'ali@example.com')}"}
    admin_token = client.post(
        "/api/admin/login",
        json={"email": "boss@example.com", "password": "AdminPass123!"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    posted = client.post(
        "/api/support/messages",
        headers=jane_headers,
        json={"body": "Aide pour Jane"},
    )
    assert posted.status_code == 200, posted.text
    client.post("/api/support/messages", headers=ali_headers, json={"body": "Aide pour Ali"})

    jane_inbox = client.get("/api/support/messages", headers=jane_headers).json()["messages"]
    ali_inbox = client.get("/api/support/messages", headers=ali_headers).json()["messages"]
    assert [item["body"] for item in jane_inbox] == ["Aide pour Jane"]
    assert [item["body"] for item in ali_inbox] == ["Aide pour Ali"]

    inbox = client.get("/api/admin/support/conversations", headers=admin_headers)
    assert inbox.status_code == 200, inbox.text
    emails = {item["email"] for item in inbox.json()["conversations"]}
    assert emails == {"jane@example.com", "ali@example.com"}

    reply = client.post(
        f"/api/admin/support/conversations/{jane['id']}",
        headers=admin_headers,
        json={"body": "Réponse uniquement pour Jane"},
    )
    assert reply.status_code == 200, reply.text

    jane_after = client.get("/api/support/messages", headers=jane_headers).json()["messages"]
    ali_after = client.get("/api/support/messages", headers=ali_headers).json()["messages"]
    assert "Réponse uniquement pour Jane" in [item["body"] for item in jane_after]
    assert "Réponse uniquement pour Jane" not in [item["body"] for item in ali_after]
    assert ali["id"] not in [item["user_id"] for item in jane_after]


def test_support_api_new_conversation_is_blank_for_user_and_admin(sqlite_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass123!")
    jane = _register("jane@example.com", "Jane Doe")
    ali = _register("ali@example.com", "Ali Martin")
    client = _client()
    jane_headers = {"Authorization": f"Bearer {_user_token(client, 'jane@example.com')}"}
    ali_headers = {"Authorization": f"Bearer {_user_token(client, 'ali@example.com')}"}
    admin_token = client.post(
        "/api/admin/login",
        json={"email": "boss@example.com", "password": "AdminPass123!"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    first = client.post(
        "/api/support/messages",
        headers=jane_headers,
        json={"body": "Fil initial de Jane"},
    )
    assert first.status_code == 200, first.text
    first_id = int(first.json()["item"]["conversation_id"])

    created = client.post("/api/support/conversations", headers=jane_headers)
    assert created.status_code == 200, created.text
    new_id = int(created.json()["conversation"]["id"])
    assert new_id != first_id
    assert created.json()["conversation"]["has_messages"] is False

    blank = client.get(
        "/api/support/messages",
        headers=jane_headers,
        params={"conversation_id": new_id},
    )
    assert blank.status_code == 200, blank.text
    assert blank.json()["messages"] == []

    posted = client.post(
        "/api/support/messages",
        headers=jane_headers,
        json={"body": "Dans le nouveau fil", "conversation_id": new_id},
    )
    assert posted.status_code == 200, posted.text
    old_thread = client.get(
        "/api/support/messages",
        headers=jane_headers,
        params={"conversation_id": first_id},
    ).json()["messages"]
    new_thread = client.get(
        "/api/support/messages",
        headers=jane_headers,
        params={"conversation_id": new_id},
    ).json()["messages"]
    assert [item["body"] for item in old_thread] == ["Fil initial de Jane"]
    assert [item["body"] for item in new_thread] == ["Dans le nouveau fil"]

    admin_created = client.post(
        f"/api/admin/support/users/{jane['id']}/conversations",
        headers=admin_headers,
    )
    assert admin_created.status_code == 200, admin_created.text
    admin_id = int(admin_created.json()["conversation"]["id"])
    admin_blank = client.get(
        f"/api/admin/support/threads/{admin_id}",
        headers=admin_headers,
    )
    assert admin_blank.status_code == 200, admin_blank.text
    assert admin_blank.json()["messages"] == []
    assert admin_blank.json()["user_id"] == jane["id"]

    reply = client.post(
        f"/api/admin/support/threads/{admin_id}",
        headers=admin_headers,
        json={"body": "Réponse dans le fil vierge"},
    )
    assert reply.status_code == 200, reply.text
    jane_admin_thread = client.get(
        "/api/support/messages",
        headers=jane_headers,
        params={"conversation_id": admin_id},
    ).json()["messages"]
    ali_all = client.get("/api/support/messages", headers=ali_headers).json()["messages"]
    assert [item["body"] for item in jane_admin_thread] == ["Réponse dans le fil vierge"]
    assert "Réponse dans le fil vierge" not in [item["body"] for item in ali_all]
    assert "Fil initial de Jane" not in [item["body"] for item in ali_all]

    stolen = client.get(
        "/api/support/messages",
        headers=ali_headers,
        params={"conversation_id": new_id},
    )
    assert stolen.status_code == 404
