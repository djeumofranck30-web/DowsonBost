"""Hunter.io — find a recruiter e-mail from a company domain or name.

Used only as a fallback when the listing itself has no apply address.
DowsonBost still sends from its own mailbox; it does not log into job boards.
"""

from __future__ import annotations

import re
import threading
from typing import Any
from urllib.parse import urlparse

import requests

from config import get_secret
from priority_employers import (
    career_host_mail_domains,
    generic_hr_local_parts,
    mailbox_domain_for_company,
    match_priority_employer,
)

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
HUNTER_EMAIL_VERIFIER_URL = "https://api.hunter.io/v2/email-verifier"

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
    "contact",
    "hello",
    "info",
    "apply",
    "application",
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

_URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_WTTJ_SLUG_RE = re.compile(
    r"/(?:companies|entreprises)/([^/?#]+)/(?:jobs|offres)",
    re.I,
)
_LINKEDIN_SLUG_RE = re.compile(r"/company/([^/?#]+)", re.I)
_PAREN_RE = re.compile(r"\s*[\(\[][^)\]]+[\)\]]")
_LEGAL_SUFFIX_RE = re.compile(
    r",?\s+(s\.?a\.?s\.?u?|s\.?a\.?r\.?l\.?|e\.?u\.?r\.?l\.?|s\.?e\.?s\.?|"
    r"s\.?a\.?|inc\.?|ltd\.?|llc\.?|gmbh|plc|corp\.?|groupe|group)\.?$",
    re.I,
)
_PLACEHOLDER_COMPANIES = {"", "n/a", "na", "none", "unknown", "confidentiel"}

_CAREER_HOST_PREFIXES = {
    "careers",
    "career",
    "jobs",
    "job",
    "emploi",
    "emplois",
    "recrute",
    "recrutement",
    "rh",
    "talent",
    "talents",
    "apply",
    "application",
    "group",
}

_LEGACY_CAREER_HOST_MAIL_DOMAINS: dict[str, str] = {
    "careers.loreal.com": "loreal.com",
    "jobs.airfrance.com": "airfrance.fr",
    "careers.accor.com": "accor.com",
}

CAREER_HOST_MAIL_DOMAINS: dict[str, str] = {
    **_LEGACY_CAREER_HOST_MAIL_DOMAINS,
    **career_host_mail_domains(),
}

_LEGACY_COMPANY_MAIL_DOMAINS: dict[str, str] = {
    "thales alenia space": "thalesaleniaspace.com",
    "l'oreal": "loreal.com",
    "loreal": "loreal.com",
    "air france": "airfrance.fr",
    "accor": "accor.com",
}

COMPANY_MAIL_DOMAINS: dict[str, str] = dict(_LEGACY_COMPANY_MAIL_DOMAINS)

_cache: dict[str, str | None] = {}
_cache_lock = threading.Lock()


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


def mailbox_domain_from_host(host: str) -> str:
    """Turn a career/ATS host into the company domain Hunter can search."""
    name = (host or "").lower().lstrip(".")
    if name.startswith("www."):
        name = name[4:]
    if not name:
        return ""
    mapped = CAREER_HOST_MAIL_DOMAINS.get(name)
    if mapped:
        return mapped
    if is_job_board_or_ats_host(name):
        return ""
    parts = name.split(".")
    if len(parts) >= 3 and parts[0] in _CAREER_HOST_PREFIXES:
        return ".".join(parts[1:])
    return name


def domain_from_company_name(value: str) -> str:
    priority = mailbox_domain_for_company(value)
    if priority:
        return priority
    key = re.sub(r"\s+", " ", clean_company_name(value).lower()).strip()
    if not key:
        return ""
    folded = (
        key.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ù", "u")
        .replace("ô", "o")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ç", "c")
        .replace("'", "")
        .replace("’", "")
    )
    return COMPANY_MAIL_DOMAINS.get(key) or COMPANY_MAIL_DOMAINS.get(folded) or ""


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


