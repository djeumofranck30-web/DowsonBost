"""FastAPI REST API for DowsonBost."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

from auth import (
    authenticate_user,
    complete_verified_password_reset,
    delete_user_account,
    init_db,
    register_user,
    request_password_reset_code,
    request_password_reset_email,
    reset_password_with_token,
    user_is_admin,
    verify_password_reset_code,
)
from config import get_database_password, get_database_url
from database import configure_database
from observability import get_logger, setup_logging
from persistence import list_analyses as list_user_analyses
from services.gdpr_export import export_user_data
from api.admin import router as admin_router
from api.candidate import router as candidate_router
from api.deps import current_user
from api.security import create_access_token
from api.serializers import public_analysis_summary, public_user
from api.support import router as support_router
from services.admin import ADMIN_INDEX_PATH

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="DowsonBost API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(support_router)
app.include_router(candidate_router)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any] | None = None


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)
    home_city: str = ""
    postal_code: str = ""
    admin_regions: list[str] | None = None
    selected_departments: list[dict[str, Any]] | None = None
    selected_cities: list[str] | None = None
    all_cities: bool = False
    admin_region: str = ""
    department_code: str = ""
    department_name: str = ""
    country: str = "France"
    contract_type: str = "CDI"
    geo_filter_mode: str = "departement"
    search_radius_km: int = 20
    experience_level: str = "confirme"
    target_sectors: list[str] | None = None
    target_job_title: str = ""
    job_max_age_days: int = 7
    selected_countries: list[str] | None = None
    geo_by_country: dict[str, dict[str, Any]] | None = None
    preferred_language: str = "fr"
    phone: str = ""


class PasswordResetCodeRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2)


class PasswordResetVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class PasswordResetCompleteRequest(BaseModel):
    user_id: int
    new_password: str = Field(min_length=8)


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


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
def admin_dashboard_page() -> FileResponse:
    if not ADMIN_INDEX_PATH.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard introuvable")
    return FileResponse(ADMIN_INDEX_PATH, media_type="text/html")


@app.post("/auth/register", response_model=MessageResponse)
def register(body: RegisterRequest) -> MessageResponse:
    ok, message = register_user(
        body.full_name,
        str(body.email),
        body.password,
        home_city=body.home_city,
        postal_code=body.postal_code,
        admin_regions=body.admin_regions,
        selected_departments=body.selected_departments,
        selected_cities=body.selected_cities,
        all_cities=body.all_cities,
        admin_region=body.admin_region,
        department_code=body.department_code,
        department_name=body.department_name,
        country=body.country,
        contract_type=body.contract_type,
        geo_filter_mode=body.geo_filter_mode,
        search_radius_km=body.search_radius_km,
        experience_level=body.experience_level,
        target_sectors=body.target_sectors,
        target_job_title=body.target_job_title,
        job_max_age_days=body.job_max_age_days,
        selected_countries=body.selected_countries,
        geo_by_country=body.geo_by_country,
        preferred_language=body.preferred_language,
        phone=body.phone,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    ok, message, user = authenticate_user(body.email, body.password)
    if not ok or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
    token = create_access_token(int(user["id"]), user["email"])
    return TokenResponse(access_token=token, user=public_user(user))


@app.post("/auth/password-reset/code", response_model=MessageResponse)
def password_reset_code(body: PasswordResetCodeRequest) -> MessageResponse:
    ok, message, _expires = request_password_reset_code(str(body.email), body.full_name)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


@app.post("/auth/password-reset/verify")
def password_reset_verify(body: PasswordResetVerifyRequest) -> dict[str, Any]:
    ok, message, user_id = verify_password_reset_code(str(body.email), body.code)
    if not ok or not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "user_id": int(user_id)}


@app.post("/auth/password-reset/complete", response_model=MessageResponse)
def password_reset_complete(body: PasswordResetCompleteRequest) -> MessageResponse:
    ok, message = complete_verified_password_reset(int(body.user_id), body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


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


@app.get("/users/me")
def read_current_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    payload = public_user(user)
    payload["is_admin"] = user_is_admin(user)
    return payload


@app.get("/users/me/export")
def export_current_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """RGPD data portability: JSON export of the candidate's own records."""
    return export_user_data(user)


@app.delete("/users/me", response_model=MessageResponse)
def delete_current_user(user: dict[str, Any] = Depends(current_user)) -> MessageResponse:
    ok, message = delete_user_account(int(user["id"]))
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return MessageResponse(message=message)


@app.get("/analyses")
def list_my_analyses(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    return [public_analysis_summary(row) for row in list_user_analyses(int(user["id"]))]
