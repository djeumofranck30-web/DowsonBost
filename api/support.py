"""Candidate support chat REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import current_user
from services.support import (
    get_support_conversation,
    mark_user_support_read,
    public_support_message,
    send_user_support_message,
    start_user_support_conversation,
    user_support_conversations,
    user_support_thread,
)

router = APIRouter(prefix="/api/support", tags=["support"])


class SupportMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


@router.get("/conversations")
def read_my_support_conversations(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"conversations": user_support_conversations(int(user["id"]))}


@router.post("/conversations")
def create_my_support_conversation(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    created = start_user_support_conversation(int(user["id"]))
    if not created:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de créer la conversation.")
    return {"conversation": created}


@router.get("/messages")
def read_my_support_thread(
    user: dict[str, Any] = Depends(current_user),
    conversation_id: int | None = None,
) -> dict[str, Any]:
    if conversation_id is not None:
        owned = get_support_conversation(int(conversation_id), user_id=int(user["id"]))
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable.")
    mark_user_support_read(int(user["id"]), conversation_id=conversation_id)
    thread = user_support_thread(int(user["id"]), conversation_id=conversation_id)
    return {"messages": [public_support_message(item) for item in thread]}


@router.post("/messages")
def send_my_support_message(
    body: SupportMessageRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ok, message, saved = send_user_support_message(
        int(user["id"]),
        body.body,
        conversation_id=body.conversation_id,
    )
    if not ok or not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "item": public_support_message(saved)}
