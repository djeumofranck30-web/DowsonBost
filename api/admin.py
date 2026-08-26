"""Admin REST routes for the DowsonBost dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import current_user
from auth import user_is_admin
from services.admin import admin_delete_user, list_registered_users, platform_overview, public_user_record

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(user: dict[str, Any]) -> dict[str, Any]:
    if not user_is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )
    return user


@router.get("/overview")
def admin_overview(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    payload = platform_overview()
    payload["viewer"] = {
        "id": int(user["id"]),
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or "",
    }
    return payload


@router.get("/users")
def admin_users(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    require_admin(user)
    return [public_user_record(item) for item in list_registered_users()]


@router.delete("/users/{user_id}")
def admin_remove_user(user_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    require_admin(user)
    ok, message = admin_delete_user(int(user["id"]), int(user_id))
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}
