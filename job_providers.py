"""Job search providers: Adzuna, SerpApi, Welcome to the Jungle, Jooble, etc."""

from __future__ import annotations

from typing import Any, Callable

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
JOB_PROVIDER_ALL = "all"

JOB_PROVIDER_LABELS: dict[str, str] = {
    JOB_PROVIDER_ALL: "Tous les moteurs (fusion)",
    JOB_PROVIDER_ADZUNA: "Adzuna (gratuit, recommandé)",
    JOB_PROVIDER_WTTJ: "Welcome to the Jungle (gratuit)",
    JOB_PROVIDER_JOBTEASER: "JobTeaser (Apify)",
    JOB_PROVIDER_JOOBLE: "Jooble",
    JOB_PROVIDER_OPTIONCARRIERE: "OptionCarriere / Careerjet",
    JOB_PROVIDER_INDEED: "Indeed (SerpApi)",
    JOB_PROVIDER_LINKEDIN: "LinkedIn Jobs (SerpApi)",
    JOB_PROVIDER_GLASSDOOR: "Glassdoor (SerpApi)",
    JOB_PROVIDER_SERPAPI: "Google Jobs / SerpApi",
}

JOB_PROVIDER_SIDEBAR_ORDER = (
    JOB_PROVIDER_ALL,
    JOB_PROVIDER_ADZUNA,
    JOB_PROVIDER_WTTJ,
    JOB_PROVIDER_JOBTEASER,
    JOB_PROVIDER_JOOBLE,
    JOB_PROVIDER_OPTIONCARRIERE,
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_LINKEDIN,
    JOB_PROVIDER_GLASSDOOR,
    JOB_PROVIDER_SERPAPI,
)

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
) -> dict[str, Any]:
    return {
        "title": title or "N/A",
        "company": company or "N/A",
        "location": location or "N/A",
        "description": description or "",
        "url": url or "",
        "contract_type": contract_type,
        "source": source,
    }


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
    return {
        "title": hit.get("name", "N/A"),
        "company": company,
        "location": _wttj_location(hit),
        "description": description,
        "url": _wttj_job_url(hit),
        "contract_type": raw_contract,
        "source": "Welcome to the Jungle",
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
                    )
                )
            if len(batch) < results_per_page:
                break
        except (requests.RequestException, ValueError, TypeError):
            break
    return jobs


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

    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "locale_code": locale_code,
            "keywords": cleaned_query,
            "location": location.strip(),
            "page": page,
            "page_size": page_size,
            "user_ip": user_ip.strip() or "127.0.0.1",
            "user_agent": DEFAULT_USER_AGENT,
        }
        if careerjet_contract:
            params["contract_type"] = careerjet_contract
        try:
            response = requests.get(
                "https://search.api.careerjet.net/v4/query",
                params=params,
                auth=(api_key.strip(), ""),
                headers={"Content-Type": "application/json", "Referer": referer},
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
                    )
                )
            if page >= int(payload.get("pages") or 1):
                break
        except (requests.RequestException, ValueError, TypeError):
            break
    return jobs


def _parse_serpapi_google_jobs(data: dict[str, Any], source_label: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs_results") or []:
        apply_options = item.get("apply_options") or []
        apply_url = apply_options[0].get("link", "") if apply_options else ""
        via = str(item.get("via", "")).strip()
        jobs.append(
            _standard_job(
                str(item.get("title", "")),
                str(item.get("company_name", "")),
                str(item.get("location", "")),
                str(item.get("description", "")),
                apply_url or str(item.get("share_link", "")),
                contract_type=str(
                    (item.get("detected_extensions") or {}).get("schedule_type", "")
                ),
                source=f"{source_label} ({via})" if via else source_label,
            )
        )
    return jobs


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

    try:
        response = requests.post(
            f"https://api.apify.com/v2/acts/{APIFY_JOBTEASER_ACTOR}/run-sync-get-dataset-items",
            params={"token": apify_token.strip(), "timeout": 120},
            json=payload,
            timeout=130,
        )
        if not response.ok:
            return []
        items = response.json()
        if not isinstance(items, list):
            return []
    except (requests.RequestException, ValueError, TypeError):
        return []

    jobs: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        jobs.append(
            _standard_job(
                str(item.get("title", "") or item.get("job_title", "")),
                str(item.get("company", "") or item.get("company_name", "")),
                str(item.get("location", "") or item.get("job_location", "")),
                str(item.get("description", "") or item.get("job_description", "")),
                str(item.get("url", "") or item.get("apply_url", "") or item.get("job_url", "")),
                contract_type=str(item.get("contract_type", "") or item.get("contractType", "")),
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
) -> tuple[bool, str]:
    if not api_key.strip():
        return (
            False,
            "CAREERJET_API_KEY manquante — inscrivez-vous sur optioncarriere.com/partners/api",
        )
    jobs = search_jobs_optioncarriere(query, "", "France", api_key, max_pages=1, page_size=3)
    if jobs:
        return True, f"OptionCarriere OK — {len(jobs)} offre(s) test pour « {query} »."
    return False, "Aucun résultat Careerjet (clé, IP whitelist ou referer à vérifier)."


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
