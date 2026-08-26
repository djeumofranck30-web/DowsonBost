"""Admin REST routes for the DowsonBost dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from api.deps import current_admin
from api.security import create_admin_token
from auth import authenticate_admin
from services.admin import admin_delete_user, list_registered_users, platform_overview, public_user_record

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