def clean_company_name(value: str) -> str:
    """Strip legal suffixes and location noise so Hunter can resolve the firm."""
    text = str(value or "").strip()
    if text.lower() in _PLACEHOLDER_COMPANIES:
        return ""
    text = _PAREN_RE.sub(" ", text)
    text = re.split(r"\s+[|\u2013\u2014/]\s+", text, maxsplit=1)[0]
    text = re.sub(r"\s+", " ", text).strip(" .,;:-")
    text = _LEGAL_SUFFIX_RE.sub("", text)
    text = text.strip(" .,;:-")
    if text.lower() in _PLACEHOLDER_COMPANIES:
        return ""
    return text


def _path_segments(url: str) -> list[str]:
    try:
        path = urlparse(url if "://" in url else f"https://{url}").path
    except ValueError:
        return []
    return [part for part in path.split("/") if part]


def company_slug_from_job(job: dict[str, Any]) -> str | None:
    """Tenant / company slug from WTTJ, LinkedIn or ATS URLs — not a mailbox domain."""
    for field in ("url", "apply_url", "company_url"):
        raw = str(job.get(field) or "").strip()
        if not raw:
            continue
        host = _host_from_url(raw)
        if "welcometothejungle.com" in host or "welcome-to-the-jungle.com" in host:
            match = _WTTJ_SLUG_RE.search(raw)
            if match:
                return match.group(1).strip().lower()
        if "linkedin.com" in host:
            match = _LINKEDIN_SLUG_RE.search(raw)
            if match:
                return match.group(1).strip().lower()
        parts = _path_segments(raw)
        if not parts:
            continue
        if "greenhouse.io" in host and parts[0] not in {"embed", "jobs"}:
            return parts[0].lower()
        if "lever.co" in host:
            return parts[0].lower()
        if "ashbyhq.com" in host:
            return parts[0].lower()
        if "smartrecruiters.com" in host:
            return parts[0].lower()
        if "workable.com" in host:
            return parts[0].lower()
        if "myworkdayjobs.com" in host:
            sub = host.split(".")[0]
            if sub and not re.fullmatch(r"wd\d+", sub):
                return sub.lower()
        if "personio." in host:
            sub = host.split(".")[0]
            if sub not in {"jobs", "www"}:
                return sub.lower()
            if parts:
                return parts[0].lower()
    return None


def _domains_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _URL_IN_TEXT_RE.finditer(text or ""):
        host = _host_from_url(match.group(0))
        if not host or is_job_board_or_ats_host(host) or host in seen:
            continue
        seen.add(host)
        found.append(host)
    return found


def infer_company_domain(job: dict[str, Any]) -> str | None:
    """Company website host, never an Indeed/LinkedIn/ATS aggregator host."""
    priority = match_priority_employer(job)
    if priority and priority.domain:
        return priority.domain
    for field in ("company_url", "website", "company_domain", "company_website"):
        mapped = mailbox_domain_from_host(_host_from_url(str(job.get(field) or "")))
        if mapped:
            return mapped
    blob = "\n".join(
        str(job.get(field) or "")
        for field in ("description", "apply_url", "url")
    )
    for host in _domains_from_text(blob):
        mapped = mailbox_domain_from_host(host)
        if mapped:
            return mapped
    mapped = mailbox_domain_from_host(
        _host_from_url(str(job.get("url") or job.get("apply_url") or ""))
    )
    if mapped:
        return mapped
    named = domain_from_company_name(str(job.get("company") or ""))
    return named or None


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
        score += 40
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
    generic_fallback: list[tuple[int, str]] = []
    for item in emails:
        if not isinstance(item, dict):
            continue
        email = str(item.get("value") or "").strip().lower()
        if not email or "@" not in email:
            continue
        score = _score_hunter_email(item)
        kind = str(item.get("type") or "").strip().lower()
        if score >= 20:
            ranked.append((score, email))
        elif kind == "generic" and score >= 0:
            generic_fallback.append((score, email))
    pool = ranked or generic_fallback
    if not pool:
        return None
    pool.sort(key=lambda pair: pair[0], reverse=True)
    return pool[0][1]


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


