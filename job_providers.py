"""Job search providers: Adzuna, SerpApi, Welcome to the Jungle, Jooble, etc."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Callable
from urllib.parse import urlparse

import requests

JOB_PROVIDER_ADZUNA = "adzuna"
JOB_PROVIDER_SERPAPI = "serpapi"
JOB_PROVIDER_WTTJ = "wttj"
JOB_PROVIDER_JOOBLE = "jooble"
JOB_PROVIDER_OPTIONCARRIERE = "optioncarriere"
JOB_PROVIDER_INDEED = "indeed"
JOB_PROVIDER_LINKEDIN = "linkedin"
JOB_PROVIDER_GLASSDOOR = "glassdoor"
JOB_PROVIDER_JOBTEASER = "jobteaser"
JOB_PROVIDER_HELLOWORK = "hellowork"
JOB_PROVIDER_MONSTER = "monster"
JOB_PROVIDER_TALENT = "talent"
JOB_PROVIDER_CAREER_SITES = "career_sites"
JOB_PROVIDER_ALL = "all"

JOB_PROVIDER_LABELS: dict[str, str] = {
    JOB_PROVIDER_ALL: "Tous les moteurs (fusion)",
    JOB_PROVIDER_ADZUNA: "Adzuna (gratuit, recommandé)",
    JOB_PROVIDER_WTTJ: "Welcome to the Jungle (gratuit)",
    JOB_PROVIDER_CAREER_SITES: "Sites carrière entreprises (Greenhouse, Lever, Workday…)",
    JOB_PROVIDER_JOBTEASER: "JobTeaser — étudiants / alternance (Apify)",
    JOB_PROVIDER_HELLOWORK: "HelloWork — pages entreprises + offres (Apify / SerpApi)",
    JOB_PROVIDER_JOOBLE: "Jooble",
    JOB_PROVIDER_OPTIONCARRIERE: "OptionCarriere / Careerjet",
    JOB_PROVIDER_INDEED: "Indeed — offres & pages entreprises (SerpApi)",
    JOB_PROVIDER_LINKEDIN: "LinkedIn Jobs — offres & entreprises (SerpApi)",
    JOB_PROVIDER_GLASSDOOR: "Glassdoor — entreprises, avis & offres (SerpApi)",
    JOB_PROVIDER_MONSTER: "Monster — entreprises & offres (Apify / SerpApi)",
    JOB_PROVIDER_TALENT: "Talent.com — entreprises & offres (Apify / SerpApi)",
    JOB_PROVIDER_SERPAPI: "Google Jobs / SerpApi (agrégateur)",
}

JOB_PROVIDER_SIDEBAR_ORDER = (
    JOB_PROVIDER_ALL,
    JOB_PROVIDER_ADZUNA,
    JOB_PROVIDER_WTTJ,
    JOB_PROVIDER_CAREER_SITES,
    JOB_PROVIDER_JOBTEASER,
    JOB_PROVIDER_HELLOWORK,
    JOB_PROVIDER_JOOBLE,
    JOB_PROVIDER_OPTIONCARRIERE,
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_LINKEDIN,
    JOB_PROVIDER_GLASSDOOR,
    JOB_PROVIDER_MONSTER,
    JOB_PROVIDER_TALENT,
    JOB_PROVIDER_SERPAPI,
)

CONNECTABLE_JOB_PROVIDERS = (
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_LINKEDIN,
    JOB_PROVIDER_HELLOWORK,
    JOB_PROVIDER_WTTJ,
    JOB_PROVIDER_JOBTEASER,
    JOB_PROVIDER_GLASSDOOR,
    JOB_PROVIDER_MONSTER,
    JOB_PROVIDER_TALENT,
    JOB_PROVIDER_JOOBLE,
    JOB_PROVIDER_OPTIONCARRIERE,
)

JOB_BOARD_SHORT_NAMES: dict[str, str] = {
    JOB_PROVIDER_INDEED: "Indeed",
    JOB_PROVIDER_LINKEDIN: "LinkedIn",
    JOB_PROVIDER_HELLOWORK: "HelloWork",
    JOB_PROVIDER_WTTJ: "Welcome to the Jungle",
    JOB_PROVIDER_JOBTEASER: "JobTeaser",
    JOB_PROVIDER_GLASSDOOR: "Glassdoor",
    JOB_PROVIDER_MONSTER: "Monster",
    JOB_PROVIDER_TALENT: "Talent.com",
    JOB_PROVIDER_JOOBLE: "Jooble",
    JOB_PROVIDER_OPTIONCARRIERE: "OptionCarriere",
}

JOB_BOARD_SIGNUP_URLS: dict[str, str] = {
    JOB_PROVIDER_INDEED: "https://secure.indeed.com/auth",
    JOB_PROVIDER_LINKEDIN: "https://www.linkedin.com/signup",
    JOB_PROVIDER_HELLOWORK: "https://www.hellowork.com/",
    JOB_PROVIDER_WTTJ: "https://www.welcometothejungle.com/",
    JOB_PROVIDER_JOBTEASER: "https://www.jobteaser.com/",
    JOB_PROVIDER_GLASSDOOR: "https://www.glassdoor.com/index.htm",
    JOB_PROVIDER_MONSTER: "https://www.monster.fr/",
    JOB_PROVIDER_TALENT: "https://www.talent.com/",
    JOB_PROVIDER_JOOBLE: "https://jooble.org/",
    JOB_PROVIDER_OPTIONCARRIERE: "https://www.optioncarriere.com/",
}

_SOURCE_TO_PROVIDER: tuple[tuple[str, str], ...] = (
    ("linkedin", JOB_PROVIDER_LINKEDIN),
    ("indeed", JOB_PROVIDER_INDEED),
    ("hellowork", JOB_PROVIDER_HELLOWORK),
    ("hello work", JOB_PROVIDER_HELLOWORK),
    ("welcome to the jungle", JOB_PROVIDER_WTTJ),
    ("wttj", JOB_PROVIDER_WTTJ),
    ("jobteaser", JOB_PROVIDER_JOBTEASER),
    ("glassdoor", JOB_PROVIDER_GLASSDOOR),
    ("monster", JOB_PROVIDER_MONSTER),
    ("talent", JOB_PROVIDER_TALENT),
    ("jooble", JOB_PROVIDER_JOOBLE),
    ("optioncarriere", JOB_PROVIDER_OPTIONCARRIERE),
    ("option carrière", JOB_PROVIDER_OPTIONCARRIERE),
    ("careerjet", JOB_PROVIDER_OPTIONCARRIERE),
    ("adzuna", JOB_PROVIDER_ADZUNA),
)


def job_board_display_name(provider: str) -> str:
    """Short site name for account-linking UI (brand names, not engine labels)."""
    return JOB_BOARD_SHORT_NAMES.get(provider, provider)


def job_board_signup_url(provider: str) -> str | None:
    """Public signup / login page for a job board."""
    return JOB_BOARD_SIGNUP_URLS.get(provider)


def provider_key_from_job_source(source: str) -> str | None:
    """Map a job listing source label to a connectable provider key."""
    raw = (source or "").strip().lower()
    if not raw:
        return None
    if raw in CONNECTABLE_JOB_PROVIDERS:
        return raw
    for needle, key in _SOURCE_TO_PROVIDER:
        if needle in raw and key in CONNECTABLE_JOB_PROVIDERS:
            return key
    return None

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

COUNTRY_LOCALE_CODES: dict[str, str] = {
    "france": "fr_FR",
    "royaume-uni": "en_GB",
    "allemagne": "de_DE",
    "espagne": "es_ES",
    "italie": "it_IT",
    "belgique": "fr_BE",
    "suisse": "fr_CH",
    "canada": "en_CA",
    "etats-unis": "en_US",
}

JOOBLE_API_HOSTS: dict[str, str] = {
    "france": "fr.jooble.org",
    "royaume-uni": "uk.jooble.org",
    "allemagne": "de.jooble.org",
    "espagne": "es.jooble.org",
}

CAREERJET_CONTRACT_MAP: dict[str, str] = {
    "Alternance": "i",
    "Stage": "i",
    "CDI": "p",
    "CDD": "t",
    "Freelance": "c",
}

JOBTEASER_CONTRACT_MAP: dict[str, list[str]] = {
    "Alternance": ["alternating", "apprenticeship", "graduate_program"],
    "Stage": ["internship", "thesis"],
    "CDI": ["cdi"],
    "CDD": ["cdd"],
    "Freelance": ["freelance"],
}

APIFY_JOBTEASER_ACTOR = "shahidirfan~jobteaser-job-scraper"
APIFY_HELLOWORK_ACTOR = "crawlerbros~hellowork-jobs-scraper"
APIFY_MONSTER_ACTOR = "orgupdate~monster-jobs-scraper"
APIFY_TALENT_ACTOR = "crawlerbros~talent-com-jobs-scraper"
APIFY_SYNC_TIMEOUT_SEC = 130

HELLOWORK_CONTRACT_MAP: dict[str, list[str]] = {
    "Alternance": ["Alternance"],
    "Stage": ["Stage"],
    "CDI": ["CDI"],
    "CDD": ["CDD"],
    "Freelance": ["Intérim"],
}

MONSTER_JOB_TYPE_MAP: dict[str, str] = {
    "CDI": "FULLTIME",
    "CDD": "CONTRACTOR",
    "Stage": "INTERN",
    "Alternance": "INTERN",
    "Freelance": "CONTRACTOR",
}

MONSTER_COUNTRY_MAP: dict[str, str] = {
    "france": "france",
    "royaume-uni": "uk",
    "allemagne": "germany",
    "espagne": "spain",
    "italie": "italy",
    "belgique": "belgium",
    "suisse": "switzerland",
    "canada": "canada",
    "etats-unis": "usa",
}

TALENT_COUNTRY_CODES: dict[str, str] = {
    "france": "fr",
    "royaume-uni": "uk",
    "allemagne": "de",
    "espagne": "es",
    "italie": "it",
    "belgique": "be",
    "suisse": "ch",
    "canada": "ca",
    "etats-unis": "www",
}

# Public Algolia credentials embedded in WTTJ front-end (read-only search).
WTTJ_ALGOLIA_APP_ID = "CSEKHVMS53"
WTTJ_ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
WTTJ_JOB_INDEXES = (
    "wk_cms_jobs_production",
    "wttj_jobs_production_fr",
    "wttj_jobs_production_en",
)

WTTJ_CONTRACT_MAP: dict[str, str] = {
    "apprenticeship": "Alternance",
    "internship": "Stage",
    "full_time": "CDI",
    "temporary": "CDD",
    "freelance": "Freelance",
    "part_time": "CDI",
    "vie": "CDD",
    "graduate_program": "Alternance",
}

# Algolia facet values for profile contract filtering (OR within each group).
WTTJ_CONTRACT_FILTERS: dict[str, list[str]] = {
    "Alternance": ["apprenticeship", "graduate_program"],
    "Stage": ["internship"],
    "CDI": ["full_time", "part_time"],
    "CDD": ["temporary", "vie"],
    "Freelance": ["freelance"],
}


def merge_job_lists(job_lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Deduplicate jobs from multiple providers (by URL or title+company)."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for jobs in job_lists:
        for job in jobs:
            url = str(job.get("url", "")).strip()
            key = url.lower() if url else f"{job.get('title', '')}|{job.get('company', '')}".lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(job)
    return merged


def _normalize_country_key(country: str) -> str:
    return country.strip().lower() or "france"


def _locale_for_country(country: str) -> str:
    return COUNTRY_LOCALE_CODES.get(_normalize_country_key(country), "fr_FR")


def _jooble_host_for_country(country: str) -> str:
    return JOOBLE_API_HOSTS.get(_normalize_country_key(country), "fr.jooble.org")


def _standard_job(
    title: str,
    company: str,
    location: str,
    description: str,
    url: str,
    *,
    contract_type: str = "",
    source: str = "",
    published_at: str | int | float = "",
) -> dict[str, Any]:
    job: dict[str, Any] = {
        "title": title or "N/A",
        "company": company or "N/A",
        "location": location or "N/A",
        "description": description or "",
        "url": url or "",
        "contract_type": contract_type,
        "source": source,
    }
    if published_at not in ("", None):
        job["published_at"] = published_at
    return job


def _serpapi_country_gl(country: str) -> str:
    mapping = {
        "france": "fr",
        "royaume-uni": "gb",
        "allemagne": "de",
        "espagne": "es",
        "italie": "it",
        "belgique": "be",
        "suisse": "ch",
        "canada": "ca",
        "etats-unis": "us",
    }
    return mapping.get(_normalize_country_key(country), "fr")


def _wttj_algolia_headers() -> dict[str, str]:
    return {
        "x-algolia-application-id": WTTJ_ALGOLIA_APP_ID,
        "x-algolia-api-key": WTTJ_ALGOLIA_API_KEY,
        "Content-Type": "application/json",
        "Referer": "https://www.welcometothejungle.com/",
        "Origin": "https://www.welcometothejungle.com",
    }


def _wttj_text_field(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value if v)
    return str(value).strip()


def _wttj_location(hit: dict[str, Any]) -> str:
    offices = hit.get("offices") or []
    parts: list[str] = []
    if isinstance(offices, list):
        for office in offices:
            if not isinstance(office, dict):
                continue
            city = str(office.get("city", "")).strip()
            region = str(office.get("state", "") or office.get("region", "")).strip()
            country = str(office.get("country_code", "") or office.get("country", "")).strip()
            chunk = ", ".join(p for p in (city, region, country) if p)
            if chunk:
                parts.append(chunk)
    if parts:
        return " | ".join(parts[:2])
    return str(hit.get("office_string", "") or hit.get("location", "") or "").strip()


def _wttj_job_url(hit: dict[str, Any]) -> str:
    org = hit.get("organization") or {}
    org_slug = org.get("slug", "") if isinstance(org, dict) else ""
    job_slug = hit.get("slug") or hit.get("reference") or ""
    locale = "fr"
    if org_slug and job_slug:
        return f"https://www.welcometothejungle.com/{locale}/companies/{org_slug}/jobs/{job_slug}"
    return str(hit.get("url", "") or hit.get("link", "")).strip()


def _wttj_contract_facet_filters(contract_type: str) -> list[list[str]] | None:
    """Build Algolia OR facet filter for WTTJ contract types."""
    values = WTTJ_CONTRACT_FILTERS.get(contract_type.strip())
    if not values:
        return None
    return [[f"contract_type:{value}" for value in values]]


def _wttj_hit_to_job(hit: dict[str, Any]) -> dict[str, Any]:
    org = hit.get("organization") or {}
    company = org.get("name", "N/A") if isinstance(org, dict) else "N/A"
    description_parts = [
        _wttj_text_field(hit.get("summary")),
        _wttj_text_field(hit.get("profile")),
        _wttj_text_field(hit.get("key_missions")),
    ]
    benefits = hit.get("benefits")
    if isinstance(benefits, list) and benefits:
        description_parts.append(
            "Avantages : " + ", ".join(str(item) for item in benefits[:10] if item)
        )
    sectors = hit.get("sectors")
    if isinstance(sectors, list) and sectors:
        description_parts.append(
            "Secteurs : " + ", ".join(str(item) for item in sectors[:8] if item)
        )
    experience = str(hit.get("experience_level_minimum", "")).strip()
    if experience:
        description_parts.append(f"Expérience minimum : {experience}")
    description = "\n\n".join(part for part in description_parts if part)
    raw_contract = str(hit.get("contract_type", "") or hit.get("contract_type_en", "")).strip().lower()
    published = (
        hit.get("published_at")
        or hit.get("published_at_date")
        or hit.get("created_at")
        or hit.get("updated_at")
        or ""
    )
    return {
        "title": hit.get("name", "N/A"),
        "company": company,
        "location": _wttj_location(hit),
        "description": description,
        "url": _wttj_job_url(hit),
        "contract_type": raw_contract,
        "source": "Welcome to the Jungle",
        "published_at": published,
    }


def search_jobs_wttj(
    query: str,
    contract_type: str = "",
    max_pages: int = 3,
    hits_per_page: int = 30,
) -> list[dict[str, Any]]:
    """Search Welcome to the Jungle via their public Algolia job index."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    facet_filters = _wttj_contract_facet_filters(contract_type)

    for index_name in WTTJ_JOB_INDEXES:
        index_jobs: list[dict[str, Any]] = []
        url = (
            f"https://{WTTJ_ALGOLIA_APP_ID.lower()}-dsn.algolia.net"
            f"/1/indexes/{index_name}/query"
        )
        try:
            for page in range(max_pages):
                payload: dict[str, Any] = {
                    "query": cleaned_query,
                    "hitsPerPage": hits_per_page,
                    "page": page,
                }
                if facet_filters:
                    payload["facetFilters"] = facet_filters
                response = requests.post(
                    url,
                    json=payload,
                    headers=_wttj_algolia_headers(),
                    timeout=25,
                )
                if not response.ok:
                    break
                hits = response.json().get("hits", [])
                if not hits:
                    break
                for hit in hits:
                    job = _wttj_hit_to_job(hit)
                    job_url = job.get("url", "")
                    if job_url and job_url in seen_urls:
                        continue
                    if job_url:
                        seen_urls.add(job_url)
                    index_jobs.append(job)
                if len(hits) < hits_per_page:
                    break
        except (requests.RequestException, ValueError, TypeError):
            continue

        if index_jobs:
            jobs = index_jobs
            break

    return jobs


