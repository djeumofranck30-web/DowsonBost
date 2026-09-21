"""Manual and automatic job application flows."""

from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypedDict
from urllib.parse import urlparse

import requests

from document_generation import generate_adapted_cv, generate_cover_letter
from email_service import (
    email_configured,
    send_application_confirmation_email,
    send_application_email,
)
from cv_layout import (
    application_document_attachments,
    cv_text_for_candidate,
    prepare_structured_cv,
    public_cv_text,
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
_SKIP_PAGE_HOSTS = (
    "indeed.",
    "linkedin.",
    "facebook.",
    "twitter.",
    "x.com",
    "youtube.",
)
_PAGE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DowsonBost/1.0; +https://dowsonbost.streamlit.app)",
    "Accept": "text/html,application/xhtml+xml",
}
RECRUITER_PREFETCH_MAX_WORKERS = 8
RECRUITER_PREFETCH_PAGE_TIMEOUT_SEC = 4


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
    email_to: str
    email_subject: str
    email_body: str
    email_from: str


def llm_keys_configured() -> bool:
    from config import collect_raw_provider_api_keys

    return any(
        collect_raw_provider_api_keys(name) for name in ("groq", "gemini", "openai")
    )


def auto_apply_readiness() -> dict[str, Any]:
    """What Streamlit secrets are in place for automatic e-mail apply."""
    from services.hunter import hunter_configured

    hunter = hunter_configured()
    mail = email_configured()
    llm = llm_keys_configured()
    missing: list[str] = []
    if not hunter:
        missing.append("HUNTER_API_KEY")
    if not mail:
        missing.append("SMTP Gmail (SMTP_HOST / SMTP_USER / SMTP_PASSWORD) ou BREVO_API_KEY")
    if not llm:
        missing.append("GROQ_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY")
    return {
        "hunter": hunter,
        "email": mail,
        "llm": llm,
        "ready": bool(hunter and mail and llm),
        "missing": missing,
    }


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
        host = email.split("@", 1)[-1] if "@" in email else ""
        if not email or "@" not in email or email in seen:
            return
        if any(local.startswith(prefix) for prefix in _IGNORE_LOCAL_PARTS):
            return
        from services.hunter import is_job_board_or_ats_host

        if is_job_board_or_ats_host(host):
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


def _should_fetch_listing(url: str) -> bool:
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return False
    lowered = raw.lower()
    return not any(skip in lowered for skip in _SKIP_PAGE_HOSTS)


def extract_apply_email_from_pages(
    job: dict[str, Any],
    *,
    timeout: int = 8,
    skip_job_boards: bool = False,
) -> str | None:
    """Fetch the public listing page and look for a mailto / recruiter address."""
    from priority_employers import extra_career_page_urls, is_priority_employer
    from services.hunter import is_job_board_or_ats_host

    priority = is_priority_employer(job)
    urls: list[str] = []
    for field in ("apply_url", "url", "company_url"):
        raw = str(job.get(field) or "").strip()
        if raw and raw not in urls and _should_fetch_listing(raw):
            if skip_job_boards and not priority:
                host = urlparse(raw).netloc.lower()
                if is_job_board_or_ats_host(host):
                    continue
            urls.append(raw)
    if priority:
        for extra in extra_career_page_urls(job):
            if extra not in urls and _should_fetch_listing(extra):
                urls.append(extra)
    limit = 5 if priority else 3
    wait = max(2, int(timeout or 8))
    for url in urls[:limit]:
        try:
            response = requests.get(url, timeout=wait, headers=_PAGE_FETCH_HEADERS)
        except requests.RequestException:
            continue
        if response.status_code >= 400 or not response.text:
            continue
        snippet = html.unescape(response.text[:180_000])
        candidates = _collect_email_candidates(snippet)
        if not candidates:
            continue
        for hint in _PRIORITY_LOCAL_HINTS:
            for email in candidates:
                if hint in email:
                    return email
        return candidates[0]
    return None


def stored_recruiter_email(job: dict[str, Any] | None) -> str | None:
    """Return a recruiter address already attached to the offer, if any."""
    raw = str((job or {}).get("recruiter_email") or "").strip()
    if "@" not in raw:
        return None
    local, _, host = raw.lower().partition("@")
    if not local or "." not in host:
        return None
    if any(local.startswith(prefix) for prefix in _IGNORE_LOCAL_PARTS):
        return None
    return f"{local}@{host}"


