"""Manual and automatic job application flows."""

from __future__ import annotations

import re
from typing import Any, Callable, TypedDict

from document_generation import generate_adapted_cv, generate_cover_letter
from email_service import email_configured, send_application_email

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_IGNORE_LOCAL_PARTS = ("noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster")
_PRIORITY_LOCAL_HINTS = (
    "recrutement",
    "recruitment",
    "rh",
    "hr",
    "jobs",
    "job",
    "career",
    "careers",
    "candidature",
    "candidatures",
    "talent",
)


class ApplicationResult(TypedDict):
    success: bool
    method: str
    message: str
    cover_letter: str
    adapted_cv: str
    apply_email: str | None
    job_url: str
    profile_text: str


def extract_apply_email(job: dict[str, Any]) -> str | None:
    """Find a recruiter e-mail in the job description or URL."""
    text = f"{job.get('description', '')}\n{job.get('url', '')}"
    candidates: list[str] = []
    seen: set[str] = set()
    for match in _EMAIL_RE.finditer(text):
        email = match.group(0).lower().strip(".")
        local = email.split("@", 1)[0]
        if email in seen:
            continue
        if any(local.startswith(prefix) for prefix in _IGNORE_LOCAL_PARTS):
            continue
        seen.add(email)
        candidates.append(email)

    if not candidates:
        return None

    for hint in _PRIORITY_LOCAL_HINTS:
        for email in candidates:
            if hint in email:
                return email
    return candidates[0]


def build_application_profile(user_profile: dict[str, Any]) -> dict[str, str]:
    """Normalize profile fields used in applications."""
    city = (
        user_profile.get("home_city")
        or user_profile.get("postal_code")
        or user_profile.get("region")
        or ""
    )
    return {
        "full_name": str(user_profile.get("full_name") or "").strip(),
        "email": str(user_profile.get("email") or "").strip(),
        "phone": str(user_profile.get("phone") or "").strip(),
        "target_job_title": str(user_profile.get("target_job_title") or "").strip(),
        "contract_type": str(user_profile.get("contract_type") or "").strip(),
        "experience_level": str(user_profile.get("experience_level") or "").strip(),
        "location": str(city).strip(),
    }


def format_application_profile_text(profile: dict[str, str]) -> str:
    """Human-readable profile block for copy-paste or e-mail footers."""
    lines = [
        f"Nom : {profile.get('full_name') or '—'}",
        f"E-mail : {profile.get('email') or '—'}",
        f"Téléphone : {profile.get('phone') or '—'}",
        f"Poste visé : {profile.get('target_job_title') or '—'}",
    ]
    if profile.get("location"):
        lines.append(f"Localisation : {profile['location']}")
    if profile.get("contract_type"):
        lines.append(f"Type de contrat : {profile['contract_type']}")
    if profile.get("experience_level"):
        lines.append(f"Expérience : {profile['experience_level']}")
    return "\n".join(lines)


def ensure_application_documents(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
    cover_letter_text: str | None = None,
    adapted_cv_text: str | None = None,
) -> tuple[str, str]:
    """Generate missing cover letter and adapted CV."""
    letter = (cover_letter_text or "").strip()
    adapted = (adapted_cv_text or "").strip()
    if not letter:
        letter = generate_cover_letter(
            cv_text,
            job,
            match,
            user_profile,
            llm_call=llm_call,
        ).strip()
    if not adapted:
        adapted = generate_adapted_cv(
            cv_text,
            job,
            match,
            user_profile,
            llm_call=llm_call,
        ).strip()
    return letter, adapted


def _application_subject(job: dict[str, Any], profile: dict[str, str]) -> str:
    title = str(job.get("title") or "Offre").strip()
    name = profile.get("full_name") or "Candidat"
    company = str(job.get("company") or "").strip()
    if company:
        return f"Candidature — {title} — {company} — {name}"
    return f"Candidature — {title} — {name}"