def test_wttj_connection(query: str = "alternance") -> tuple[bool, str]:
    """Quick connectivity check for Welcome to the Jungle search."""
    try:
        jobs = search_jobs_wttj(query, max_pages=1, hits_per_page=3)
    except Exception as exc:  # noqa: BLE001 — surfaced to UI
        return False, f"Erreur WTTJ : {exc}"
    if jobs:
        return True, f"Connexion OK — {len(jobs)} offre(s) test pour « {query} »."
    return False, "Aucun résultat WTTJ (index ou requête indisponible)."


def search_jobs_jooble(
    query: str,
    location: str,
    country: str,
    api_key: str,
    max_pages: int = 2,
    results_per_page: int = 30,
) -> list[dict[str, Any]]:
    """Search Jooble REST API (free key from fr.jooble.org/api/about)."""
    cleaned_query = query.strip()
    if not cleaned_query or not api_key.strip():
        return []

    host = _jooble_host_for_country(country)
    url = f"https://{host}/api/{api_key.strip()}"
    loc = location.strip() or country.strip() or "France"
    jobs: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        try:
            response = requests.post(
                url,
                json={
                    "keywords": cleaned_query,
                    "location": loc,
                    "page": str(page),
                    "ResultOnPage": results_per_page,
                    "companysearch": False,
                },
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if not response.ok:
                break
            payload = response.json()
            batch = payload.get("jobs") or []
            if not batch:
                break
            for item in batch:
                salary = str(item.get("salary", "")).strip()
                snippet = str(item.get("snippet", "")).strip()
                description = snippet
                if salary:
                    description = f"{description}\n\nSalaire : {salary}".strip()
                jobs.append(
                    _standard_job(
                        str(item.get("title", "")),
                        str(item.get("company", "")),
                        str(item.get("location", "")),
                        description,
                        str(item.get("link", "")),
                        contract_type=str(item.get("type", "")),
                        source="Jooble",
                        published_at=item.get("updated") or item.get("pubDate") or item.get("date", ""),
                    )
                )
            if len(batch) < results_per_page:
                break
        except (requests.RequestException, ValueError, TypeError):
            break
    return jobs


def is_public_routable_ip(ip: str) -> bool:
    """True when IP is a usable public address for Careerjet user_ip."""
    try:
        return ipaddress.ip_address(str(ip).strip()).is_global
    except ValueError:
        return False


def normalize_careerjet_referer(referer: str) -> str:
    """Ensure referer ends with / as required by Careerjet examples."""
    cleaned = str(referer or "").strip()
    if not cleaned:
        return "https://localhost/"
    if not cleaned.endswith("/"):
        cleaned += "/"
    return cleaned


def _fetch_public_ip() -> str:
    """Best-effort public IP (server egress) for Careerjet when client IP unavailable."""
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        if response.ok:
            ip = str(response.json().get("ip", "")).strip()
            if ip:
                return ip
    except (requests.RequestException, ValueError, TypeError):
        pass
    return ""


def resolve_careerjet_user_ip(configured_ip: str = "", client_ip: str = "") -> str:
    """Pick a Careerjet-compatible user_ip (public visitor IP preferred)."""
    for candidate in (client_ip, configured_ip):
        cleaned = str(candidate or "").strip()
        if cleaned and is_public_routable_ip(cleaned):
            return cleaned
    public_ip = _fetch_public_ip()
    if public_ip and is_public_routable_ip(public_ip):
        return public_ip
    return configured_ip.strip() or public_ip or "127.0.0.1"


def _extract_blocked_server_ip(error_message: str) -> str:
    match = re.search(
        r"Unauthorized access from IP\s+([0-9a-fA-F:.]+)",
        error_message or "",
    )
    return match.group(1) if match else ""


def _careerjet_failure_hint(
    error: str,
    *,
    user_ip: str,
    referer: str,
    client_ip_raw: str = "",
    server_ip: str = "",
) -> str:
    blocked_ip = _extract_blocked_server_ip(error) or server_ip
    lines = [
        f"Paramètre **user_ip** envoyé : `{user_ip}`",
        f"Referer : `{referer}`",
    ]
    if client_ip_raw and client_ip_raw != user_ip:
        lines.append(
            f"IP visiteur brute ignorée (réseau privé Streamlit) : `{client_ip_raw}`"
        )
    if blocked_ip:
        lines.append(
            f"IP **serveur** refusée par Careerjet : `{blocked_ip}` "
            "(c'est l'adresse de sortie Streamlit Cloud, pas votre PC)."
        )
    lines.extend(
        [
            "",
            "**À faire sur [optioncarriere.com/partners/api](https://www.optioncarriere.com/partners/api) :**",
            f"1. Autoriser / whitelister l'IP serveur `{blocked_ip or server_ip or '?'}`",
            f"2. Vérifier que le referer enregistré = `{referer}` (URL Streamlit exacte)",
            "3. Dans secrets.toml : `CAREERJET_REFERER = \"https://votre-app.streamlit.app/\"`",
            "",
            "Note : Streamlit Cloud peut changer d'IP — contactez Careerjet si le blocage persiste.",
        ]
    )
    return "\n".join(lines)


def _careerjet_request(
    api_key: str,
    params: dict[str, Any],
    referer: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Call Careerjet v4 and return (payload, error_message)."""
    try:
        response = requests.get(
            "https://search.api.careerjet.net/v4/query",
            params=params,
            auth=(api_key.strip(), ""),
            headers={"Content-Type": "application/json", "Referer": referer.strip()},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f"Réseau Careerjet : {exc}"

    body_preview = (response.text or "")[:240].strip()
    if not response.ok:
        return None, f"HTTP {response.status_code} — {body_preview or 'réponse vide'}"

    try:
        payload = response.json()
    except ValueError:
        return None, f"Réponse JSON invalide — {body_preview}"

    if isinstance(payload, dict) and str(payload.get("type", "")).upper() == "ERROR":
        return None, str(payload.get("error") or payload.get("message") or body_preview)

    return payload, None


def search_jobs_optioncarriere(
    query: str,
    location: str,
    country: str,
    api_key: str,
    user_ip: str = "127.0.0.1",
    referer: str = "https://localhost/",
    contract_type: str = "",
    page_size: int = 30,
    max_pages: int = 2,
) -> list[dict[str, Any]]:
    """Search OptionCarriere via Careerjet v4 API."""
    cleaned_query = query.strip()
    if not cleaned_query or not api_key.strip():
        return []

    jobs: list[dict[str, Any]] = []
    locale_code = _locale_for_country(country)
    careerjet_contract = CAREERJET_CONTRACT_MAP.get(contract_type.strip(), "")
    effective_ip = resolve_careerjet_user_ip(user_ip)
    effective_referer = normalize_careerjet_referer(referer)

    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "locale_code": locale_code,
            "keywords": cleaned_query,
            "location": location.strip(),
            "page": page,
            "page_size": page_size,
            "user_ip": effective_ip,
            "user_agent": DEFAULT_USER_AGENT,
        }
        if careerjet_contract:
            params["contract_type"] = careerjet_contract

        payload, _error = _careerjet_request(api_key, params, effective_referer)
        if payload is None:
            break
        batch = payload.get("jobs") or []
        if not batch:
            break
        for item in batch:
            salary = str(item.get("salary", "")).strip()
            description = str(item.get("description", "")).strip()
            if salary and salary not in description:
                description = f"{description}\n\nSalaire : {salary}".strip()
            jobs.append(
                _standard_job(
                    str(item.get("title", "")),
                    str(item.get("company", "")),
                    str(item.get("locations", "")),
                    description,
                    str(item.get("url", "")),
                    source="OptionCarriere",
                    published_at=item.get("date", ""),
                )
            )
        if page >= int(payload.get("pages") or 1):
            break
    return jobs


def probe_optioncarriere_connection(
    api_key: str,
    *,
    user_ip: str = "",
    referer: str = "https://localhost/",
    client_ip: str = "",
    query: str = "alternance",
) -> tuple[bool, str]:
    """Test Careerjet with explicit diagnostics (IP, referer, HTTP body)."""
    if not api_key.strip():
        return (
            False,
            "CAREERJET_API_KEY manquante — inscrivez-vous sur optioncarriere.com/partners/api",
        )

    effective_ip = resolve_careerjet_user_ip(user_ip, client_ip=client_ip)
    effective_referer = normalize_careerjet_referer(referer)
    server_ip = _fetch_public_ip()
    params = {
        "locale_code": "fr_FR",
        "keywords": query.strip() or "alternance",
        "location": "",
        "page": 1,
        "page_size": 3,
        "user_ip": effective_ip,
        "user_agent": DEFAULT_USER_AGENT,
    }
    payload, error = _careerjet_request(api_key, params, effective_referer)
    if error:
        hint = _careerjet_failure_hint(
            error,
            user_ip=effective_ip,
            referer=effective_referer,
            client_ip_raw=client_ip,
            server_ip=server_ip,
        )
        return False, f"Careerjet : {error}\n\n{hint}"

    batch = (payload or {}).get("jobs") or []
    if batch:
        return True, (
            f"OptionCarriere OK — {len(batch)} offre(s) test pour « {query} » "
            f"(IP `{effective_ip}`)."
        )
    return (
        False,
        "Careerjet a répondu sans offres pour « alternance ». "
        f"Vérifiez la clé et le referer `{effective_referer}`."
    )


def _parse_serpapi_google_jobs(data: dict[str, Any], source_label: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs_results") or []:
        apply_options = item.get("apply_options") or []
        apply_url = apply_options[0].get("link", "") if apply_options else ""
        via = str(item.get("via", "")).strip()
        extensions = item.get("detected_extensions") or {}
        jobs.append(
            _standard_job(
                str(item.get("title", "")),
                str(item.get("company_name", "")),
                str(item.get("location", "")),
                str(item.get("description", "")),
                apply_url or str(item.get("share_link", "")),
                contract_type=str(extensions.get("schedule_type", "")),
                source=f"{source_label} ({via})" if via else source_label,
                published_at=extensions.get("posted_at") or item.get("date", ""),
            )
        )
    return jobs


CAREER_SITE_SOURCE_LABEL = "Site carrière entreprise"

CAREER_ATS_HOSTS: tuple[str, ...] = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "jobs.ashbyhq.com",
    "jobs.smartrecruiters.com",
    "apply.workable.com",
    "jobs.personio.de",
)

ATS_HOST_FRAGMENTS: tuple[str, ...] = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "workable.com",
    "personio.",
    "recruitee.com",
    "welcomekit.co",
    "jobvite.com",
    "icims.com",
    "successfactors.com",
    "taleo.net",
    "bamboohr.com",
    "teamtailor.com",
    "join.com",
)

JOB_BOARD_EXCLUSION_HOSTS: tuple[str, ...] = (
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
)

_CAREER_PATH_HINTS = (
    "/job",
    "/jobs/",
    "/emploi",
    "/offre",
    "/career",
    "/carriere",
    "/opening",
    "/position",
    "/vacanc",
    "/recruit",
    "/posting",
    "gh_jid",
    "/j/",
)

_CAREERS_HOME_RE = re.compile(
    r"^/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?(?:careers|carriere[s]?|jobs|emploi[s]?|"
    r"join(?:-us)?|we-are-hiring)(?:/)?$",
    re.I,
)

_JOB_TITLE_SPLIT_RE = re.compile(r"\s+[|\u2013\u2014]\s+")


def _host_from_url(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _host_matches(host: str, needle: str) -> bool:
    needle = needle.lower().lstrip(".")
    return host == needle or host.endswith("." + needle)


def is_job_board_career_url(url: str) -> bool:
    """True when the URL belongs to a public job board rather than a company ATS."""
    host = _host_from_url(url)
    if not host:
        return True
    return any(_host_matches(host, board) for board in JOB_BOARD_EXCLUSION_HOSTS)


def is_company_ats_host(url: str) -> bool:
    host = _host_from_url(url)
    return bool(host) and any(fragment in host for fragment in ATS_HOST_FRAGMENTS)


def company_from_career_url(url: str, fallback: str = "") -> str:
    """Best-effort company name from a Greenhouse / Lever / Workday / … URL."""
    parsed = urlparse(url)
    host = _host_from_url(url)
    parts = [p for p in parsed.path.split("/") if p]

    if "greenhouse.io" in host and parts:
        return parts[0].replace("-", " ").title()
    if "lever.co" in host and parts:
        return parts[0].replace("-", " ").title()
    if "ashbyhq.com" in host and parts:
        return parts[0].replace("-", " ").title()
    if "smartrecruiters.com" in host and parts:
        return parts[0].replace("-", " ").title()
    if "workable.com" in host and parts:
        return parts[0].replace("-", " ").title()
    if "myworkdayjobs.com" in host:
        sub = host.split(".")[0]
        if sub and not re.fullmatch(r"wd\d+", sub):
            return sub.replace("-", " ").title()
    if "personio." in host:
        sub = host.split(".")[0]
        if sub not in {"jobs", "www"}:
            return sub.replace("-", " ").title()
        if parts:
            return parts[0].replace("-", " ").title()

    labels = host.split(".")
    if labels and labels[0] in {"careers", "jobs", "emploi", "career", "recruiting", "apply"}:
        if len(labels) >= 3:
            return labels[1].replace("-", " ").title()
    elif labels and labels[0] not in {"www"}:
        return labels[0].replace("-", " ").title()
    return (fallback or "").strip()


def _clean_career_job_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip())
    text = _JOB_TITLE_SPLIT_RE.split(text, maxsplit=1)[0].strip()
    lowered = text.lower()
    for suffix in (" at ", " chez "):
        idx = lowered.rfind(suffix)
        if idx > 8:
            text = text[:idx].strip()
            break
    return text[:200]


def _is_career_homepage(url: str) -> bool:
    try:
        path = urlparse(url).path or "/"
    except ValueError:
        return False
    return bool(_CAREERS_HOME_RE.match(path))


def _looks_like_job_listing(title: str, url: str, snippet: str) -> bool:
    try:
        path = urlparse(url).path or "/"
    except ValueError:
        return False
    if path in {"", "/"}:
        return False
    if is_company_ats_host(url):
        return not _is_career_homepage(url)
    lowered_url = url.lower()
    if any(hint in lowered_url for hint in _CAREER_PATH_HINTS):
        return not _is_career_homepage(url)
    blob = f"{title} {snippet}".lower()
    return any(token in blob for token in ("cdi", "cdd", "alternance", "stage", "hiring", "recrut"))


def _job_from_google_organic(
    item: dict[str, Any],
    *,
    location: str,
    source_label: str = CAREER_SITE_SOURCE_LABEL,
) -> dict[str, Any] | None:
    url = str(item.get("link") or item.get("url") or "").strip()
    title = _clean_career_job_title(str(item.get("title") or ""))
    snippet = str(item.get("snippet") or item.get("snippet_highlighted_words") or "")
    if isinstance(item.get("snippet_highlighted_words"), list):
        snippet = str(item.get("snippet") or "")
    if not url or not title or not url.startswith("http"):
        return None
    if is_job_board_career_url(url):
        return None
    if not _looks_like_job_listing(title, url, snippet):
        return None
    fallback_company = str(item.get("source") or "").strip()
    company = company_from_career_url(url, fallback_company) or fallback_company or "N/A"
    job_location = location.strip() or "N/A"
    return _standard_job(
        title,
        company,
        job_location,
        snippet,
        url,
        source=source_label,
        published_at=item.get("date") or "",
    )


def _career_site_google_queries(query: str, location: str) -> list[str]:
    q = query.strip()
    geo = f" {location.strip()}" if location.strip() else ""
    ats = " OR ".join(f"site:{host}" for host in CAREER_ATS_HOSTS)
    excluded = " ".join(f"-site:{host}" for host in JOB_BOARD_EXCLUSION_HOSTS[:14])
    return [
        f"{q}{geo} ({ats})",
        f"{q}{geo} (inurl:careers OR inurl:carriere OR inurl:jobs OR inurl:emploi) {excluded}",
    ]


def _search_google_organic(
    query: str,
    country: str,
    api_key: str,
    *,
    num: int = 10,
) -> list[dict[str, Any]]:
    params = {
        "engine": "google",
        "q": query.strip(),
        "api_key": api_key.strip(),
        "hl": "fr",
        "gl": _serpapi_country_gl(country),
        "num": num,
    }
    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("organic_results") or [])


def search_jobs_career_sites(
    query: str,
    location: str,
    country: str,
    api_key: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find openings on company career / ATS pages via Google (SerpApi)."""
    if not api_key.strip() or not query.strip():
        return []

    jobs: list[dict[str, Any]] = []
    last_error: BaseException | None = None
    for google_query in _career_site_google_queries(query, location):
        try:
            organic = _search_google_organic(google_query, country, api_key)
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else 0
            if status in {401, 403}:
                raise
            continue
        except requests.RequestException as exc:
            last_error = exc
            continue
        batch: list[dict[str, Any]] = []
        for item in organic:
            if not isinstance(item, dict):
                continue
            job = _job_from_google_organic(item, location=location)
            if job:
                batch.append(job)
        jobs = merge_job_lists([jobs, batch])
        if len(jobs) >= limit:
            break
    if not jobs and last_error and isinstance(last_error, requests.HTTPError):
        raise last_error
    return jobs[:limit]


def try_search_career_sites(
    query: str,
    location: str,
    country: str,
    api_key: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Career-site search that never fails the surrounding analysis."""
    if not api_key.strip() or not query.strip():
        return []
    try:
        return search_jobs_career_sites(
            query, location, country, api_key, limit=limit
        )
    except (RuntimeError, requests.RequestException, ValueError, TypeError, KeyError):
        return []


def merge_career_site_results(
    result: dict[str, Any],
    *,
    query: str,
    metier: str = "",
    location: str = "",
    country: str = "France",
    provider: str = "",
    api_key: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Append company career-site jobs to an existing search result (once per analysis)."""
    used = [str(p) for p in (result.get("providers_used") or [])]
    if (
        JOB_PROVIDER_CAREER_SITES in used
        or (provider or "").strip().lower() == JOB_PROVIDER_CAREER_SITES
    ):
        return result
    extra = try_search_career_sites(
        (query or metier).strip(),
        location,
        country or "France",
        api_key,
        limit=limit,
    )
    if not extra:
        return result
    merged = dict(result)
    merged["jobs"] = merge_job_lists([list(result.get("jobs") or []), extra])
    merged["providers_used"] = list(dict.fromkeys([*used, JOB_PROVIDER_CAREER_SITES]))
    return merged


def search_jobs_serpapi_google_jobs(
    query: str,
    location: str,
    country: str,
    api_key: str,
    *,
    source_filter: str = "",
) -> list[dict[str, Any]]:
    """Search Google Jobs via SerpApi, optionally filtered by aggregator (LinkedIn, Indeed…)."""
    if not api_key.strip() or not query.strip():
        return []

    serp_location = location.strip() or country.strip() or "France"
    params = {
        "engine": "google_jobs",
        "q": query.strip(),
        "location": serp_location,
        "api_key": api_key.strip(),
        "hl": "fr",
        "gl": _serpapi_country_gl(country),
    }
    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=45,
    )
    response.raise_for_status()
    jobs = _parse_serpapi_google_jobs(response.json(), "Google Jobs (SerpApi)")

    if source_filter:
        needle = source_filter.lower()
        jobs = [
            job
            for job in jobs
            if needle in job.get("source", "").lower()
            or needle in job.get("url", "").lower()
        ]
    return jobs


def search_jobs_indeed_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Search Indeed via SerpApi (engine=indeed), fallback to Google Jobs filter."""
    if not api_key.strip() or not query.strip():
        return []

    serp_location = location.strip() or country.strip() or "France"
    params = {
        "engine": "indeed",
        "q": query.strip(),
        "l": serp_location,
        "api_key": api_key.strip(),
        "hl": "fr",
        "gl": _serpapi_country_gl(country),
    }
    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=45,
        )
        if response.ok:
            data = response.json()
            results = data.get("jobs_results") or data.get("organic_results") or []
            jobs: list[dict[str, Any]] = []
            for item in results:
                jobs.append(
                    _standard_job(
                        str(item.get("title", "")),
                        str(item.get("company_name", "") or item.get("company", "")),
                        str(item.get("location", "")),
                        str(item.get("description", "") or item.get("snippet", "")),
                        str(item.get("link", "") or item.get("share_link", "")),
                        source="Indeed",
                    )
                )
            if jobs:
                return jobs
    except (requests.RequestException, ValueError, TypeError):
        pass

    return search_jobs_serpapi_google_jobs(
        query, location, country, api_key, source_filter="indeed"
    )


def search_jobs_linkedin_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """LinkedIn listings via Google Jobs aggregation (SerpApi)."""
    linkedin_query = f"{query.strip()} linkedin"
    jobs = search_jobs_serpapi_google_jobs(
        linkedin_query, location, country, api_key, source_filter="linkedin"
    )
    if jobs:
        for job in jobs:
            job["source"] = "LinkedIn Jobs"
        return jobs
    return search_jobs_serpapi_google_jobs(
        query, location, country, api_key, source_filter="linkedin"
    )


def search_jobs_glassdoor_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Glassdoor listings via Google Jobs aggregation (SerpApi)."""
    jobs = search_jobs_serpapi_google_jobs(
        query, location, country, api_key, source_filter="glassdoor"
    )
    for job in jobs:
        job["source"] = "Glassdoor"
    return jobs


def _run_apify_actor_sync(
    actor_id: str,
    payload: dict[str, Any],
    apify_token: str,
    *,
    timeout: int = APIFY_SYNC_TIMEOUT_SEC,
) -> list[dict[str, Any]]:
    """Run an Apify actor synchronously and return dataset items."""
    if not apify_token.strip():
        return []
    try:
        response = requests.post(
            f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": apify_token.strip(), "timeout": max(30, timeout - 10)},
            json=payload,
            timeout=timeout,
        )
        if not response.ok:
            return []
        data = response.json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except (requests.RequestException, ValueError, TypeError):
        return []
    return []


def _first_str(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def search_jobs_serpapi_filtered(
    query: str,
    location: str,
    country: str,
    api_key: str,
    *,
    source_filter: str,
    source_label: str,
) -> list[dict[str, Any]]:
    """Search Google Jobs via SerpApi and keep only listings from one platform."""
    jobs = search_jobs_serpapi_google_jobs(
        query,
        location,
        country,
        api_key,
        source_filter=source_filter,
    )
    for job in jobs:
        job["source"] = source_label
    return jobs


def search_jobs_hellowork_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    return search_jobs_serpapi_filtered(
        query, location, country, api_key,
        source_filter="hellowork",
        source_label="HelloWork",
    )


def search_jobs_monster_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    return search_jobs_serpapi_filtered(
        query, location, country, api_key,
        source_filter="monster",
        source_label="Monster",
    )


def search_jobs_talent_serpapi(
    query: str,
    location: str,
    country: str,
    api_key: str,
) -> list[dict[str, Any]]:
    return search_jobs_serpapi_filtered(
        query, location, country, api_key,
        source_filter="talent.com",
        source_label="Talent.com",
    )


def search_jobs_hellowork(
    query: str,
    location: str,
    contract_type: str,
    apify_token: str,
    *,
    serpapi_key: str = "",
    max_results: int = 30,
) -> list[dict[str, Any]]:
    """HelloWork via Apify (prioritaire) ou SerpApi."""
    if apify_token.strip() and query.strip():
        payload: dict[str, Any] = {
            "mode": "search",
            "searchQuery": query.strip(),
            "sortBy": "date",
            "maxItems": max(1, min(max_results, 50)),
        }
        city = location.strip()
        if city:
            payload["city"] = city
        contract_types = HELLOWORK_CONTRACT_MAP.get(contract_type.strip(), [])
        if contract_types:
            payload["contractTypes"] = contract_types
        items = _run_apify_actor_sync(APIFY_HELLOWORK_ACTOR, payload, apify_token)
        jobs = [
            _standard_job(
                _first_str(item, "title"),
                _first_str(item, "company"),
                _first_str(item, "location"),
                _first_str(item, "salary"),
                _first_str(item, "url"),
                contract_type=_first_str(item, "contractType"),
                source="HelloWork",
                published_at=item.get("postedDate") or item.get("postedDateRelative") or "",
            )
            for item in items
            if _first_str(item, "title") or _first_str(item, "url")
        ]
        if jobs:
            return jobs

    if serpapi_key.strip():
        return search_jobs_hellowork_serpapi(query, location, "France", serpapi_key)
    return []


def search_jobs_monster(
    query: str,
    location: str,
    country: str,
    apify_token: str,
    *,
    serpapi_key: str = "",
    contract_type: str = "",
    max_pages: int = 2,
) -> list[dict[str, Any]]:
    """Monster via Apify (prioritaire) ou SerpApi."""
    if apify_token.strip() and query.strip():
        payload: dict[str, Any] = {
            "includeKeyword": query.strip(),
            "locationName": location.strip() or country.strip(),
            "countryName": MONSTER_COUNTRY_MAP.get(_normalize_country_key(country), "france"),
            "pagesToFetch": max(1, min(max_pages, 3)),
            "datePosted": "month",
        }
        job_type = MONSTER_JOB_TYPE_MAP.get(contract_type.strip())
        if job_type:
            payload["jobType"] = job_type
        items = _run_apify_actor_sync(APIFY_MONSTER_ACTOR, payload, apify_token)
        jobs = [
            _standard_job(
                _first_str(item, "job_title", "jobTitle", "title"),
                _first_str(item, "company_name", "companyName", "company"),
                _first_str(item, "location"),
                _first_str(item, "description", "salary"),
                _first_str(item, "URL", "jobUrl", "url"),
                contract_type=_first_str(item, "job_type", "jobType"),
                source="Monster",
                published_at=item.get("date") or item.get("postedDate") or "",
            )
            for item in items
            if _first_str(item, "job_title", "jobTitle", "title") or _first_str(item, "URL", "jobUrl", "url")
        ]
        if jobs:
            return jobs

    if serpapi_key.strip():
        return search_jobs_monster_serpapi(query, location, country, serpapi_key)
    return []


def search_jobs_talent(
    query: str,
    location: str,
    country: str,
    apify_token: str,
    *,
    serpapi_key: str = "",
    max_results: int = 30,
) -> list[dict[str, Any]]:
    """Talent.com via Apify (prioritaire) ou SerpApi."""
    if apify_token.strip() and query.strip():
        payload: dict[str, Any] = {
            "mode": "search",
            "keyword": query.strip(),
            "location": location.strip() or country.strip(),
            "country": TALENT_COUNTRY_CODES.get(_normalize_country_key(country), "fr"),
            "sortBy": "date",
            "maxItems": max(1, min(max_results, 50)),
            "maxPages": 3,
        }
        items = _run_apify_actor_sync(APIFY_TALENT_ACTOR, payload, apify_token)
        jobs = [
            _standard_job(
                _first_str(item, "title"),
                _first_str(item, "company"),
                _first_str(item, "location"),
                _first_str(item, "descriptionSnippet", "description", "salary"),
                _first_str(item, "jobUrl", "url"),
                contract_type=_first_str(item, "employmentType"),
                source="Talent.com",
                published_at=item.get("datePosted") or item.get("postedAgo") or "",
            )
            for item in items
            if _first_str(item, "title") or _first_str(item, "jobUrl", "url")
        ]
        if jobs:
            return jobs

    if serpapi_key.strip():
        return search_jobs_talent_serpapi(query, location, country, serpapi_key)
    return []


def search_jobs_jobteaser(
    query: str,
    location: str,
    contract_type: str,
    apify_token: str,
    max_results: int = 30,
) -> list[dict[str, Any]]:
    """Search JobTeaser via Apify actor (requires APIFY_API_TOKEN)."""
    if not apify_token.strip() or not query.strip():
        return []

    payload: dict[str, Any] = {
        "keyword": query.strip(),
        "location": location.strip(),
        "language": "fr",
        "results_wanted": max(1, min(max_results, 50)),
    }
    contract_types = JOBTEASER_CONTRACT_MAP.get(contract_type.strip(), [])
    if contract_types:
        payload["jobTypes"] = contract_types

    items = _run_apify_actor_sync(APIFY_JOBTEASER_ACTOR, payload, apify_token)
    jobs: list[dict[str, Any]] = []
    for item in items:
        jobs.append(
            _standard_job(
                _first_str(item, "title", "job_title"),
                _first_str(item, "company", "company_name"),
                _first_str(item, "location", "job_location"),
                _first_str(item, "description", "job_description"),
                _first_str(item, "url", "apply_url", "job_url"),
                contract_type=_first_str(item, "contract_type", "contractType"),
                source="JobTeaser",
            )
        )
    return jobs


def test_jooble_connection(api_key: str, query: str = "alternance") -> tuple[bool, str]:
    if not api_key.strip():
        return False, "JOOBLE_API_KEY manquante — inscrivez-vous sur fr.jooble.org/api/about"
    jobs = search_jobs_jooble(query, "", "France", api_key, max_pages=1, results_per_page=3)
    if jobs:
        return True, f"Jooble OK — {len(jobs)} offre(s) test pour « {query} »."
    return False, "Aucun résultat Jooble (clé invalide ou quota épuisé)."


def test_optioncarriere_connection(
    api_key: str,
    query: str = "alternance",
    *,
    user_ip: str = "",
    referer: str = "https://localhost/",
    client_ip: str = "",
) -> tuple[bool, str]:
    return probe_optioncarriere_connection(
        api_key,
        user_ip=user_ip,
        referer=referer,
        client_ip=client_ip,
        query=query,
    )


def test_serpapi_platform_connection(
    api_key: str,
    platform: str,
    query: str = "alternance",
) -> tuple[bool, str]:
    if not api_key.strip():
        return False, "SERPAPI_API_KEY manquante."
    searchers = {
        "indeed": search_jobs_indeed_serpapi,
        "linkedin": search_jobs_linkedin_serpapi,
        "glassdoor": search_jobs_glassdoor_serpapi,
        "hellowork": search_jobs_hellowork_serpapi,
        "monster": search_jobs_monster_serpapi,
        "talent": search_jobs_talent_serpapi,
    }
    fn = searchers.get(platform)
    if not fn:
        return False, f"Plateforme inconnue : {platform}"
    try:
        jobs = fn(query, "", "France", api_key)
    except Exception as exc:  # noqa: BLE001
        return False, f"Erreur SerpApi ({platform}) : {exc}"
    if jobs:
        return True, f"{platform.title()} OK — {len(jobs)} offre(s) test."
    return False, f"Aucun résultat {platform} via SerpApi pour « {query} »."


def test_hellowork_connection(
    apify_token: str,
    *,
    serpapi_key: str = "",
    query: str = "alternance",
) -> tuple[bool, str]:
    jobs = search_jobs_hellowork(
        query, "Paris", "Alternance", apify_token, serpapi_key=serpapi_key, max_results=3
    )
    if jobs:
        return True, f"HelloWork OK — {len(jobs)} offre(s) test pour « {query} »."
    if not apify_token.strip() and not serpapi_key.strip():
        return (
            False,
            "APIFY_API_TOKEN ou SERPAPI_API_KEY requis pour HelloWork.",
        )
    return False, "Aucun résultat HelloWork (token Apify/SerpApi ou acteur indisponible)."


def test_monster_connection(
    apify_token: str,
    *,
    serpapi_key: str = "",
    query: str = "alternance",
) -> tuple[bool, str]:
    jobs = search_jobs_monster(
        query, "Paris", "France", apify_token, serpapi_key=serpapi_key, max_pages=1
    )
    if jobs:
        return True, f"Monster OK — {len(jobs)} offre(s) test pour « {query} »."
    if not apify_token.strip() and not serpapi_key.strip():
        return False, "APIFY_API_TOKEN ou SERPAPI_API_KEY requis pour Monster."
    return False, "Aucun résultat Monster (token Apify/SerpApi ou acteur indisponible)."


def test_talent_connection(
    apify_token: str,
    *,
    serpapi_key: str = "",
    query: str = "alternance",
) -> tuple[bool, str]:
    jobs = search_jobs_talent(
        query, "Paris", "France", apify_token, serpapi_key=serpapi_key, max_results=3
    )
    if jobs:
        return True, f"Talent.com OK — {len(jobs)} offre(s) test pour « {query} »."
    if not apify_token.strip() and not serpapi_key.strip():
        return False, "APIFY_API_TOKEN ou SERPAPI_API_KEY requis pour Talent.com."
    return False, "Aucun résultat Talent.com (token Apify/SerpApi ou acteur indisponible)."


def test_jobteaser_connection(
    apify_token: str,
    query: str = "alternance",
) -> tuple[bool, str]:
    if not apify_token.strip():
        return (
            False,
            "APIFY_API_TOKEN manquant — créez un compte sur apify.com pour JobTeaser.",
        )
    jobs = search_jobs_jobteaser(query, "", "Alternance", apify_token, max_results=3)
    if jobs:
        return True, f"JobTeaser OK — {len(jobs)} offre(s) test pour « {query} »."
    return False, "Aucun résultat JobTeaser (token Apify ou acteur indisponible)."


def provider_secrets_from_getter(get_secret: Callable[[str, str], str]) -> dict[str, str]:
    """Collect provider credentials from a Streamlit-style get_secret helper."""
    return {
        "adzuna_app_id": get_secret("ADZUNA_APP_ID", ""),
        "adzuna_app_key": get_secret("ADZUNA_APP_KEY", ""),
        "serpapi_api_key": get_secret("SERPAPI_API_KEY", ""),
        "jooble_api_key": get_secret("JOOBLE_API_KEY", ""),
        "careerjet_api_key": get_secret("CAREERJET_API_KEY", ""),
        "careerjet_user_ip": get_secret("CAREERJET_USER_IP", "127.0.0.1"),
        "careerjet_referer": get_secret("CAREERJET_REFERER", "https://localhost/"),
        "apify_api_token": get_secret("APIFY_API_TOKEN", ""),
    }


def configured_providers(
    has_adzuna: bool | None = None,
    has_serpapi: bool | None = None,
    wttj_enabled: bool = True,
    *,
    secrets: dict[str, str] | None = None,
) -> list[str]:
    """Return providers that can be used in « all » mode."""
    if secrets is not None:
        has_adzuna = bool(secrets.get("adzuna_app_id") and secrets.get("adzuna_app_key"))
        has_serpapi = bool(secrets.get("serpapi_api_key"))
        has_jooble = bool(secrets.get("jooble_api_key"))
        has_careerjet = bool(secrets.get("careerjet_api_key"))
        has_apify = bool(secrets.get("apify_api_token"))
    else:
        has_adzuna = bool(has_adzuna)
        has_serpapi = bool(has_serpapi)
        has_jooble = False
        has_careerjet = False
        has_apify = False

    available: list[str] = []
    if has_adzuna:
        available.append(JOB_PROVIDER_ADZUNA)
    if wttj_enabled:
        available.append(JOB_PROVIDER_WTTJ)
    if has_apify:
        available.append(JOB_PROVIDER_JOBTEASER)
    if has_jooble:
        available.append(JOB_PROVIDER_JOOBLE)
    if has_careerjet:
        available.append(JOB_PROVIDER_OPTIONCARRIERE)
    if has_serpapi:
        available.extend(
            [
                JOB_PROVIDER_INDEED,
                JOB_PROVIDER_LINKEDIN,
                JOB_PROVIDER_GLASSDOOR,
                JOB_PROVIDER_SERPAPI,
            ]
        )
    if has_apify or has_serpapi:
        for provider_id in (
            JOB_PROVIDER_HELLOWORK,
            JOB_PROVIDER_MONSTER,
            JOB_PROVIDER_TALENT,
        ):
            if provider_id not in available:
                available.append(provider_id)
    return available


def default_job_provider(
    has_adzuna: bool | None = None,
    has_serpapi: bool | None = None,
    *,
    secrets: dict[str, str] | None = None,
) -> str:
    """Pick a sensible default provider."""
    providers = configured_providers(
        has_adzuna=has_adzuna,
        has_serpapi=has_serpapi,
        secrets=secrets,
    )
    if len(providers) > 1:
        return JOB_PROVIDER_ALL
    if JOB_PROVIDER_WTTJ in providers:
        return JOB_PROVIDER_WTTJ
    return providers[0] if providers else JOB_PROVIDER_WTTJ