def _stamp_recruiter_email(
    job: dict[str, Any],
    email: str | None,
    source: str,
) -> dict[str, Any]:
    """Persist a found recruiter address so Apply can reuse it."""
    cleaned = stored_recruiter_email({"recruiter_email": email or ""}) or ""
    if not cleaned:
        job["recruiter_email_source"] = source or job.get("recruiter_email_source") or ""
        job["recruiter_email_resolved"] = True
        return job
    job["recruiter_email"] = cleaned
    job["recruiter_email_source"] = source
    job["recruiter_email_resolved"] = True
    return job


def recruiter_lookup_key(job: dict[str, Any]) -> str:
    """Group jobs that share one Hunter / company mailbox lookup."""
    from services.hunter import clean_company_name, infer_company_domain

    domain = str(infer_company_domain(job) or "").strip().lower()
    if domain:
        return f"domain:{domain}"
    company = clean_company_name(str(job.get("company") or ""))
    if company:
        return f"company:{company.lower()}"
    url = str(job.get("url") or "").strip().lower()
    return f"url:{url}" if url else f"anon:{id(job)}"


def resolve_apply_email(
    job: dict[str, Any],
    *,
    refresh: bool = False,
    skip_job_boards: bool = False,
    skip_pages: bool = False,
    page_timeout: int = 8,
    hunter_max_queries: int | None = None,
    hunter_timeout: int = 8,
) -> str | None:
    """Listing address first, then the public page, then Hunter.io.

    When analysis already found an address, reuse it. An empty prefetch
    (Indeed/LinkedIn with no public mailbox) must not block a later Hunter lookup.
    """
    from services.hunter import attach_inferred_company_url, find_recruiter_email

    attach_inferred_company_url(job)
    if not refresh:
        stored = stored_recruiter_email(job)
        if stored:
            return stored
    listed = extract_apply_email(job)
    if listed:
        return listed
    if not skip_pages:
        from_page = extract_apply_email_from_pages(
            job,
            timeout=page_timeout,
            skip_job_boards=skip_job_boards,
        )
        if from_page:
            return from_page
    return find_recruiter_email(
        job,
        max_queries=hunter_max_queries,
        timeout=hunter_timeout,
    )


def prefetch_recruiter_emails(
    jobs: list[dict[str, Any]],
    *,
    max_workers: int = RECRUITER_PREFETCH_MAX_WORKERS,
) -> list[dict[str, Any]]:
    """Resolve recruiter addresses during analysis and stamp them on each offer."""
    from services.hunter import attach_inferred_company_url

    stamped = [dict(job or {}) for job in jobs]
    if not stamped:
        return stamped
    for job in stamped:
        attach_inferred_company_url(job)

    remaining: list[int] = []
    for index, job in enumerate(stamped):
        listed = extract_apply_email(job)
        if listed:
            _stamp_recruiter_email(job, listed, "listing")
        else:
            remaining.append(index)

    def _fetch_page(index: int) -> tuple[int, str | None]:
        job = stamped[index]
        try:
            email = extract_apply_email_from_pages(
                job,
                timeout=RECRUITER_PREFETCH_PAGE_TIMEOUT_SEC,
                skip_job_boards=True,
            )
        except Exception:  # noqa: BLE001 — one listing must not fail the analysis
            email = None
        return index, email

    if remaining:
        workers = min(max(1, int(max_workers)), len(remaining))
        page_hits: dict[int, str] = {}
        if workers == 1:
            for index in remaining:
                idx, email = _fetch_page(index)
                if email:
                    page_hits[idx] = email
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_fetch_page, index) for index in remaining]
                for future in as_completed(futures):
                    try:
                        idx, email = future.result()
                    except Exception:  # noqa: BLE001
                        continue
                    if email:
                        page_hits[idx] = email
        still_need: list[int] = []
        for index in remaining:
            email = page_hits.get(index)
            if email:
                _stamp_recruiter_email(stamped[index], email, "page")
            else:
                still_need.append(index)
        remaining = still_need

    groups: dict[str, list[int]] = {}
    for index in remaining:
        groups.setdefault(recruiter_lookup_key(stamped[index]), []).append(index)

    def _fetch_hunter(indices: list[int]) -> tuple[list[int], str | None]:
        from services.hunter import find_recruiter_email

        try:
            email = find_recruiter_email(stamped[indices[0]])
        except Exception:  # noqa: BLE001
            email = None
        return indices, email

    if groups:
        group_items = list(groups.values())
        workers = min(max(1, int(max_workers)), len(group_items))
        if workers == 1:
            hunter_rows = [_fetch_hunter(indices) for indices in group_items]
        else:
            hunter_rows = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(_fetch_hunter, indices) for indices in group_items
                ]
                for future in as_completed(futures):
                    try:
                        hunter_rows.append(future.result())
                    except Exception:  # noqa: BLE001
                        continue
        for indices, email in hunter_rows:
            source = "hunter" if email else "hunter"
            for index in indices:
                _stamp_recruiter_email(stamped[index], email, source)
    return stamped


