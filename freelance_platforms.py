"""Freelance marketplaces by country and mission listing helpers."""

from __future__ import annotations

import re
from typing import Any

from priority_employers import normalize_employer_country

SEARCH_MODE_EMPLOI = "emploi"
SEARCH_MODE_FREELANCE = "freelance"
SEARCH_MODES = (SEARCH_MODE_EMPLOI, SEARCH_MODE_FREELANCE)

FREELANCE_QUERY_KEYWORDS = (
    "freelance",
    "mission",
    "contract",
    "consultant",
    "remote",
    "independent contractor",
    "project-based",
    "gig",
)

# (display name, public host) — searched via SerpApi site: restriction.
GLOBAL_FREELANCE_PLATFORMS: tuple[tuple[str, str], ...] = (
    ("Upwork", "upwork.com"),
    ("Fiverr", "fiverr.com"),
    ("Freelancer", "freelancer.com"),
)

COUNTRY_FREELANCE_PLATFORMS: dict[str, tuple[tuple[str, str], ...]] = {
    "France": (
        ("Malt", "malt.fr"),
        ("Freelance.com", "freelance.com"),
        ("Free-Work", "free-work.com"),
        ("Comet", "comet.co"),
        ("Codeur", "codeur.com"),
        ("ComeUp", "comeup.com"),
        ("Crème de la Crème", "cremedelacreme.io"),
        ("Upwork", "upwork.com"),
    ),
    "Belgique": (
        ("Malt", "malt.fr"),
        ("Freelance.com", "freelance.com"),
        ("Twago", "twago.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
    ),
    "Suisse": (
        ("Malt", "malt.fr"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Twago", "twago.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Canada": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Guru", "guru.com"),
        ("Toptal", "toptal.com"),
        ("Workhoppers", "workhoppers.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Etats-Unis": (
        ("Upwork", "upwork.com"),
        ("Fiverr", "fiverr.com"),
        ("Toptal", "toptal.com"),
        ("Freelancer", "freelancer.com"),
        ("Guru", "guru.com"),
        ("We Work Remotely", "weworkremotely.com"),
    ),
    "Royaume-Uni": (
        ("PeoplePerHour", "peopleperhour.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Toptal", "toptal.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Allemagne": (
        ("Freelancermap", "freelancermap.de"),
        ("Twago", "twago.com"),
        ("Upwork", "upwork.com"),
        ("Freelance.de", "freelance.de"),
        ("Fiverr", "fiverr.com"),
    ),
    "Espagne": (
        ("Malt", "malt.es"),
        ("Workana", "workana.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Italie": (
        ("Malt", "malt.it"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Portugal": (
        ("Malt", "malt.pt"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Pays-Bas": (
        ("Malt", "malt.nl"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Suede": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Toptal", "toptal.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Norvege": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Danemark": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Finlande": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Australie": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
        ("Toptal", "toptal.com"),
    ),
    "Nouvelle-Zelande": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Maroc": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Cote d Ivoire": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Senegal": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Cameroun": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Kenya": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
        ("Toptal", "toptal.com"),
    ),
    "Nigeria": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
        ("Toptal", "toptal.com"),
    ),
    "Ghana": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Afrique du Sud": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
        ("Toptal", "toptal.com"),
    ),
    "Tunisie": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Algerie": (
        ("ComeUp", "comeup.com"),
        ("Freelance.com", "freelance.com"),
        ("Upwork", "upwork.com"),
        ("Fiverr", "fiverr.com"),
    ),
    "Egypte": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
        ("Mostaql", "mostaql.com"),
    ),
    "Rwanda": (
        ("Upwork", "upwork.com"),
        ("Freelancer", "freelancer.com"),
        ("Fiverr", "fiverr.com"),
    ),
}

_BUDGET_RE = re.compile(
    r"(?:tjm|budget|rate|tarif|daily)\s*[:\-]?\s*(\d[\d\s]{1,6})\s*(?:€|eur|\$|usd|cad|£)?(?:\s*(?:/?\s*(?:j(?:our)?|day|d)\b|/j\b))?",
    re.I,
)
_EUR_DAY_RE = re.compile(
    r"(\d[\d\s]{1,6})\s*(?:€|eur)\s*(?:ht\s*)?(?:/?\s*(?:j(?:our)?|day)|/j)\b",
    re.I,
)
_DURATION_RE = re.compile(
    r"(\d{1,3})\s*(?:mois|month|months|semaines?|weeks?|jours?|days?)",
    re.I,
)


def normalize_search_mode(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"freelance", "mission", "missions", "independant", "indépendant"}:
        return SEARCH_MODE_FREELANCE
    return SEARCH_MODE_EMPLOI


def profile_search_mode(profile: dict[str, Any] | None) -> str:
    """emploi unless the student explicitly chose freelance mode."""
    profile = profile or {}
    stored = normalize_search_mode(str(profile.get("search_mode") or ""))
    if stored == SEARCH_MODE_FREELANCE:
        return SEARCH_MODE_FREELANCE
    contract = str(profile.get("contract_type") or "").strip().lower()
    if contract == "freelance":
        return SEARCH_MODE_FREELANCE
    return SEARCH_MODE_EMPLOI


def is_freelance_mode(profile: dict[str, Any] | None) -> bool:
    return profile_search_mode(profile) == SEARCH_MODE_FREELANCE


def _country_key(country: str) -> str:
    return normalize_employer_country(country) or str(country or "").strip()


def platforms_for_countries(
    countries: list[str] | tuple[str, ...] | None,
    *,
    max_platforms: int = 8,
) -> list[tuple[str, str]]:
    """Unique (name, host) marketplaces for the student's selected countries."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    wanted = [item for item in (countries or []) if str(item).strip()] or ["France"]
    for country in wanted:
        key = _country_key(country)
        rows = COUNTRY_FREELANCE_PLATFORMS.get(key) or GLOBAL_FREELANCE_PLATFORMS
        for name, host in rows:
            host_key = host.strip().lower()
            if not host_key or host_key in seen:
                continue
            seen.add(host_key)
            out.append((name, host_key))
            if len(out) >= max_platforms:
                return out
    if not out:
        for name, host in GLOBAL_FREELANCE_PLATFORMS:
            out.append((name, host))
    return out[:max_platforms]


def freelance_platform_hosts(countries: list[str] | tuple[str, ...] | None) -> list[str]:
    return [host for _name, host in platforms_for_countries(countries)]


def enrich_query_for_freelance(query: str) -> str:
    """Keep the job title first, then add compact freelance search terms."""
    cleaned = " ".join(str(query or "").split())
    if not cleaned:
        return "freelance mission"
    blob = cleaned.lower()
    extras = [word for word in ("freelance", "mission", "contract", "consultant") if word not in blob]
    if not extras:
        return cleaned
    return f"{cleaned} {' '.join(extras[:3])}".strip()


def _parse_int_token(raw: str) -> int | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    if 50 <= value <= 5000:
        return value
    if 50_000 <= value <= 5_000_000:
        return value // 1000
    return None


def infer_mission_daily_rate(job: dict[str, Any]) -> int | None:
    for field in ("mission_budget", "daily_rate", "tjm", "budget"):
        raw = job.get(field)
        if isinstance(raw, (int, float)) and raw > 0:
            value = int(raw)
            return value if value < 20_000 else value // 220
        parsed = _parse_int_token(str(raw or ""))
        if parsed:
            return parsed
    blob = f"{job.get('title', '')} {job.get('description', '')} {job.get('salary', '')}"
    for pattern in (_EUR_DAY_RE, _BUDGET_RE):
        match = pattern.search(blob)
        if match:
            parsed = _parse_int_token(match.group(1))
            if parsed:
                return parsed
    return None


def infer_mission_duration(job: dict[str, Any]) -> str:
    stored = str(job.get("mission_duration") or job.get("duration") or "").strip()
    if stored:
        return stored
    blob = f"{job.get('title', '')} {job.get('description', '')}"
    match = _DURATION_RE.search(blob)
    return match.group(0).strip() if match else ""


def tag_freelance_mission(job: dict[str, Any], *, platform: str = "") -> dict[str, Any]:
    """Mark a listing as a freelance mission and extract budget / duration when present."""
    item = dict(job)
    item["listing_kind"] = "mission"
    if not str(item.get("contract_type") or "").strip():
        item["contract_type"] = "Freelance"
    if platform and not str(item.get("source") or "").strip():
        item["source"] = platform
    budget = infer_mission_daily_rate(item)
    if budget:
        item["mission_budget"] = budget
        item["daily_rate"] = budget
    duration = infer_mission_duration(item)
    if duration:
        item["mission_duration"] = duration
    client = str(item.get("company") or "").strip()
    if client:
        item["client"] = client
    return item


def job_matches_budget(job: dict[str, Any], daily_rate: int) -> bool:
    """Keep unknown budgets; drop missions clearly below the student's TJM."""
    floor = int(daily_rate or 0)
    if floor <= 0:
        return True
    listed = infer_mission_daily_rate(job)
    if listed is None:
        return True
    return listed >= int(floor * 0.7)
