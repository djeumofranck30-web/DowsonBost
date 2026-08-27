"""1:1 candidate ↔ admin support chat isolation."""

from __future__ import annotations

from auth import authenticate_user, register_user
from services.support import (
    admin_support_conversations,
    admin_support_unread,
    mark_admin_support_read,
    mark_user_support_read,
    send_admin_support_reply,
    send_user_support_message,
    user_support_thread,
    user_support_unread,
)


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


def test_empty_support_message_is_rejected(sqlite_db):
    jane = _register("jane@example.com", "Jane Doe")
    ok, message, saved = send_user_support_message(int(jane["id"]), "   ")
    assert not ok
    assert saved is None
    assert "vide" in message.lower()
    assert user_support_thread(int(jane["id"])) == []


def test_support_threads_are_private_per_user(sqlite_db):
    jane = _register("jane@example.com", "Jane Doe")
    ali = _register("ali@example.com", "Ali Martin")
    jane_id = int(jane["id"])
    ali_id = int(ali["id"])

    ok, _, saved = send_user_support_message(jane_id, "Bonjour, j’ai un souci de CV.")
    assert ok and saved is not None
    send_user_support_message(ali_id, "Question d’Ali uniquement.")

    jane_thread = user_support_thread(jane_id)
    ali_thread = user_support_thread(ali_id)
    assert [item["body"] for item in jane_thread] == ["Bonjour, j’ai un souci de CV."]
    assert [item["body"] for item in ali_thread] == ["Question d’Ali uniquement."]
    assert all(int(item["user_id"]) == jane_id for item in jane_thread)
    assert all(int(item["user_id"]) == ali_id for item in ali_thread)

    ok, _, reply = send_admin_support_reply(
        jane_id,
        "Réponse privée pour Jane.",
        admin_email="boss@example.com",
    )
    assert ok and reply is not None
    assert reply["sender_role"] == "admin"

    jane_bodies = [item["body"] for item in user_support_thread(jane_id)]
    ali_bodies = [item["body"] for item in user_support_thread(ali_id)]
    assert "Réponse privée pour Jane." in jane_bodies
    assert "Réponse privée pour Jane." not in ali_bodies
    assert "Question d’Ali uniquement." not in jane_bodies

    conversations = admin_support_conversations()
    emails = [item["email"] for item in conversations]
    assert "jane@example.com" in emails
    assert "ali@example.com" in emails
    jane_conv = next(item for item in conversations if item["email"] == "jane@example.com")
    assert jane_conv["unread"] == 1
    assert admin_support_unread() == 2

    mark_admin_support_read(jane_id)
    assert user_support_unread(jane_id) == 1
    mark_user_support_read(jane_id)
    assert user_support_unread(jane_id) == 0
    assert admin_support_unread() == 1