def prefetch_recruiter_emails_for_results(
    results: list[dict[str, Any]],
    *,
    max_workers: int = RECRUITER_PREFETCH_MAX_WORKERS,
) -> list[dict[str, Any]]:
    """Stamp recruiter e-mails onto analysis result job payloads."""
    jobs = [dict(entry.get("job") or {}) for entry in results]
    stamped = prefetch_recruiter_emails(jobs, max_workers=max_workers)
    prepared: list[dict[str, Any]] = []
    for entry, job in zip(results, stamped, strict=False):
        item = dict(entry)
        item["job"] = job
        prepared.append(item)
    return prepared


def enrich_application_profile(user_profile: dict[str, Any]) -> dict[str, Any]:
    """Fill missing contact fields from the logged-in account when the snapshot omitted them."""
    profile = dict(user_profile or {})
    if str(profile.get("email") or "").strip():
        return profile
    user_id = profile.get("id")
    if not user_id:
        return profile
    try:
        from auth import get_user_by_id

        account = get_user_by_id(int(user_id)) or {}
    except Exception:  # noqa: BLE001
        return profile
    if account.get("email"):
        profile["email"] = account["email"]
    if account.get("full_name") and not str(profile.get("full_name") or "").strip():
        profile["full_name"] = account["full_name"]
    if account.get("phone") and not str(profile.get("phone") or "").strip():
        profile["phone"] = account["phone"]
    return profile


def build_application_profile(user_profile: dict[str, Any]) -> dict[str, str]:
    """Normalize profile fields used in applications."""
    city = (
        user_profile.get("home_city")
        or user_profile.get("postal_code")
        or user_profile.get("region")
        or ""
    )
    full_name = str(user_profile.get("full_name") or "").strip()
    parts = [p for p in full_name.split() if p]
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": str(user_profile.get("email") or "").strip(),
        "phone": str(user_profile.get("phone") or "").strip(),
        "target_job_title": str(user_profile.get("target_job_title") or "").strip(),
        "contract_type": str(user_profile.get("contract_type") or "").strip(),
        "experience_level": str(user_profile.get("experience_level") or "").strip(),
        "location": str(city).strip(),
        "skills_text": str(user_profile.get("skills_text") or "").strip(),
        "portfolio_url": str(user_profile.get("portfolio_url") or "").strip(),
        "daily_rate": str(int(user_profile.get("daily_rate") or 0) or ""),
        "availability": "disponible immédiatement",
        "search_mode": str(user_profile.get("search_mode") or user_profile.get("contract_type") or "").strip(),
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


def format_application_autofill_text(
    profile: dict[str, str],
    *,
    cover_letter: str = "",
    adapted_cv: str = "",
) -> str:
    """Block of candidate fields ready to paste into a job-site form."""
    lines = [
        f"Prénom : {profile.get('first_name') or '—'}",
        f"Nom : {profile.get('last_name') or '—'}",
        f"Nom complet : {profile.get('full_name') or '—'}",
        f"E-mail : {profile.get('email') or '—'}",
        f"Téléphone : {profile.get('phone') or '—'}",
        f"Ville : {profile.get('location') or '—'}",
        f"Poste : {profile.get('target_job_title') or '—'}",
    ]
    if profile.get("skills_text"):
        lines.append(f"Compétences : {profile['skills_text']}")
    if profile.get("portfolio_url"):
        lines.append(f"Portfolio : {profile['portfolio_url']}")
    if profile.get("daily_rate"):
        lines.append(f"TJM : {profile['daily_rate']} € HT / jour")
    if profile.get("availability"):
        lines.append(f"Disponibilité : {profile['availability']}")
    if cover_letter.strip():
        lines.extend(["", "--- Proposition / lettre ---", cover_letter.strip()])
    if adapted_cv.strip():
        structured = prepare_structured_cv(adapted_cv)
        clean = public_cv_text(structured) or cv_text_for_candidate(adapted_cv)
        lines.extend(["", "--- CV adapté ---", clean])
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
    skip_adapted: bool = False,
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
        if skip_adapted:
            adapted = (cv_text or "").strip()
        else:
            adapted = generate_adapted_cv(
                cv_text,
                job,
                match,
                user_profile,
                llm_call=llm_call,
            ).strip()
    return letter, cv_text_for_candidate(adapted)


