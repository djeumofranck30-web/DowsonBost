"""Streamlit data access.

On Streamlit Cloud the UI talks to Postgres in-process (one connection per
click). HTTP to FastAPI is used only when API_BASE_URL points to a separate
backend — a localhost hop in the same process made every click slower.
"""

from __future__ import annotations

from typing import Any

from services.api_client import ApiError, BackendClient
from services.embedded_api import backend_url, using_remote_api

_TOKEN = ""
_BACKEND_READY = False
_CLIENT: BackendClient | None = None


def _session_state() -> Any | None:
    try:
        import streamlit as st

        return st.session_state
    except Exception:  # noqa: BLE001
        return None


def get_access_token() -> str:
    state = _session_state()
    if state is not None and state.get("api_access_token"):
        return str(state.get("api_access_token") or "")
    return _TOKEN


def set_access_token(token: str) -> None:
    global _TOKEN
    _TOKEN = token or ""
    state = _session_state()
    if state is not None:
        state.api_access_token = _TOKEN


def clear_access_token() -> None:
    set_access_token("")
    state = _session_state()
    if state is not None:
        state.pop("api_access_token", None)
        state.pop("_workspace_cache", None)
        state.pop("_workspace_at", None)


def ensure_backend() -> str:
    """Attach a remote FastAPI only when API_BASE_URL is set. No embedded server."""
    global _BACKEND_READY, _CLIENT
    if not using_remote_api():
        _BACKEND_READY = False
        _CLIENT = None
        return ""
    url = backend_url()
    _CLIENT = BackendClient(url, get_access_token())
    _BACKEND_READY = True
    return url


def backend_ready() -> bool:
    return _BACKEND_READY


def backend_uses_http() -> bool:
    return bool(_BACKEND_READY and using_remote_api())


def client() -> BackendClient:
    global _CLIENT
    url = backend_url()
    token = get_access_token()
    if _CLIENT is None or _CLIENT.base_url != url:
        _CLIENT = BackendClient(url, token)
    else:
        _CLIENT.set_token(token)
    return _CLIENT


def _http() -> bool:
    return backend_uses_http()


def _api_message(exc: ApiError, fallback: str) -> str:
    return exc.message or fallback