def submit_application_automatically(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
    cover_letter_text: str | None = None,
    adapted_cv_text: str | None = None,
    locale: str = "fr",
) -> ApplicationResult:
    """
    Automatic application:
    1. Load profile + generate letter/CV if needed
    2. Send by e-mail when a recruiter address is found
    3. Otherwise prepare a complete dossier for the external form
    """
    from i18n import t

    profile = build_application_profile(user_profile)
    job_url = str(job.get("url") or "").strip()
    profile_text = format_application_profile_text(profile)

    if not profile.get("email"):
        return ApplicationResult(
            success=False,
            method="missing_profile",
            message=t("job.apply_auto_missing_email", locale=locale),
            cover_letter="",
            adapted_cv="",
            apply_email=None,
            job_url=job_url,
            profile_text=profile_text,
        )

    try:
        letter, adapted = ensure_application_documents(
            cv_text,
            job,
            match,
            user_profile,
            llm_call=llm_call,
            cover_letter_text=cover_letter_text,
            adapted_cv_text=adapted_cv_text,
        )
    except Exception as exc:
        return ApplicationResult(
            success=False,
            method="generation_error",
            message=t("job.apply_auto_generation_error", locale=locale, error=str(exc)),
            cover_letter=cover_letter_text or "",
            adapted_cv=adapted_cv_text or "",
            apply_email=None,
            job_url=job_url,
            profile_text=profile_text,
        )

    apply_email = extract_apply_email(job)
    if apply_email and email_configured():
        body = (
            f"{letter}\n\n"
            f"---\n"
            f"{profile_text}\n\n"
            f"{t('job.apply_email_footer', locale=locale, url=job_url or '—')}"
        )
        ok, detail = send_application_email(
            to_email=apply_email,
            subject=_application_subject(job, profile),
            body_text=body,
            attachments=[
                ("cv_adapte.txt", adapted, "text/plain; charset=utf-8"),
                ("lettre_motivation.txt", letter, "text/plain; charset=utf-8"),
            ],
            reply_to=profile.get("email") or None,
        )
        if ok:
            return ApplicationResult(
                success=True,
                method="email",
                message=t(
                    "job.apply_auto_email_sent",
                    locale=locale,
                    email=apply_email,
                ),
                cover_letter=letter,
                adapted_cv=adapted,
                apply_email=apply_email,
                job_url=job_url,
                profile_text=profile_text,
            )
        return ApplicationResult(
            success=False,
            method="email_failed",
            message=t("job.apply_auto_email_failed", locale=locale, error=detail),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=apply_email,
            job_url=job_url,
            profile_text=profile_text,
        )

    if apply_email and not email_configured():
        return ApplicationResult(
            success=True,
            method="external_prepared",
            message=t(
                "job.apply_auto_external_prepared",
                locale=locale,
                email=apply_email,
            ),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=apply_email,
            job_url=job_url,
            profile_text=profile_text,
        )

    return ApplicationResult(
        success=True,
        method="external_prepared",
        message=t("job.apply_auto_external_prepared_no_email", locale=locale),
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=None,
        job_url=job_url,
        profile_text=profile_text,
    )


def prepare_manual_application(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
    cover_letter_text: str | None = None,
    adapted_cv_text: str | None = None,
    generate_documents: bool = False,
    locale: str = "fr",
) -> ApplicationResult:
    """Prepare dossier for manual application on the job board."""
    from i18n import t

    profile = build_application_profile(user_profile)
    profile_text = format_application_profile_text(profile)
    job_url = str(job.get("url") or "").strip()
    letter = (cover_letter_text or "").strip()
    adapted = (adapted_cv_text or "").strip()

    if generate_documents and cv_text and user_profile:
        try:
            letter, adapted = ensure_application_documents(
                cv_text,
                job,
                match,
                user_profile,
                llm_call=llm_call,
                cover_letter_text=letter or None,
                adapted_cv_text=adapted or None,
            )
        except Exception as exc:
            return ApplicationResult(
                success=False,
                method="generation_error",
                message=t("job.apply_auto_generation_error", locale=locale, error=str(exc)),
                cover_letter=letter,
                adapted_cv=adapted,
                apply_email=extract_apply_email(job),
                job_url=job_url,
                profile_text=profile_text,
            )

    if not job_url:
        return ApplicationResult(
            success=False,
            method="missing_url",
            message=t("job.apply_manual_missing_url", locale=locale),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=extract_apply_email(job),
            job_url="",
            profile_text=profile_text,
        )

    return ApplicationResult(
        success=True,
        method="manual",
        message=t("job.apply_manual_ready", locale=locale),
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=extract_apply_email(job),
        job_url=job_url,
        profile_text=profile_text,
    )
