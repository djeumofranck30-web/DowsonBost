"""Candidate data API — Streamlit talks to these routes instead of the database."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from api.deps import current_user
from api.serializers import (
    public_analysis_job,
    public_analysis_summary,
    public_job_account,
    public_user,
)
from auth import (
    change_password,
    delete_user_account,
    update_user_preferred_language,
    update_user_profile,
)
from persistence import (
    already_applied_to_company,
    already_applied_to_offer,
    analysis_to_session_dict,
    applications_csv,
    applications_needing_followup,
    connect_job_account,
    control_center_counts,
    count_user_applications,
    disconnect_job_account,
    get_active_cv_document,
    get_analysis,
    get_analysis_apply_context,
    get_analysis_result,
    get_analysis_results_by_ids,
    get_notification_settings,
    list_analyses,
    list_connected_job_accounts,
    list_dashboard_results,
    list_user_applications,
    record_application,
    save_generated_documents,
    save_notification_settings,
    update_application_status,
)
from services.analysis_queue import (
    enqueue_analysis_job,
    get_analysis_job,
    get_latest_analysis_job,
)
from services.hunter import find_recruiter_email, hunter_configured
from services.support import user_support_unread

router = APIRouter(tags=["candidate"])


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2)
    home_city: str = ""
    postal_code: str = ""
    admin_regions: list[str] = Field(default_factory=list)
    selected_departments: list[dict[str, Any]] = Field(default_factory=list)
    selected_cities: list[str] = Field(default_factory=list)
    all_cities: bool = False
    country: str = "France"
    contract_type: str = "CDI"
    geo_filter_mode: str = "departement"
    search_radius_km: int = 20
    experience_level: str = "confirme"
    target_sectors: list[str] = Field(default_factory=list)
    target_job_title: str = ""
    job_max_age_days: int = 7
    selected_countries: list[str] | None = None
    geo_by_country: dict[str, dict[str, Any]] | None = None
    phone: str | None = None
    work_mode: str = "tous"
    salary_min: int = 0
    skills_text: str = ""
    diplomas_text: str = ""
    experiences_text: str = ""
    daily_rate: int = 0
    portfolio_url: str = ""


class LanguageUpdateRequest(BaseModel):
    preferred_language: str = Field(min_length=2, max_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class NotificationSettingsRequest(BaseModel):
    email_alerts_enabled: bool = False
    alert_min_score: int = 70
    alert_frequency: str = "after_search"
    auto_search_enabled: bool = False
    auto_search_weekday: str = "monday"
    auto_search_hour: int = 8
    auto_search_provider: str = ""
    auto_search_depth: str = "standard"
    auto_search_daily_limit: int = 10
    followup_emails_enabled: bool = False


class ApplicationRecordRequest(BaseModel):
    result_id: int
    channel: str = "manual"
    status: str = "applied"
    notes: str = ""


class ApplicationStatusRequest(BaseModel):
    status: str
    notes: str = ""


class GeneratedDocumentsRequest(BaseModel):
    cover_letter_text: str = ""
    adapted_cv_text: str = ""


class HunterLookupRequest(BaseModel):
    job: dict[str, Any]


class JobAccountRequest(BaseModel):
    provider: str
    account_email: str = Field(min_length=2)
    has_existing_account: bool = False
    profile_url: str = ""


class EnqueueAnalysisRequest(BaseModel):
    job_provider: str = "all"
    analysis_depth: str = "standard"
    cv_fingerprint: str = ""
    cv_text: str = ""
    extraction_method: str = "native"
    trigger_source: str = "ui"


def _http_error(ok: bool, message: str, *, code: int = status.HTTP_400_BAD_REQUEST) -> None:
    if not ok:
        raise HTTPException(status_code=code, detail=message)


@router.get("/me/workspace")
def read_workspace(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """One round-trip for the Streamlit shell: profile + dashboard counts."""
    user_id = int(user["id"])
    return {
        "profile": public_user(user),
        "analyses": [public_analysis_summary(row) for row in list_analyses(user_id)],
        "notifications": get_notification_settings(user_id),
        "control_center": control_center_counts(user_id),
        "application_count": count_user_applications(user_id),
        "support_unread": user_support_unread(user_id),
        "job_accounts": [public_job_account(row) for row in list_connected_job_accounts(user_id)],
        "hunter_configured": hunter_configured(),
        "latest_job": public_analysis_job(get_latest_analysis_job(user_id)),
    }


@router.patch("/users/me")
def patch_current_user(
    body: ProfileUpdateRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ok, message, updated = update_user_profile(
        int(user["id"]),
        body.full_name,
        body.home_city,
        body.postal_code,
        body.admin_regions,
        body.selected_departments,
        body.selected_cities,
        body.all_cities,
        body.country,
        body.contract_type,
        body.geo_filter_mode,
        body.search_radius_km,
        body.experience_level,
        body.target_sectors,
        body.target_job_title,
        body.job_max_age_days,
        selected_countries=body.selected_countries,
        geo_by_country=body.geo_by_country,
        phone=body.phone,
        work_mode=body.work_mode,
        salary_min=body.salary_min,
        skills_text=body.skills_text,
        diplomas_text=body.diplomas_text,
        experiences_text=body.experiences_text,
        daily_rate=body.daily_rate,
        portfolio_url=body.portfolio_url,
    )
    _http_error(ok, message)
    return {"message": message, "user": public_user(updated or user)}


@router.patch("/users/me/language")
def patch_language(
    body: LanguageUpdateRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ok, message, updated = update_user_preferred_language(
        int(user["id"]), body.preferred_language
    )
    _http_error(ok, message)
    return {"message": message, "user": public_user(updated or user)}


@router.post("/users/me/password")
def post_password(
    body: PasswordChangeRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, str]:
    ok, message = change_password(
        int(user["id"]), body.current_password, body.new_password
    )
    _http_error(ok, message)
    return {"message": message}


@router.get("/me/notifications")
def read_notifications(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return get_notification_settings(int(user["id"]))


@router.put("/me/notifications")
def put_notifications(
    body: NotificationSettingsRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    settings = body.model_dump()
    save_notification_settings(int(user["id"]), settings)
    return get_notification_settings(int(user["id"]))


@router.get("/analyses/{analysis_id}")
def read_analysis(
    analysis_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    stored = get_analysis(int(user["id"]), int(analysis_id))
    if not stored:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyse introuvable")
    return analysis_to_session_dict(stored)


@router.get("/analyses/{analysis_id}/dashboard")
def read_analysis_dashboard(
    analysis_id: int,
    limit: int = 200,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    rows = list_dashboard_results(
        int(user["id"]),
        analysis_id=int(analysis_id),
        limit=max(1, min(int(limit), 400)),
    )
    return {"results": rows}


@router.get("/analyses/{analysis_id}/apply-context")
def read_apply_context(
    analysis_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ctx = get_analysis_apply_context(int(user["id"]), int(analysis_id))
    if not ctx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyse introuvable")
    return ctx


@router.get("/results/{result_id}")
def read_result(
    result_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    row = get_analysis_result(int(user["id"]), int(result_id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre introuvable")
    return row


@router.get("/results")
def read_results(
    ids: str = "",
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    parsed: list[int] = []
    for part in (ids or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed.append(int(part))
        except ValueError:
            continue
    loaded = get_analysis_results_by_ids(int(user["id"]), parsed)
    return {"results": {str(key): value for key, value in loaded.items()}}


@router.post("/results/{result_id}/documents")
def post_result_documents(
    result_id: int,
    body: GeneratedDocumentsRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, str]:
    save_generated_documents(
        int(user["id"]),
        int(result_id),
        cover_letter_text=body.cover_letter_text,
        adapted_cv_text=body.adapted_cv_text,
    )
    return {"message": "ok"}


@router.get("/applications")
def read_applications(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"applications": list_user_applications(int(user["id"]))}


@router.get("/applications/control-center")
def read_control_center(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return control_center_counts(int(user["id"]))


@router.get("/applications/followups")
def read_followups(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"applications": applications_needing_followup(int(user["id"]))}


@router.get("/applications/csv")
def read_applications_csv(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    return {"csv": applications_csv(int(user["id"]))}


class DuplicateCheckRequest(BaseModel):
    company: str = ""
    job: dict[str, Any] = Field(default_factory=dict)
    exclude_result_id: int | None = None


@router.post("/applications/duplicates")
def read_duplicates(
    body: DuplicateCheckRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    user_id = int(user["id"])
    return {
        "company": already_applied_to_company(
            user_id, body.company, exclude_result_id=body.exclude_result_id
        ),
        "offer": already_applied_to_offer(
            user_id, body.job, exclude_result_id=body.exclude_result_id
        ),
    }


@router.post("/applications")
def post_application(
    body: ApplicationRecordRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    saved = record_application(
        int(user["id"]),
        int(body.result_id),
        body.channel,
        status=body.status,
        notes=body.notes,
    )
    if not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enregistrement impossible")
    return {"ok": True}


@router.patch("/applications/{result_id}")
def patch_application(
    result_id: int,
    body: ApplicationStatusRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    saved = update_application_status(
        int(user["id"]),
        int(result_id),
        body.status,
        notes=body.notes,
    )
    if not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mise à jour impossible")
    return {"ok": True}


@router.get("/job-accounts")
def read_job_accounts(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"accounts": [public_job_account(row) for row in list_connected_job_accounts(int(user["id"]))]}


@router.post("/job-accounts")
def post_job_account(
    body: JobAccountRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ok, message = connect_job_account(
        int(user["id"]),
        body.provider,
        str(body.account_email),
        has_existing_account=body.has_existing_account,
        profile_url=body.profile_url,
    )
    _http_error(ok, message)
    return {"message": message}


@router.delete("/job-accounts/{provider}")
def delete_job_account(
    provider: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, str]:
    ok, message = disconnect_job_account(int(user["id"]), provider)
    _http_error(ok, message)
    return {"message": message}


@router.get("/me/cv")
def read_active_cv(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    doc = get_active_cv_document(int(user["id"]))
    return {"document": doc}


@router.post("/hunter/email")
def post_hunter_email(
    body: HunterLookupRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    del user
    email = find_recruiter_email(body.job or {})
    return {"email": email or "", "configured": hunter_configured()}


@router.get("/analysis-jobs/latest")
def read_latest_job(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"job": public_analysis_job(get_latest_analysis_job(int(user["id"])))}


@router.get("/analysis-jobs/{job_id}")
def read_analysis_job(
    job_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    job = get_analysis_job(int(job_id), int(user["id"]))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyse introuvable")
    return {"job": public_analysis_job(job)}


@router.post("/analysis-jobs")
def post_analysis_job(
    body: EnqueueAnalysisRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    job_id, err = enqueue_analysis_job(
        int(user["id"]),
        public_user(user),
        job_provider=body.job_provider,
        analysis_depth=body.analysis_depth,
        cv_fingerprint=body.cv_fingerprint,
        cv_text=body.cv_text,
        extraction_method=body.extraction_method,
        trigger_source=body.trigger_source,
    )
    if err and err != "already":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    return {"job_id": job_id, "error": err}


@router.post("/analysis-jobs/upload")
async def post_analysis_job_upload(
    job_provider: str = Form("all"),
    analysis_depth: str = Form("standard"),
    cv_fingerprint: str = Form(""),
    extraction_method: str = Form("native"),
    trigger_source: str = Form("ui"),
    pdf: UploadFile | None = File(None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    pdf_bytes = await pdf.read() if pdf is not None else None
    job_id, err = enqueue_analysis_job(
        int(user["id"]),
        public_user(user),
        job_provider=job_provider,
        analysis_depth=analysis_depth,
        cv_fingerprint=cv_fingerprint,
        pdf_bytes=pdf_bytes,
        extraction_method=extraction_method,
        trigger_source=trigger_source,
    )
    if err and err != "already":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    return {"job_id": job_id, "error": err}