def authenticate_user(email: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    if not _http():
        from auth import authenticate_user as local

        return local(email, password)
    try:
        payload = client().post("/auth/login", json={"email": email, "password": password})
    except ApiError as exc:
        return False, _api_message(exc, "Connexion impossible"), None
    token = str(payload.get("access_token") or "")
    user = payload.get("user") if isinstance(payload.get("user"), dict) else None
    if not token:
        return False, "Jeton API manquant", None
    set_access_token(token)
    if user is None:
        try:
            user = client().get("/users/me")
        except ApiError as exc:
            return False, _api_message(exc, "Profil introuvable"), None
    return True, "Connexion réussie", user


def register_user(full_name: str, email: str, password: str, **kwargs: Any) -> tuple[bool, str]:
    if not _http():
        from auth import register_user as local

        return local(full_name, email, password, **kwargs)
    body = {"full_name": full_name, "email": email, "password": password}
    body.update(kwargs)
    try:
        payload = client().post("/auth/register", json=body)
    except ApiError as exc:
        return False, _api_message(exc, "Inscription impossible")
    return True, str(payload.get("message") or "Compte créé")


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from auth import get_user_by_id as local

        return local(user_id)
    try:
        user = client().get("/users/me")
    except ApiError:
        return None
    if int(user.get("id") or 0) != int(user_id):
        return user
    return user


def update_user_preferred_language(
    user_id: int, locale: str
) -> tuple[bool, str, dict[str, Any] | None]:
    if not _http() or not get_access_token():
        from auth import update_user_preferred_language as local

        return local(user_id, locale)
    try:
        payload = client().patch(
            "/users/me/language", json={"preferred_language": locale}
        )
    except ApiError as exc:
        return False, _api_message(exc, "Langue non enregistrée"), None
    return True, str(payload.get("message") or "ok"), payload.get("user")


def update_user_profile(user_id: int, *args: Any, **kwargs: Any) -> tuple[bool, str, dict[str, Any] | None]:
    if not _http() or not get_access_token():
        from auth import update_user_profile as local

        return local(user_id, *args, **kwargs)
    names = (
        "full_name",
        "home_city",
        "postal_code",
        "admin_regions",
        "selected_departments",
        "selected_cities",
        "all_cities",
        "country",
        "contract_type",
        "geo_filter_mode",
        "search_radius_km",
        "experience_level",
        "target_sectors",
        "target_job_title",
        "job_max_age_days",
    )
    body = dict(kwargs)
    for index, name in enumerate(names):
        if index < len(args) and name not in body:
            body[name] = args[index]
    try:
        payload = client().patch("/users/me", json=body)
    except ApiError as exc:
        return False, _api_message(exc, "Profil non enregistré"), None
    return True, str(payload.get("message") or "ok"), payload.get("user")


def change_password(user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
    if not _http() or not get_access_token():
        from auth import change_password as local

        return local(user_id, current_password, new_password)
    try:
        payload = client().post(
            "/users/me/password",
            json={"current_password": current_password, "new_password": new_password},
        )
    except ApiError as exc:
        return False, _api_message(exc, "Mot de passe non modifié")
    return True, str(payload.get("message") or "ok")


def delete_user_account(user_id: int) -> tuple[bool, str]:
    if not _http() or not get_access_token():
        from auth import delete_user_account as local

        return local(user_id)
    try:
        payload = client().delete("/users/me")
    except ApiError as exc:
        return False, _api_message(exc, "Suppression impossible")
    clear_access_token()
    return True, str(payload.get("message") or "ok")


def request_password_reset_code(email: str, full_name: str) -> tuple[bool, str, str]:
    if not _http():
        from auth import request_password_reset_code as local

        return local(email, full_name)
    try:
        payload = client().post(
            "/auth/password-reset/code",
            json={"email": email, "full_name": full_name},
        )
    except ApiError as exc:
        return False, _api_message(exc, "Code non envoyé"), ""
    return True, str(payload.get("message") or "ok"), ""


def verify_password_reset_code(email: str, code: str) -> tuple[bool, str, int | None]:
    if not _http():
        from auth import verify_password_reset_code as local

        return local(email, code)
    try:
        payload = client().post(
            "/auth/password-reset/verify",
            json={"email": email, "code": code},
        )
    except ApiError as exc:
        return False, _api_message(exc, "Code invalide"), None
    return True, str(payload.get("message") or "ok"), payload.get("user_id")


def complete_verified_password_reset(user_id: int, new_password: str) -> tuple[bool, str]:
    if not _http():
        from auth import complete_verified_password_reset as local

        return local(user_id, new_password)
    try:
        payload = client().post(
            "/auth/password-reset/complete",
            json={"user_id": int(user_id), "new_password": new_password},
        )
    except ApiError as exc:
        return False, _api_message(exc, "Mot de passe non réinitialisé")
    return True, str(payload.get("message") or "ok")


def fetch_workspace() -> dict[str, Any]:
    if not _http() or not get_access_token():
        return {}
    return client().get("/me/workspace")


def get_notification_settings(user_id: int) -> dict[str, Any]:
    if not _http() or not get_access_token():
        from persistence import get_notification_settings as local

        return local(user_id)
    try:
        return client().get("/me/notifications")
    except ApiError:
        from persistence import get_notification_settings as local

        return local(user_id)


def save_notification_settings(user_id: int, settings: dict[str, Any]) -> None:
    if not _http() or not get_access_token():
        from persistence import save_notification_settings as local

        local(user_id, settings)
        return
    client().put("/me/notifications", json=settings)


def list_analyses(user_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import list_analyses as local

        return local(user_id, limit=limit)
    rows = client().get("/analyses")
    return list(rows) if isinstance(rows, list) else []


def get_analysis(user_id: int, analysis_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import get_analysis as local

        return local(user_id, analysis_id)
    try:
        session = client().get(f"/analyses/{int(analysis_id)}")
    except ApiError:
        return None
    if not isinstance(session, dict):
        return None
    session.setdefault("id", session.get("analysis_id") or analysis_id)
    session.setdefault("created_at", session.get("saved_at"))
    return session


def get_analysis_apply_context(user_id: int, analysis_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import get_analysis_apply_context as local

        return local(user_id, analysis_id)
    try:
        return client().get(f"/analyses/{int(analysis_id)}/apply-context")
    except ApiError:
        return None


def list_dashboard_results(user_id: int, **kwargs: Any) -> list[dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import list_dashboard_results as local

        return local(user_id, **kwargs)
    analysis_id = kwargs.get("analysis_id")
    limit = int(kwargs.get("limit") or 200)
    if not analysis_id:
        return []
    payload = client().get(
        f"/analyses/{int(analysis_id)}/dashboard",
        params={"limit": limit},
    )
    rows = payload.get("results") if isinstance(payload, dict) else payload
    return list(rows or [])


def list_user_applications(user_id: int) -> list[dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import list_user_applications as local

        return local(user_id)
    payload = client().get("/applications")
    return list((payload or {}).get("applications") or [])


def count_user_applications(user_id: int) -> int:
    if not _http() or not get_access_token():
        from persistence import count_user_applications as local

        return local(user_id)
    workspace = fetch_workspace()
    if workspace:
        return int(workspace.get("application_count") or 0)
    return len(list_user_applications(user_id))


def control_center_counts(user_id: int) -> dict[str, int]:
    if not _http() or not get_access_token():
        from persistence import control_center_counts as local

        return local(user_id)
    return client().get("/applications/control-center")


def record_application(
    user_id: int,
    result_id: int,
    channel: str,
    *,
    status: str = "applied",
    notes: str = "",
) -> bool:
    if not _http() or not get_access_token():
        from persistence import record_application as local

        return local(user_id, result_id, channel, status=status, notes=notes)
    try:
        payload = client().post(
            "/applications",
            json={
                "result_id": int(result_id),
                "channel": channel,
                "status": status,
                "notes": notes,
            },
        )
    except ApiError:
        return False
    return bool((payload or {}).get("ok"))


def update_application_status(
    user_id: int,
    result_id: int,
    status: str,
    notes: str = "",
) -> bool:
    if not _http() or not get_access_token():
        from persistence import update_application_status as local

        return local(user_id, result_id, status, notes=notes)
    try:
        payload = client().patch(
            f"/applications/{int(result_id)}",
            json={"status": status, "notes": notes},
        )
    except ApiError:
        return False
    return bool((payload or {}).get("ok"))


def get_analysis_result(user_id: int, result_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import get_analysis_result as local

        return local(user_id, result_id)
    try:
        return client().get(f"/results/{int(result_id)}")
    except ApiError:
        return None


def get_analysis_results_by_ids(user_id: int, result_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import get_analysis_results_by_ids as local

        return local(user_id, result_ids)
    if not result_ids:
        return {}
    payload = client().get("/results", params={"ids": ",".join(str(item) for item in result_ids)})
    raw = payload.get("results") if isinstance(payload, dict) else payload
    if isinstance(raw, dict):
        return {int(key): value for key, value in raw.items()}
    return {}


def save_generated_documents(
    user_id: int,
    result_id: int,
    *,
    cover_letter_text: str = "",
    adapted_cv_text: str = "",
) -> None:
    if not _http() or not get_access_token():
        from persistence import save_generated_documents as local

        local(
            user_id,
            result_id,
            cover_letter_text=cover_letter_text,
            adapted_cv_text=adapted_cv_text,
        )
        return
    client().post(
        f"/results/{int(result_id)}/documents",
        json={"cover_letter_text": cover_letter_text, "adapted_cv_text": adapted_cv_text},
    )


def get_connected_job_account(user_id: int, provider: str) -> dict[str, Any] | None:
    key = (provider or "").strip().lower()
    for row in list_connected_job_accounts(user_id):
        if str(row.get("provider") or "").strip().lower() == key:
            return row
    return None


def log_scheduled_run(user_id: int, *args: Any, **kwargs: Any) -> None:
    if _http():
        return
    from persistence import log_scheduled_run as local

    local(user_id, *args, **kwargs)


def list_connected_job_accounts(user_id: int) -> list[dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import list_connected_job_accounts as local

        return local(user_id)
    payload = client().get("/job-accounts")
    return list((payload or {}).get("accounts") or [])


def connect_job_account(user_id: int, provider: str, account_email: str, **kwargs: Any) -> tuple[bool, str]:
    if not _http() or not get_access_token():
        from persistence import connect_job_account as local

        return local(user_id, provider, account_email, **kwargs)
    body = {
        "provider": provider,
        "account_email": account_email,
        "has_existing_account": bool(kwargs.get("has_existing_account")),
        "profile_url": kwargs.get("profile_url") or "",
    }
    try:
        payload = client().post("/job-accounts", json=body)
    except ApiError as exc:
        return False, _api_message(exc, "Compte non lié")
    return True, str(payload.get("message") or "ok")


def disconnect_job_account(user_id: int, provider: str) -> tuple[bool, str]:
    if not _http() or not get_access_token():
        from persistence import disconnect_job_account as local

        return local(user_id, provider)
    try:
        payload = client().delete(f"/job-accounts/{provider}")
    except ApiError as exc:
        return False, _api_message(exc, "Compte non retiré")
    return True, str(payload.get("message") or "ok")


def get_active_cv_document(user_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import get_active_cv_document as local

        return local(user_id)
    payload = client().get("/me/cv")
    return (payload or {}).get("document")


def applications_csv(user_id: int) -> str:
    if not _http() or not get_access_token():
        from persistence import applications_csv as local

        return local(user_id)
    payload = client().get("/applications/csv")
    return str((payload or {}).get("csv") or "")


def applications_needing_followup(user_id: int, **kwargs: Any) -> list[dict[str, Any]]:
    if not _http() or not get_access_token():
        from persistence import applications_needing_followup as local

        return local(user_id, **kwargs)
    payload = client().get("/applications/followups")
    return list((payload or {}).get("applications") or [])


def already_applied_to_company(
    user_id: int, company: str, *, exclude_result_id: int | None = None
) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import already_applied_to_company as local

        return local(user_id, company, exclude_result_id=exclude_result_id)
    payload = client().post(
        "/applications/duplicates",
        json={"company": company, "exclude_result_id": exclude_result_id},
    )
    return payload.get("company")


def already_applied_to_offer(
    user_id: int,
    job: dict[str, Any] | None,
    *,
    exclude_result_id: int | None = None,
) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from persistence import already_applied_to_offer as local

        return local(user_id, job, exclude_result_id=exclude_result_id)
    payload = client().post(
        "/applications/duplicates",
        json={"job": job or {}, "exclude_result_id": exclude_result_id},
    )
    return payload.get("offer")


def find_recruiter_email(job: dict[str, Any], *, api_key: str | None = None) -> str | None:
    if not _http() or not get_access_token():
        from services.hunter import find_recruiter_email as local

        return local(job, api_key=api_key)
    payload = client().post("/hunter/email", json={"job": job or {}})
    email = str((payload or {}).get("email") or "").strip()
    return email or None


def hunter_configured() -> bool:
    if not _http() or not get_access_token():
        from services.hunter import hunter_configured as local

        return local()
    try:
        workspace = fetch_workspace()
        if workspace:
            return bool(workspace.get("hunter_configured"))
    except ApiError:
        pass
    from services.hunter import hunter_configured as local

    return local()


def user_support_unread(user_id: int) -> int:
    if not _http() or not get_access_token():
        from services.support import user_support_unread as local

        return local(user_id)
    try:
        payload = client().get("/api/support/conversations")
    except ApiError:
        return 0
    total = 0
    for row in (payload or {}).get("conversations") or []:
        total += int(row.get("unread_count") or row.get("unread") or 0)
    return total


def enqueue_analysis_job(
    user_id: int,
    user_profile: dict[str, Any],
    **kwargs: Any,
) -> tuple[int | None, str]:
    if not _http() or not get_access_token():
        from services.analysis_queue import enqueue_analysis_job as local

        return local(user_id, user_profile, **kwargs)
    pdf_bytes = kwargs.get("pdf_bytes")
    try:
        if pdf_bytes:
            payload = client().post(
                "/analysis-jobs/upload",
                data={
                    "job_provider": kwargs.get("job_provider") or "all",
                    "analysis_depth": kwargs.get("analysis_depth") or "standard",
                    "cv_fingerprint": kwargs.get("cv_fingerprint") or "",
                    "extraction_method": kwargs.get("extraction_method") or "native",
                    "trigger_source": kwargs.get("trigger_source") or "ui",
                },
                files={"pdf": ("cv.pdf", pdf_bytes, "application/pdf")},
                timeout=60,
            )
        else:
            payload = client().post(
                "/analysis-jobs",
                json={
                    "job_provider": kwargs.get("job_provider") or "all",
                    "analysis_depth": kwargs.get("analysis_depth") or "standard",
                    "cv_fingerprint": kwargs.get("cv_fingerprint") or "",
                    "cv_text": kwargs.get("cv_text") or "",
                    "extraction_method": kwargs.get("extraction_method") or "native",
                    "trigger_source": kwargs.get("trigger_source") or "ui",
                },
            )
    except ApiError as exc:
        return None, exc.message or "enqueue_failed"
    return payload.get("job_id"), str(payload.get("error") or "")


def get_analysis_job(job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from services.analysis_queue import get_analysis_job as local

        return local(job_id, user_id)
    try:
        payload = client().get(f"/analysis-jobs/{int(job_id)}")
    except ApiError:
        return None
    return (payload or {}).get("job")


def get_latest_analysis_job(user_id: int) -> dict[str, Any] | None:
    if not _http() or not get_access_token():
        from services.analysis_queue import get_latest_analysis_job as local

        return local(user_id)
    try:
        payload = client().get("/analysis-jobs/latest")
    except ApiError:
        return None
    return (payload or {}).get("job")


def logout() -> None:
    clear_access_token()


def uses_separate_database_process() -> bool:
    """True when Streamlit should not open its own Postgres checkout."""
    return backend_uses_http()
