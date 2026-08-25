"""Manual and automatic job application flows."""

from __future__ import annotations

import html
import json
import re
from typing import Any, Callable, TypedDict

from document_generation import generate_adapted_cv, generate_cover_letter
from email_service import (
    email_configured,
    send_application_confirmation_email,
    send_application_email,
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_MAILTO_RE = re.compile(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", re.I)
_OBFUSCATED_EMAIL_RE = re.compile(
    r"([a-zA-Z0-9._%+-]+)\s*(?:\[at\]|\(at\)|@|\s+at\s+)\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\.|\s+dot\s+)\s*([a-zA-Z]{2,})",
    re.I,
)
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
    "contact",
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
    user_notified: bool


def _normalize_job_text(job: dict[str, Any]) -> str:
    chunks = [
        str(job.get("description") or ""),
        str(job.get("url") or ""),
        str(job.get("apply_url") or ""),
        str(job.get("company") or ""),
    ]
    return html.unescape("\n".join(chunks))


def _collect_email_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        email = raw.lower().strip().strip(".;,)")
        local = email.split("@", 1)[0]
        if not email or "@" not in email or email in seen:
            return
        if any(local.startswith(prefix) for prefix in _IGNORE_LOCAL_PARTS):
            return
        seen.add(email)
        candidates.append(email)

    for match in _MAILTO_RE.finditer(text):
        _add(match.group(1))
    for match in _OBFUSCATED_EMAIL_RE.finditer(text):
        _add(f"{match.group(1)}@{match.group(2)}.{match.group(3)}")
    for match in _EMAIL_RE.finditer(text):
        _add(match.group(0))

    return candidates


def extract_apply_email(job: dict[str, Any]) -> str | None:
    """Find a recruiter e-mail in the job description, apply URL, or listing URL."""
    candidates = _collect_email_candidates(_normalize_job_text(job))
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


def notify_candidate_application(
    user_profile: dict[str, Any],
    job: dict[str, Any],
    *,
    method: str,
    recruiter_email: str | None = None,
    locale: str = "fr",
) -> bool:
    """E-mail the candidate a confirmation of their application. Never raises."""
    profile = build_application_profile(user_profile)
    user_email = profile.get("email") or ""
    if not user_email:
        return False
    try:
        ok, _detail = send_application_confirmation_email(
            user_email,
            profile.get("full_name") or user_email,
            job,
            method=method,
            recruiter_email=recruiter_email,
            locale=locale,
        )
    except Exception:  # noqa: BLE001 — applying must succeed even if mail fails
        return False
    return ok


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


def _send_user_application_copy(
    profile: dict[str, str],
    job: dict[str, Any],
    letter: str,
    adapted: str,
    profile_text: str,
    job_url: str,
    *,
    locale: str,
) -> bool:
    """E-mail the prepared dossier to the candidate when no recruiter address exists."""
    from i18n import t

    user_email = profile.get("email") or ""
    if not user_email or not email_configured():
        return False
    title = str(job.get("title") or "Offre").strip()
    body = (
        f"{t('job.apply_user_copy_intro', locale=locale, title=title)}\n\n"
        f"{t('job.apply_user_copy_next', locale=locale)}\n"
        f"{job_url or '—'}\n\n"
        f"{profile_text}\n\n"
        f"---\n{letter}\n"
    )
    ok, _detail = send_application_email(
        to_email=user_email,
        subject=t("job.apply_user_copy_subject", locale=locale, title=title),
        body_text=body,
        attachments=[
            ("cv_adapte.txt", adapted, "text/plain; charset=utf-8"),
            ("lettre_motivation.txt", letter, "text/plain; charset=utf-8"),
        ],
    )
    return ok


def _external_prepared_message(
    profile: dict[str, str],
    job: dict[str, Any],
    *,
    apply_email: str | None,
    user_notified: bool,
    locale: str,
) -> str:
    from i18n import t

    parts = [t("job.apply_auto_prepared_success", locale=locale)]
    if apply_email and not email_configured():
        parts.append(
            t("job.apply_auto_external_prepared", locale=locale, email=apply_email)
        )
    elif not apply_email:
        parts.append(t("job.apply_auto_prepared_next", locale=locale))
    if job.get("url"):
        parts.append(t("job.apply_auto_opens_site", locale=locale))
    if user_notified:
        parts.append(
            t("job.apply_auto_prepared_user_email", locale=locale, email=profile.get("email", ""))
        )
    return " ".join(parts)


def job_listing_open_script(url: str) -> str:
    """HTML snippet that opens a job listing in a new browser tab."""
    target = str(url or "").strip()
    if not target:
        return ""
    payload = json.dumps(target).replace("<", "\\u003c").replace(">", "\\u003e")
    return (
        "<!DOCTYPE html><html><body><script>"
        "try {"
        f" (window.top || window.parent || window).open({payload},"
        " '_blank', 'noopener,noreferrer');"
        "} catch (e) {"
        f" window.open({payload}, '_blank', 'noopener,noreferrer');"
        "}"
        "</script></body></html>"
    )


def _empty_result(**overrides: Any) -> ApplicationResult:
    base: ApplicationResult = {
        "success": False,
        "method": "",
        "message": "",
        "cover_letter": "",
        "adapted_cv": "",
        "apply_email": None,
        "job_url": "",
        "profile_text": "",
        "user_notified": False,
    }
    base.update(overrides)
    return base


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
        return _empty_result(
            method="missing_profile",
            message=t("job.apply_auto_missing_email", locale=locale),
            profile_text=profile_text,
            job_url=job_url,
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
        return _empty_result(
            method="generation_error",
            message=t("job.apply_auto_generation_error", locale=locale, error=str(exc)),
            cover_letter=cover_letter_text or "",
            adapted_cv=adapted_cv_text or "",
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
            user_notified = notify_candidate_application(
                profile,
                job,
                method="email",
                recruiter_email=apply_email,
                locale=locale,
            )
            message = t(
                "job.apply_auto_email_sent",
                locale=locale,
                email=apply_email,
            )
            if user_notified:
                message = (
                    f"{message} "
                    f"{t('job.apply_user_confirmation_sent', locale=locale, email=profile.get('email', ''))}"
                )
            return _empty_result(
                success=True,
                method="email",
                message=message,
                cover_letter=letter,
                adapted_cv=adapted,
                apply_email=apply_email,
                job_url=job_url,
                profile_text=profile_text,
                user_notified=user_notified,
            )
        return _empty_result(
            method="email_failed",
            message=t("job.apply_auto_email_failed", locale=locale, error=detail),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=apply_email,
            job_url=job_url,
            profile_text=profile_text,
        )

    user_notified = _send_user_application_copy(
        profile,
        job,
        letter,
        adapted,
        profile_text,
        job_url,
        locale=locale,
    )
    return _empty_result(
        success=True,
        method="external_prepared",
        message=_external_prepared_message(
            profile,
            job,
            apply_email=apply_email,
            user_notified=user_notified,
            locale=locale,
        ),
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=apply_email,
        job_url=job_url,
        profile_text=profile_text,
        user_notified=user_notified,
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
            return _empty_result(
                method="generation_error",
                message=t("job.apply_auto_generation_error", locale=locale, error=str(exc)),
                cover_letter=letter,
                adapted_cv=adapted,
                apply_email=extract_apply_email(job),
                job_url=job_url,
                profile_text=profile_text,
            )

    if not job_url:
        return _empty_result(
            method="missing_url",
            message=t("job.apply_manual_missing_url", locale=locale),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=extract_apply_email(job),
            job_url="",
            profile_text=profile_text,
        )

    return _empty_result(
        success=True,
        method="manual",
        message=t("job.apply_manual_ready", locale=locale),
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=extract_apply_email(job),
        job_url=job_url,
        profile_text=profile_text,
    )
