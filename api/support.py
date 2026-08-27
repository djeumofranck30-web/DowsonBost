"""Candidate support chat REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import current_user
from services.support import (
    mark_user_support_read,
    public_support_message,
    send_user_support_message,
    user_support_thread,
)

router = APIRouter(prefix="/api/support", tags=["support"])


class SupportMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.get("/messages")
def read_my_support_thread(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    mark_user_support_read(int(user["id"]))
    thread = user_support_thread(int(user["id"]))
    return {"messages": [public_support_message(item) for item in thread]}


@router.post("/messages")
def send_my_support_message(
    body: SupportMessageRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ok, message, saved = send_user_support_message(int(user["id"]), body.body)
    if not ok or not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "item": public_support_message(saved)}
