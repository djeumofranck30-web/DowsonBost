"""Hunter.io — find a recruiter e-mail from a company domain or name.

Used only as a fallback when the listing itself has no apply address.
DowsonBost still sends from its own mailbox; it does not log into job boards.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from config import get_secret

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"

_PRIORITY_LOCAL_PARTS = (
    "recrutement",
    "recruitment",
    "candidature",
    "candidatures",
    "jobs",
    "job",
    "career",
    "careers",
    "rh",
    "hr",
    "talent",
    "talents",
    "emploi",
)

_ATS_OR_BOARD_HOSTS = (
    "indeed.com",
    "indeed.fr",
    "linkedin.com",
    "welcometothejungle.com",
    "hellowork.com",
    "hellowork.fr",
    "glassdoor.com",
    "glassdoor.fr",
    "monster.fr",
    "monster.com",
    "adzuna.fr",
    "adzuna.com",
    "jooble.org",
    "optioncarriere.com",
    "jobteaser.com",
    "talent.com",
    "francetravail.fr",
    "pole-emploi.fr",
    "apec.fr",
    "cadremploi.fr",
    "keljob.com",
    "meteojob.com",
    "simplyhired.com",
    "ziprecruiter.com",
    "google.com",
    "youtube.com",
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "icims.com",
    "workable.com",
    "recruitee.com",
    "teamtailor.com",
    "ashbyhq.com",
    "jobvite.com",
    "breezy.hr",
    "personio.com",
    "personio.de",
    "welcome-to-the-jungle.com",
    "serpapi.com",
    "dowsonbost.streamlit.app",
)

_cache: dict[str, str | None] = {}


def hunter_api_key() -> str:
    return get_secret("HUNTER_API_KEY", "").strip()


def hunter_configured() -> bool:
    return bool(hunter_api_key())


def _host_from_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = (urlparse(raw).hostname or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def is_job_board_or_ats_host(host: str) -> bool:
    name = (host or "").lower().lstrip(".")
    if name.startswith("www."):
        name = name[4:]
    if not name:
        return True
    for excluded in _ATS_OR_BOARD_HOSTS:
        if name == excluded or name.endswith("." + excluded):
            return True
    return False


def infer_company_domain(job: dict[str, Any]) -> str | None:
    """Company website host, never an Indeed/LinkedIn/ATS aggregator host."""
    for field in ("company_url", "website", "company_domain", "company_website"):
        host = _host_from_url(str(job.get(field) or ""))
        if host and not is_job_board_or_ats_host(host):
            return host
    host = _host_from_url(str(job.get("url") or job.get("apply_url") or ""))
    if host and not is_job_board_or_ats_host(host):
        return host
    return None


def _score_hunter_email(entry: dict[str, Any]) -> int:
    value = str(entry.get("value") or "").strip().lower()
    if "@" not in value:
        return -1
    local = value.split("@", 1)[0]
    department = str(entry.get("department") or "").strip().lower()
    position = str(entry.get("position") or "").strip().lower()
    kind = str(entry.get("type") or "").strip().lower()
    try:
        confidence = int(entry.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    hr_dept = department in {"hr", "human resources"} or "recruit" in department
    priority_local = any(
        hint == local or local.startswith(hint) for hint in _PRIORITY_LOCAL_PARTS
    )
    score = confidence
    if priority_local:
        score += 80
    if hr_dept:
        score += 50
    if any(token in position for token in ("recruit", "talent", "rh", "hr ", "human resource")):
        score += 30
    if kind == "generic":
        score += 10
    elif kind == "personal" and not hr_dept and not priority_local:
        return -1
    return score


def pick_recruiter_email(payload: dict[str, Any]) -> str | None:
    """Choose the safest recruiter mailbox from a Hunter domain-search payload."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    emails = data.get("emails") if isinstance(data, dict) else None
    if not isinstance(emails, list):
        return None
    ranked: list[tuple[int, str]] = []
    for item in emails:
        if not isinstance(item, dict):
            continue
        email = str(item.get("value") or "").strip().lower()
        score = _score_hunter_email(item)
        if score < 20 or not email or "@" not in email:
            continue
        ranked.append((score, email))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1]


def _hunter_get(params: dict[str, str]) -> dict[str, Any] | None:
    try:
        response = requests.get(
            HUNTER_DOMAIN_SEARCH_URL,
            params=params,
            timeout=15,
        )
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def find_recruiter_email(
    job: dict[str, Any],
    *,
    api_key: str | None = None,
) -> str | None:
    """Look up a recruiter address on Hunter.io for this listing's company."""
    key = (api_key if api_key is not None else hunter_api_key()).strip()
    if not key:
        return None
    domain = infer_company_domain(job)
    company = str(job.get("company") or "").strip()
    cache_key = domain or company.lower()
    if not cache_key:
        return None
    if cache_key in _cache:
        return _cache[cache_key]

    params: dict[str, str] = {"api_key": key, "limit": "10"}
    if domain:
        params["domain"] = domain
        params["department"] = "hr"
    elif company:
        params["company"] = company
        params["department"] = "hr"
    else:
        _cache[cache_key] = None
        return None

    payload = _hunter_get(params)
    email = pick_recruiter_email(payload or {})
    if not email and domain:
        fallback = dict(params)
        fallback.pop("department", None)
        payload = _hunter_get(fallback)
        email = pick_recruiter_email(payload or {})
    _cache[cache_key] = email
    return email


def clear_hunter_cache() -> None:
    _cache.clear()