def _application_subject(job: dict[str, Any], profile: dict[str, str]) -> str:
    title = str(job.get("title") or "Offre").strip()
    name = profile.get("full_name") or "Candidat"
    company = str(job.get("company") or "").strip()
    if company:
        return f"Candidature — {title} — {company} — {name}"
    return f"Candidature — {title} — {name}"


def _application_body(
    job: dict[str, Any],
    profile: dict[str, str],
    job_url: str,
    *,
    locale: str,
) -> str:
    """Short recruiter e-mail: the PDF letter and CV are already attached."""
    from i18n import t

    title = str(job.get("title") or "cette offre").strip()
    company = str(job.get("company") or "").strip()
    name = str(profile.get("full_name") or "Candidat").strip()
    company_bit = f" au sein de {company}" if company else ""
    lines = [
        t("job.apply_email_greeting", locale=locale),
        "",
        t(
            "job.apply_email_intro",
            locale=locale,
            title=title,
            company=company_bit,
        ),
        "",
        t("job.apply_email_attachments", locale=locale),
        "",
        t("job.apply_email_close", locale=locale),
        "",
        t("job.apply_email_signoff", locale=locale),
        name,
    ]
    contact = " · ".join(
        part for part in (profile.get("phone") or "", profile.get("email") or "") if part
    )
    if contact:
        lines.append(contact)
    if job_url:
        lines.extend(["", t("job.apply_email_footer", locale=locale, url=job_url)])
    return "\n".join(lines)


def _send_user_application_copy(
    profile: dict[str, str],
    job: dict[str, Any],
    letter: str,
    adapted: str,
    profile_text: str,
    job_url: str,
    *,
    locale: str,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    original_cv: str = "",
    subject: str | None = None,
    body_text: str | None = None,
    recruiter_email: str | None = None,
) -> tuple[bool, str]:
    """E-mail the candidate a copy of the application that was (or would be) sent."""
    from i18n import t

    user_email = profile.get("email") or ""
    if not user_email or not email_configured():
        return False, t("job.apply_auto_missing_email", locale=locale)
    title = str(job.get("title") or "Offre").strip()
    intro = (
        t("job.apply_mail_copy_sent_intro", locale=locale, email=recruiter_email)
        if recruiter_email
        else t("job.apply_user_copy_intro", locale=locale, title=title)
    )
    next_line = (
        t("job.apply_mail_copy_sent_next", locale=locale)
        if recruiter_email
        else t("job.apply_user_copy_next", locale=locale)
    )
    body = (
        f"{intro}\n\n"
        f"{t('job.apply_email_attachments', locale=locale)}\n\n"
        f"{next_line}\n"
        f"{job_url or '—'}\n"
    )
    copy_subject = t(
        "job.apply_mail_copy_subject",
        locale=locale,
        subject=subject or _application_subject(job, profile),
    )
    return send_application_email(
        to_email=user_email,
        subject=copy_subject,
        body_text=body,
        attachments=application_document_attachments(
            letter,
            adapted,
            job=job,
            match=match,
            user_profile=user_profile or profile,
            original_cv=original_cv,
        ),
        from_email=user_email,
        from_name=profile.get("full_name") or "",
        reply_to=user_email,
        locale=locale,
    )


