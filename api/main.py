"""FastAPI REST API for DowsonBost."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from auth import (
    authenticate_user,
    get_user_by_id,
    init_db,
    request_password_reset_email,
    reset_password_with_token,
)
from config import get_database_password, get_database_url
from database import configure_database
from observability import get_logger, setup_logging
from persistence import list_analyses
from api.security import create_access_token, decode_access_token

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="DowsonBost API", version="1.0.0")
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str


@app.on_event("startup")
def _startup() -> None:
    configure_database(get_database_url(), password=get_database_password())
    init_db()
    logger.info("API startup complete")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    ok, message, user = authenticate_user(body.email, body.password)
    if not ok or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
    token = create_access_token(int(user["id"]), user["email"])
    return TokenResponse(access_token=token)


@app.post("/auth/password-reset/request", response_model=MessageResponse)
def password_reset_request(body: PasswordResetRequest) -> MessageResponse:
    ok, message = request_password_reset_email(body.email)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


@app.post("/auth/password-reset/confirm", response_model=MessageResponse)
def password_reset_confirm(body: PasswordResetConfirm) -> MessageResponse:
    ok, message = reset_password_with_token(body.token, body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@app.get("/users/me")
def read_current_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "target_job_title": user.get("target_job_title", ""),
        "preferred_language": user.get("preferred_language", "fr"),
    }


@app.get("/analyses")
def list_analyses(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    rows = list_analyses(int(user["id"]))
    return [
        {
            "id": row["id"],
            "created_at": row.get("created_at"),
            "target_job_title": row.get("target_job_title"),
            "jobs_found": row.get("jobs_found"),
            "analysis_depth": row.get("analysis_depth"),
        }
        for row in rows
    ]