def _hunter_verify(email: str, api_key: str) -> bool:
    """True when Hunter says the mailbox exists (or the domain accepts all)."""
    try:
        response = requests.get(
            HUNTER_EMAIL_VERIFIER_URL,
            params={"email": email, "api_key": api_key},
            timeout=12,
        )
    except requests.RequestException:
        return False
    if response.status_code >= 400:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    data = payload.get("data") if isinstance(payload, dict) else None
    status = ""
    if isinstance(data, dict):
        status = str(data.get("status") or "").strip().lower()
    elif isinstance(payload, dict):
        status = str(payload.get("status") or "").strip().lower()
    return status in {"valid", "accept_all"}


def find_generic_hr_inbox(domain: str, *, api_key: str) -> str | None:
    """Try public HR local-parts on a known company domain, verified via Hunter."""
    host = (domain or "").strip().lower().lstrip("@")
    if not host or "@" in host:
        return None
    cache_key = f"generic:{host}"
    if cache_key in _cache:
        return _cache[cache_key]
    found: str | None = None
    for local in generic_hr_local_parts():
        email = f"{local}@{host}"
        if _hunter_verify(email, api_key):
            found = email
            break
    _cache[cache_key] = found
    return found


def _search_queries(job: dict[str, Any]) -> list[dict[str, str]]:
    """Ordered Hunter lookups: generic inboxes first, then unfiltered, then name."""
    domain = infer_company_domain(job)
    company = clean_company_name(str(job.get("company") or ""))
    slug = company_slug_from_job(job)
    if slug and not company:
        company = slug.replace("-", " ").replace("_", " ").strip()
    extra_domain = domain_from_company_name(company)
    matched = match_priority_employer(job)
    priority_domain = matched.domain if matched else ""
    priority_name = matched.name if matched else ""

    queries: list[dict[str, str]] = []

    def _add(**extra: str) -> None:
        query = {key: value for key, value in extra.items() if value}
        if "domain" not in query and "company" not in query:
            return
        if query in queries:
            return
        queries.append(query)

    for host in (priority_domain, domain, extra_domain):
        if host:
            _add(domain=host, type="generic")
            _add(domain=host)
    if priority_name:
        _add(company=priority_name, type="generic")
        _add(company=priority_name)
    if company:
        _add(company=company, type="generic")
        _add(company=company)
    if slug:
        slug_name = slug.replace("-", " ").replace("_", " ").strip()
        if slug_name and slug_name.lower() != company.lower():
            _add(company=slug_name, type="generic")
            _add(company=slug_name)
    return queries


def find_recruiter_email(
    job: dict[str, Any],
    *,
    api_key: str | None = None,
) -> str | None:
    """Look up a recruiter address on Hunter.io for this listing's company."""
    key = (api_key if api_key is not None else hunter_api_key()).strip()
    if not key:
        return None
    queries = _search_queries(job)
    if not queries:
        matched = match_priority_employer(job)
        if matched and matched.domain:
            queries = [{"domain": matched.domain, "type": "generic"}, {"domain": matched.domain}]
        else:
            return None
    cache_key = "|".join(
        f"{item.get('domain') or item.get('company')}:{item.get('type') or '*'}"
        for item in queries
    )
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

    email: str | None = None
    for extra in queries:
        params = {"api_key": key, "limit": "10", **extra}
        email = pick_recruiter_email(_hunter_get(params) or {})
        if email:
            break
    if not email:
        matched = match_priority_employer(job)
        domain = (matched.domain if matched else "") or infer_company_domain(job) or ""
        if domain:
            email = find_generic_hr_inbox(domain, api_key=key)
    with _cache_lock:
        _cache[cache_key] = email
    return email


def clear_hunter_cache() -> None:
    with _cache_lock:
        _cache.clear()