def _external_prepared_message(
    profile: dict[str, str],
    _job: dict[str, Any],
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
    if user_notified:
        parts.append(
            t("job.apply_auto_prepared_user_email", locale=locale, email=profile.get("email", ""))
        )
    return " ".join(parts)


def job_listing_open_script(url: str, clipboard_text: str = "") -> str:
    """HTML snippet that opens a job listing and copies candidate fields."""
    target = str(url or "").strip()
    if not target:
        return ""
    payload = json.dumps(target).replace("<", "\\u003c").replace(">", "\\u003e")
    clip = json.dumps(clipboard_text or "").replace("<", "\\u003c").replace(">", "\\u003e")
    return (
        "<!DOCTYPE html><html><body><script>"
        f"var _clip = {clip};"
        "if (_clip) {"
        " try { navigator.clipboard.writeText(_clip); } catch (e) {}"
        "}"
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
        "email_to": "",
        "email_subject": "",
        "email_body": "",
        "email_from": "",
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
    Automatic application by e-mail only:
    1. Load profile + generate letter/CV if needed
    2. Find a recruiter address on the listing, then Hunter
    3. Send the application and notify the candidate
    """
    from i18n import t

    user_profile = enrich_application_profile(user_profile)
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

    if not email_configured():
        return _empty_result(
            method="email_not_configured",
            message=t("job.apply_auto_mail_not_configured", locale=locale),
            profile_text=profile_text,
            job_url=job_url,
        )

    apply_email = resolve_apply_email(
        job,
        skip_job_boards=True,
        skip_pages=False,
        page_timeout=5,
        hunter_max_queries=3,
        hunter_timeout=8,
    )
    if apply_email:
        _stamp_recruiter_email(
            job,
            apply_email,
            str(job.get("recruiter_email_source") or "lookup"),
        )
    else:
        _stamp_recruiter_email(job, None, "hunter")

    try:
        letter, adapted = ensure_application_documents(
            cv_text,
            job,
            match,
            user_profile,
            llm_call=llm_call,
            cover_letter_text=cover_letter_text,
            adapted_cv_text=adapted_cv_text,
            skip_adapted=False,
        )
    except Exception as exc:
        return _empty_result(
            method="generation_error",
            message=t("job.apply_auto_generation_error", locale=locale, error=str(exc)),
            cover_letter=cover_letter_text or "",
            adapted_cv=adapted_cv_text or "",
            apply_email=apply_email,
            job_url=job_url,
            profile_text=profile_text,
        )

    subject = _application_subject(job, profile)
    body = _application_body(job, profile, job_url, locale=locale)
    attachments = application_document_attachments(
        letter,
        adapted,
        job=job,
        match=match,
        user_profile=user_profile,
        original_cv=cv_text,
    )
    sender_email = profile.get("email") or ""
    sender_name = profile.get("full_name") or ""

    if apply_email:
        ok, detail = send_application_email(
            to_email=apply_email,
            subject=subject,
            body_text=body,
            attachments=attachments,
            from_email=sender_email,
            from_name=sender_name,
            reply_to=sender_email or None,
            locale=locale,
        )
        user_notified = False
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
                from_email=sender_email,
            )
            if user_notified:
                message = (
                    f"{message} "
                    f"{t('job.apply_user_confirmation_sent', locale=locale, email=sender_email)}"
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
                email_to=apply_email,
                email_subject=subject,
                email_body=body,
                email_from=sender_email,
            )
        return _empty_result(
            method="email_failed",
            message=t("job.apply_auto_email_failed", locale=locale, error=detail),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=apply_email,
            job_url=job_url,
            profile_text=profile_text,
            email_to=apply_email,
            email_subject=subject,
            email_body=body,
            email_from=sender_email,
        )

    from services.hunter import hunter_configured

    missing = (
        t("job.apply_auto_hunter_missing", locale=locale)
        if not hunter_configured()
        else t("job.apply_auto_no_recruiter", locale=locale)
    )
    pack_ok, copy_detail = send_application_email(
        to_email=sender_email,
        subject=subject,
        body_text=body,
        attachments=attachments,
        from_email=sender_email,
        from_name=sender_name,
        reply_to=sender_email or None,
        locale=locale,
    )
    if not pack_ok:
        return _empty_result(
            method="email_failed",
            message=t("job.apply_auto_email_failed", locale=locale, error=copy_detail),
            cover_letter=letter,
            adapted_cv=adapted,
            job_url=job_url,
            profile_text=profile_text,
            email_to=sender_email,
            email_subject=subject,
            email_body=body,
            email_from=sender_email,
        )
    user_notified = notify_candidate_application(
        profile,
        job,
        method="auto_prepared",
        locale=locale,
    )
    message = _external_prepared_message(
        profile,
        job,
        apply_email=None,
        user_notified=user_notified,
        locale=locale,
    )
    if user_notified:
        message = (
            f"{message} "
            f"{t('job.apply_user_confirmation_sent', locale=locale, email=sender_email)}"
        )
    return _empty_result(
        success=True,
        method="prepared",
        message=f"{message} {missing}",
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=None,
        job_url=job_url,
        profile_text=profile_text,
        user_notified=user_notified,
        email_to=sender_email,
        email_subject=subject,
        email_body=body,
        email_from=sender_email,
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

    user_profile = enrich_application_profile(user_profile)
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
                apply_email=resolve_apply_email(job),
                job_url=job_url,
                profile_text=profile_text,
            )

    if not job_url:
        return _empty_result(
            method="missing_url",
            message=t("job.apply_manual_missing_url", locale=locale),
            cover_letter=letter,
            adapted_cv=adapted,
            apply_email=resolve_apply_email(job),
            job_url="",
            profile_text=profile_text,
        )

    return _empty_result(
        success=True,
        method="manual",
        message=t("job.apply_manual_ready", locale=locale),
        cover_letter=letter,
        adapted_cv=adapted,
        apply_email=resolve_apply_email(job),
        job_url=job_url,
        profile_text=profile_text,
    )
