"""Candidate ↔ admin support chat, with multiple private conversations."""

from __future__ import annotations

import html
from typing import Any

from auth import get_user_by_id
from constants import SUPPORT_MESSAGE_MAX_LEN
from persistence import (
    count_admin_unread_support,
    count_unread_support_messages,
    create_support_conversation,
    get_support_conversation,
    insert_support_message,
    list_support_conversations,
    list_support_thread,
    list_user_support_conversations,
    mark_support_thread_read,
)

SENDER_USER = "user"
SENDER_ADMIN = "admin"


def _clean_body(body: str) -> tuple[bool, str]:
    text = (body or "").strip()
    if not text:
        return False, ""
    if len(text) > SUPPORT_MESSAGE_MAX_LEN:
        text = text[:SUPPORT_MESSAGE_MAX_LEN]
    return True, text


def start_user_support_conversation(user_id: int) -> dict[str, Any] | None:
    if not get_user_by_id(int(user_id)):
        return None
    return create_support_conversation(int(user_id), created_by="user")


def start_admin_support_conversation(user_id: int) -> dict[str, Any] | None:
    if not get_user_by_id(int(user_id)):
        return None
    return create_support_conversation(int(user_id), created_by="admin")


def send_user_support_message(
    user_id: int,
    body: str,
    *,
    conversation_id: int | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    ok, text = _clean_body(body)
    if not ok:
        return False, "Message vide.", None
    if not get_user_by_id(int(user_id)):
        return False, "Utilisateur introuvable.", None
    if conversation_id and not get_support_conversation(
        int(conversation_id), user_id=int(user_id)
    ):
        return False, "Conversation introuvable.", None
    message = insert_support_message(
        int(user_id),
        SENDER_USER,
        text,
        conversation_id=int(conversation_id) if conversation_id else None,
    )
    return True, "Message envoyé.", message


def send_admin_support_reply(
    user_id: int,
    body: str,
    *,
    admin_id: int | None = None,
    admin_email: str = "",
    conversation_id: int | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    ok, text = _clean_body(body)
    if not ok:
        return False, "Message vide.", None
    if not get_user_by_id(int(user_id)):
        return False, "Utilisateur introuvable.", None
    if conversation_id and not get_support_conversation(
        int(conversation_id), user_id=int(user_id)
    ):
        return False, "Conversation introuvable.", None
    message = insert_support_message(
        int(user_id),
        SENDER_ADMIN,
        text,
        admin_id=int(admin_id) if admin_id else None,
        admin_email=(admin_email or "").strip(),
        conversation_id=int(conversation_id) if conversation_id else None,
    )
    return True, "Réponse envoyée.", message


def user_support_conversations(user_id: int) -> list[dict[str, Any]]:
    return list_user_support_conversations(int(user_id))


def user_support_thread(
    user_id: int,
    *,
    conversation_id: int | None = None,
) -> list[dict[str, Any]]:
    return list_support_thread(int(user_id), conversation_id=conversation_id)


def admin_support_thread(
    user_id: int,
    *,
    conversation_id: int | None = None,
) -> list[dict[str, Any]]:
    if not get_user_by_id(int(user_id)):
        return []
    return list_support_thread(int(user_id), conversation_id=conversation_id)


def mark_user_support_read(
    user_id: int,
    *,
    conversation_id: int | None = None,
) -> None:
    mark_support_thread_read(
        int(user_id),
        incoming_role=SENDER_ADMIN,
        conversation_id=conversation_id,
    )


def mark_admin_support_read(
    user_id: int,
    *,
    conversation_id: int | None = None,
) -> None:
    mark_support_thread_read(
        int(user_id),
        incoming_role=SENDER_USER,
        conversation_id=conversation_id,
    )


def user_support_unread(user_id: int) -> int:
    return count_unread_support_messages(int(user_id), incoming_role=SENDER_ADMIN)


def admin_support_unread() -> int:
    return count_admin_unread_support()


def admin_support_conversations() -> list[dict[str, Any]]:
    """Inbox rows: real conversations plus candidates who do not have one yet."""
    return list_support_conversations()


def public_support_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(message["id"]),
        "conversation_id": int(message["conversation_id"])
        if message.get("conversation_id") is not None
        else None,
        "user_id": int(message["user_id"]),
        "sender_role": message.get("sender_role") or "",
        "body": message.get("body") or "",
        "created_at": message.get("created_at") or "",
        "read_at": message.get("read_at"),
        "admin_email": message.get("admin_email") or "",
    }


def _format_support_time(value: str | None) -> str:
    if not value:
        return ""
    return str(value)[:16].replace("T", " ")


def render_support_thread_html(
    messages: list[dict[str, Any]],
    *,
    user_label: str,
    admin_label: str,
    empty_text: str,
) -> str:
    if not messages:
        return (
            '<div class="empty-panel">'
            f"<p>{html.escape(empty_text)}</p>"
            "</div>"
        )
    parts = ['<div class="support-thread">']
    for message in messages:
        role = "admin" if message.get("sender_role") == SENDER_ADMIN else "user"
        label = admin_label if role == "admin" else user_label
        when = _format_support_time(str(message.get("created_at") or ""))
        parts.append(
            f'<div class="support-bubble {role}">'
            f'<div class="meta">{html.escape(label)} · {html.escape(when)}</div>'
            f"<p>{html.escape(str(message.get('body') or ''))}</p>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)
