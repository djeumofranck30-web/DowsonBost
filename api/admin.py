"""Admin REST routes for the DowsonBost dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from api.deps import current_admin
from api.security import create_admin_token
from auth import authenticate_admin, get_user_by_id
from services.admin import admin_delete_user, list_registered_users, platform_overview, public_user_record
from services.support import (
    admin_support_conversations,
    admin_support_thread,
    get_support_conversation,
    mark_admin_support_read,
    public_support_message,
    send_admin_support_reply,
    start_admin_support_conversation,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SupportReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/login", response_model=AdminTokenResponse)
def admin_login(body: AdminLoginRequest) -> AdminTokenResponse:
    ok, message, admin = authenticate_admin(body.email, body.password)
    if not ok or not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
    token = create_admin_token(str(admin["email"]), int(admin.get("id") or 0))
    return AdminTokenResponse(access_token=token)


@router.get("/overview")
def admin_overview(user: dict[str, Any] = Depends(current_admin)) -> dict[str, Any]:
    payload = platform_overview()
    payload["viewer"] = {
        "id": int(user.get("id") or 0),
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or "",
    }
    return payload


@router.get("/users")
def admin_users(user: dict[str, Any] = Depends(current_admin)) -> list[dict[str, Any]]:
    return [public_user_record(item) for item in list_registered_users()]


@router.delete("/users/{user_id}")
def admin_remove_user(user_id: int, user: dict[str, Any] = Depends(current_admin)) -> dict[str, str]:
    ok, message = admin_delete_user(user, int(user_id))
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@router.get("/support/conversations")
def admin_support_inbox(user: dict[str, Any] = Depends(current_admin)) -> dict[str, Any]:
    return {"conversations": admin_support_conversations()}


@router.get("/support/conversations/{user_id}")
def admin_support_user_thread(
    user_id: int,
    user: dict[str, Any] = Depends(current_admin),
) -> dict[str, Any]:
    target = get_user_by_id(int(user_id))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    mark_admin_support_read(int(user_id))
    thread = admin_support_thread(int(user_id))
    return {
        "user_id": int(user_id),
        "user": public_user_record(target),
        "messages": [public_support_message(item) for item in thread],
    }


@router.post("/support/conversations/{user_id}")
def admin_support_user_reply(
    user_id: int,
    body: SupportReplyRequest,
    user: dict[str, Any] = Depends(current_admin),
) -> dict[str, Any]:
    ok, message, saved = send_admin_support_reply(
        int(user_id),
        body.body,
        admin_id=int(user.get("id") or 0) or None,
        admin_email=str(user.get("email") or ""),
    )
    if not ok or not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "item": public_support_message(saved)}


@router.post("/support/users/{user_id}/conversations")
def admin_create_support_conversation(
    user_id: int,
    user: dict[str, Any] = Depends(current_admin),
) -> dict[str, Any]:
    created = start_admin_support_conversation(int(user_id))
    if not created:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return {"conversation": created}


@router.get("/support/threads/{conversation_id}")
def admin_support_conversation_thread(
    conversation_id: int,
    user: dict[str, Any] = Depends(current_admin),
) -> dict[str, Any]:
    space = get_support_conversation(int(conversation_id))
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable.")
    target = get_user_by_id(int(space["user_id"]))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    mark_admin_support_read(int(space["user_id"]), conversation_id=int(conversation_id))
    thread = admin_support_thread(int(space["user_id"]), conversation_id=int(conversation_id))
    return {
        "user_id": int(space["user_id"]),
        "conversation_id": int(conversation_id),
        "user": public_user_record(target),
        "messages": [public_support_message(item) for item in thread],
    }


@router.post("/support/threads/{conversation_id}")
def admin_support_conversation_reply(
    conversation_id: int,
    body: SupportReplyRequest,
    user: dict[str, Any] = Depends(current_admin),
) -> dict[str, Any]:
    space = get_support_conversation(int(conversation_id))
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable.")
    ok, message, saved = send_admin_support_reply(
        int(space["user_id"]),
        body.body,
        admin_id=int(user.get("id") or 0) or None,
        admin_email=str(user.get("email") or ""),
        conversation_id=int(conversation_id),
    )
    if not ok or not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "item": public_support_message(saved)}
