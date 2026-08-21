"""Strict job filtering by contract, geography, experience and sector."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any

import requests

from france_geo import (
    find_region_for_department_code,
    profile_all_cities,
    resolve_multi_geo_from_profile,
    resolve_selected_cities,
)
from job_providers import WTTJ_CONTRACT_MAP

CONTRACT_TYPES = (
    "CDI",
    "CDD",
    "Alternance",
    "Stage",
    "Freelance",
    "Intérim",
)

COUNTRY_OPTIONS = ("France",)

GEO_FILTER_MODES = (
    "ville",
    "departement",
    "rayon",
)

EXPERIENCE_LEVELS = (
    "junior",
    "confirme",
    "senior",
    "tous",
)

EXPERIENCE_LABELS = {
    "junior": "Junior",
    "confirme": "Confirmé",
    "senior": "Senior",
    "tous": "Tous niveaux",
}

SECTOR_OPTIONS = (
    "Informatique",
    "Télécoms",
    "Finance",
    "Santé",
    "Industrie",
    "Commerce",
    "Transport",
    "Énergie",
    "Consulting",
    "Public",
    "Éducation",
    "Immobilier",
    "Média",
    "Autre",
)

CONTRACT_ALIASES: dict[str, tuple[str, ...]] = {
    "CDI": (
        "cdi",
        "permanent",
        "durée indéterminée",
        "duree indeterminee",
        "temps plein",
        "full time",
        "full-time",
    ),
    "CDD": (
        "cdd",
        "contract",
        "durée déterminée",
        "duree determinee",
        "fixed term",
        "fixed-term",
    ),
    "Alternance": (
        "alternance",
        "alternant",
        "alternante",
        " en alternance",
        "apprentissage",
        "apprenti",
        "apprentie",
        "contrat pro",
        "contrat de professionnalisation",
        "contrat d'apprentissage",
        "contrat d apprentissage",
        "professionnalisation",
        "work-study",
        "work study",
        "cfa",
    ),
    "Stage": (
        "stage",
        "internship",
        "stagiaire",
        "intern ",
    ),
    "Freelance": (
        "freelance",
        "indépendant",
        "independant",
        "independent contractor",
        "portage",
    ),
    "Intérim": (
        "intérim",
        "interim",
        "mission intérimaire",
        "mission interim",
        "temporaire",
        "temporary",
    ),
}

ADZUNA_CONTRACT_MAP = {
    "permanent": "CDI",
    "contract": "CDD",
    "part_time": "CDI",
}

# Terms appended to Adzuna/SerpApi queries to surface the right contract type.
CONTRACT_SEARCH_TERMS: dict[str, str] = {
    "Alternance": "alternance",
    "Stage": "stage",
    "CDD": "CDD",
    "Intérim": "intérim",
    "Freelance": "freelance",
}

# Prefer specific contracts before generic Adzuna metadata (often wrong).
CONTRACT_INFERENCE_ORDER = (
    "Alternance",
    "Stage",
    "Intérim",
    "Freelance",
    "CDD",
    "CDI",
)

EXPERIENCE_ALIASES: dict[str, tuple[str, ...]] = {
    "junior": (
        "junior",
        "debutant",
        "débutant",
        "debutant",
        "0-2 ans",
        "1 an d'experience",
        "2 ans d'experience",
        "young professional",
        "jeune diplome",
        "jeune diplômé",
        "first experience",
    ),
    "confirme": (
        "confirme",
        "confirmé",
        "intermediaire",
        "intermédiaire",
        "3 ans",
        "4 ans",
        "5 ans",
        "2 a 5 ans",
        "2 à 5 ans",
        "experimente",
        "expérimenté",
    ),
    "senior": (
        "senior",
        "expert",
        "lead",
        "principal",
        "architecte",
        "5+ ans",
        "10 ans",
        "15 ans",
        "chef de",
        "manager",
        "directeur",
    ),
}

SECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "Informatique": (
        "informatique",
        "it ",
        " tech",
        "software",
        "digital",
        "cyber",
        "systeme",
        "système",
        "developpeur",
        "développeur",
        "devops",
        "data",
    ),
    "Télécoms": ("telecom", "télécom", "reseau", "réseau", "fibre", "5g", "operateur"),
    "Finance": ("finance", "banque", "banking", "assurance", "fintech", "comptab"),
    "Santé": ("sante", "santé", "medical", "médical", "hopital", "hôpital", "pharma"),
    "Industrie": ("industrie", "industrial", "manufacturing", "usine", "production"),
    "Commerce": ("commerce", "retail", "distribution", "e-commerce", "vente"),
    "Transport": ("transport", "logistique", "supply chain", "mobilite"),
    "Énergie": ("energie", "énergie", "energy", "utilities", "renouvelable"),
    "Consulting": ("consulting", "conseil", "cabinet", "audit", "esi"),
    "Public": ("public", "collectivite", "collectivité", "administration", "service public"),
    "Éducation": ("education", "éducation", "ecole", "école", "universite", "formation"),
    "Immobilier": ("immobilier", "real estate", "promotion immobiliere"),
    "Média": ("media", "média", "communication", "marketing", "publicite"),
    "Autre": (),
}

# Location markers that indicate a job is outside metropolitan France.
FOREIGN_LOCATION_MARKERS: tuple[str, ...] = (
    "cameroon",
    "cameroun",
    "douala",
    "yaounde",
    "yaoundé",
    "united kingdom",
    "royaume-uni",
    " u.k.",
    " uk,",
    " uk ",
    "london",
    "germany",
    "allemagne",
    "berlin",
    "spain",
    "espagne",
    "madrid",
    "italy",
    "italie",
    "rome",
    "belgium",
    "belgique",
    "bruxelles",
    "brussels",
    "switzerland",
    "suisse",
    "geneve",
    "genève",
    "zurich",
    "usa",
    "united states",
    "états-unis",
    "etats-unis",
    "canada",
    "montreal",
    "montréal",
    "senegal",
    "sénégal",
    "maroc",
    "morocco",
    "casablanca",
    "tunisia",
    "tunisie",
    "algeria",
    "algérie",
    "algerie",
)

DEPARTMENT_LOCATION_ALIASES: dict[str, tuple[str, ...]] = {
    "75": ("paris",),
    "94": ("val-de-marne", "val de marne", "limeil", "vincennes", "creteil", "créteil"),
    "92": ("hauts-de-seine", "hauts de seine", "nanterre", "boulogne"),
    "93": ("seine-saint-denis", "seine saint denis", "saint-denis"),
    "91": ("essonne", "evry", "évry"),
    "78": ("yvelines", "versailles"),
    "95": ("val-d'oise", "val d oise", "cergy"),
    "77": ("seine-et-marne", "seine et marne", "melun"),
    "69": ("rhone", "rhône", "lyon"),
    "13": ("bouches-du-rhone", "bouches du rhone", "marseille"),
    "31": ("haute-garonne", "toulouse"),
    "33": ("gironde", "bordeaux"),
    "59": ("nord", "lille"),
    "44": ("loire-atlantique", "loire atlantique", "nantes"),
    "67": ("bas-rhin", "strasbourg"),
}


def build_domicile_location(profile: dict[str, Any]) -> str:
    """Home address for radius-search center (not Adzuna API scope)."""
    parts: list[str] = []
    city = str(profile.get("home_city", "")).strip()
    postal = str(profile.get("postal_code", "")).strip()
    country = profile_country(profile)
    if city:
        parts.append(city)
    if postal:
        parts.append(postal)
    parts.append(country)
    return ", ".join(parts)


def build_profile_search_location(profile: dict[str, Any]) -> str:
    """Backward-compatible alias — domicile only (API search is country-wide)."""
    return build_domicile_location(profile)


def profile_country(profile: dict[str, Any]) -> str:
    return str(profile.get("country", "France")).strip() or "France"


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_contract_type(value: str) -> str:
    cleaned = value.strip()
    for contract in CONTRACT_TYPES:
        if normalize_text(cleaned) == normalize_text(contract):
            return contract
    return cleaned


def extract_french_department(postal_code: str) -> str:
    """Return French department code from a postal code (e.g. 94450 -> 94)."""
    digits = re.sub(r"\D", "", postal_code or "")
    if len(digits) < 2:
        return ""
    if digits.startswith(("971", "972", "973", "974", "976")):
        return digits[:3]
    if digits.startswith(("200", "201")):
        return "2A" if digits.startswith("200") else "2B"
    return digits[:2]


def infer_job_contract(job: dict[str, Any]) -> str:
    """Infer normalized contract type — title/description first, then API metadata."""
    blob = normalize_text(
        " ".join(
            [
                str(job.get("title", "")),
                str(job.get("description", "")),
            ]
        )
    )

    for contract in CONTRACT_INFERENCE_ORDER:
        if any(alias in blob for alias in CONTRACT_ALIASES[contract]):
            return contract

    raw_type = str(job.get("contract_type", "")).strip().lower()
    if raw_type in WTTJ_CONTRACT_MAP:
        return WTTJ_CONTRACT_MAP[raw_type]
    if raw_type in ADZUNA_CONTRACT_MAP:
        return ADZUNA_CONTRACT_MAP[raw_type]

    return ""


def enrich_query_for_contract(query: str, contract_type: str) -> str:
    """Add contract keyword to job search query when missing."""
    cleaned = query.strip()
    expected = normalize_contract_type(contract_type)
    boost = CONTRACT_SEARCH_TERMS.get(expected, "")
    if not boost or not cleaned:
        return cleaned
    if normalize_text(boost) in normalize_text(cleaned):
        return cleaned
    return f"{cleaned} {boost}".strip()


def format_filter_rejection_hint(
    stats: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    """Human-readable hint when strict filters remove all jobs."""
    parts: list[str] = []
    contract = profile.get("contract_type", "CDI")
    if stats.get("rejected_contract", 0) >= stats.get("total", 0) * 0.5:
        parts.append(
            f"contrat **{contract}** (Adzuna classe souvent les offres en CDI — "
            "la recherche inclut maintenant le mot-clé du contrat)"
        )
    if stats.get("rejected_geo", 0):
        cities = resolve_selected_cities(profile)
        parts.append(
            "zone géographique "
            f"(villes : {', '.join(cities[:3])}{'…' if len(cities) > 3 else ''})"
        )
    if stats.get("rejected_experience", 0):
        parts.append(f"niveau **{stats.get('experience_level', '—')}**")
    if stats.get("rejected_sector", 0):
        sectors = stats.get("target_sectors") or []
        parts.append(f"secteur(s) **{', '.join(sectors) if sectors else 'CV'}**")
    return " · ".join(parts) if parts else "filtres stricts du profil"


def normalize_experience_level(value: str) -> str:
    cleaned = normalize_text(value)
    mapping = {
        "junior": "junior",
        "debutant": "junior",
        "débutant": "junior",
        "confirme": "confirme",
        "confirmé": "confirme",
        "senior": "senior",
        "tous": "tous",
        "tous niveaux": "tous",
    }
    return mapping.get(cleaned, cleaned)


def parse_target_sectors(raw: Any) -> list[str]:
    """Parse sector list from JSON string, list, or comma-separated text."""
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    if not raw:
        return []
    text = str(raw).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(s).strip() for s in parsed if str(s).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in text.split(",") if part.strip()]


def serialize_target_sectors(sectors: list[str]) -> str:
    return json.dumps([s for s in sectors if s], ensure_ascii=False)


def resolve_experience_level(
    profile: dict[str, Any],
    cv_profile: dict[str, Any] | None = None,
) -> str:
    level = normalize_experience_level(str(profile.get("experience_level", "")).strip())
    if level and level != "tous":
        return level
    if level == "tous":
        return "tous"
    if cv_profile:
        cv_level = normalize_experience_level(str(cv_profile.get("niveau_experience", "")))
        if cv_level:
            return cv_level
    return "confirme"


def resolve_target_sectors(
    profile: dict[str, Any],
    cv_profile: dict[str, Any] | None = None,
) -> list[str]:
    sectors = parse_target_sectors(profile.get("target_sectors"))
    if sectors:
        return sectors
    if cv_profile:
        cv_sectors = cv_profile.get("secteurs") or []
        if isinstance(cv_sectors, list):
            return [str(s).strip() for s in cv_sectors if str(s).strip()]
    return []


def infer_job_experience_level(job: dict[str, Any]) -> str:
    blob = normalize_text(
        " ".join(
            [
                str(job.get("title", "")),
                str(job.get("description", "")),
                str(job.get("experience_level", "")),
            ]
        )
    )
    for level in ("senior", "junior", "confirme"):
        if any(alias in blob for alias in EXPERIENCE_ALIASES[level]):
            return level
    return ""


def infer_job_sector(job: dict[str, Any]) -> str:
    blob = normalize_text(
        " ".join([str(job.get("title", "")), str(job.get("description", ""))])
    )
    for sector, aliases in SECTOR_ALIASES.items():
        if normalize_text(sector) in blob:
            return sector
        if any(alias in blob for alias in aliases):
            return sector
    return ""


def job_matches_experience_level(job: dict[str, Any], expected_level: str) -> bool:
    """Strict experience filter — exact match; unknown job level is rejected."""
    expected = normalize_experience_level(expected_level)
    if not expected or expected == "tous":
        return True
    inferred = infer_job_experience_level(job)
    if not inferred:
        return False
    return inferred == expected


def job_matches_sector(job: dict[str, Any], target_sectors: list[str]) -> bool:
    """Strict sector filter — job must match at least one target sector."""
    if not target_sectors:
        return True
    blob = normalize_text(
        " ".join([str(job.get("title", "")), str(job.get("description", ""))])
    )
    for sector in target_sectors:
        sector_norm = normalize_text(sector)
        if sector_norm in blob:
            return True
        for alias in SECTOR_ALIASES.get(sector, ()):
            if alias in blob:
                return True
    inferred = infer_job_sector(job)
    if inferred and inferred in target_sectors:
        return True
    return False


def job_matches_contract(job: dict[str, Any], user_contract: str) -> bool:
    """Strict contract filter — exact match only."""
    expected = normalize_contract_type(user_contract)
    inferred = infer_job_contract(job)
    if not inferred:
        return False
    return inferred == expected


def _coords_from_nominatim(query: str) -> tuple[float, float] | None:
    if not query.strip():
        return None
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "DowsonBost/1.0 (job-matching)"},
            timeout=15,
        )
        if not response.ok:
            return None
        results = response.json()
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))


def job_matches_country(job: dict[str, Any], expected_country: str) -> bool:
    """Job location must match the user's selected country."""
    location_raw = str(job.get("location", ""))
    location = normalize_text(location_raw)
    country_norm = normalize_text(expected_country or "France")

    if country_norm == "france":
        for marker in FOREIGN_LOCATION_MARKERS:
            if marker in location:
                return False
        if "france" in location or "francais" in location:
            return True
        if re.search(r"\b\d{5}\b", location_raw):
            return True
        if re.search(r"\(\d{2,3}[AB]?\)", location_raw):
            return True
        return bool(location.strip())

    return country_norm in location or normalize_text(expected_country) in location


def _job_matches_single_department(
    job: dict[str, Any],
    department_code: str,
    department_name: str,
    postal_code: str,
) -> bool:
    location_raw = str(job.get("location", ""))
    location = normalize_text(location_raw)
    department = department_code.strip().upper()
    if not department:
        department = extract_french_department(postal_code)
    if not department:
        return False

    if re.search(rf"\b{re.escape(department)}\b", location_raw):
        return True
    if re.search(rf"\({re.escape(department)}\)", location_raw):
        return True

    dept_name_norm = normalize_text(department_name)
    if dept_name_norm and dept_name_norm in location:
        return True

    if postal_code and postal_code in location_raw:
        return True

    for match in re.finditer(r"\b(\d{5})\b", location_raw):
        if extract_french_department(match.group(1)) == department:
            return True

    for alias in DEPARTMENT_LOCATION_ALIASES.get(department, ()):
        if normalize_text(alias) in location:
            return True

    return False


def job_matches_department(job: dict[str, Any], profile: dict[str, Any]) -> bool:
    """Job must be in one of the user's selected departments."""
    _, departments = resolve_multi_geo_from_profile(profile)
    postal_code = str(profile.get("postal_code", "")).strip()

    if departments:
        return any(
            _job_matches_single_department(
                job,
                dept.get("code", ""),
                dept.get("name", ""),
                postal_code,
            )
            for dept in departments
        )

    department_code = str(profile.get("department_code", "")).strip().upper()
    department_name = str(profile.get("department_name", "")).strip()
    return _job_matches_single_department(
        job, department_code, department_name, postal_code
    )


def job_matches_region(job: dict[str, Any], profile: dict[str, Any]) -> bool:
    """Job must be in one of the user's selected regions (or implied by department)."""
    regions, departments = resolve_multi_geo_from_profile(profile)
    location = normalize_text(str(job.get("location", "")))
    region_norms = {normalize_text(r) for r in regions if r}

    if any(rn in location for rn in region_norms if rn):
        return True

    postal_code = str(profile.get("postal_code", "")).strip()
    for dept in departments:
        dept_region = dept.get("region") or find_region_for_department_code(dept.get("code", ""))
        if normalize_text(dept_region) in region_norms:
            if _job_matches_single_department(
                job,
                dept.get("code", ""),
                dept.get("name", ""),
                postal_code,
            ):
                return True

    return False


def _city_match_tokens(city: str) -> list[str]:
    norm = normalize_text(city)
    tokens = [norm] if norm else []
    for part in re.split(r"[-\s]+", norm):
        if len(part) >= 4 and part not in tokens:
            tokens.append(part)
    return tokens


def _job_matches_single_city(
    job: dict[str, Any],
    city: str,
    postal_code: str = "",
) -> bool:
    location_raw = str(job.get("location", ""))
    location = normalize_text(location_raw)

    for token in _city_match_tokens(city):
        if token in location:
            return True
    if postal_code and postal_code in location_raw:
        return True
    return False


def job_matches_city(job: dict[str, Any], profile: dict[str, Any]) -> bool:
    """Job must be in one of the user's selected cities."""
    cities = resolve_selected_cities(profile)
    if not cities:
        return False
    postal_code = str(profile.get("postal_code", "")).strip()
    home_city = normalize_text(str(profile.get("home_city", "")).strip())
    return any(
        _job_matches_single_city(
            job,
            city,
            postal_code if normalize_text(city) == home_city else "",
        )
        for city in cities
    )


def job_matches_geography(
    job: dict[str, Any],
    profile: dict[str, Any],
    user_coords: tuple[float, float] | None = None,
    job_coords_cache: dict[str, tuple[float, float] | None] | None = None,
) -> bool:
    """Strict filter: country + regions + departments + cities (+ optional radius)."""
    mode = str(profile.get("geo_filter_mode", "departement")).strip().lower()
    radius_km = int(profile.get("search_radius_km") or 20)
    country = profile_country(profile)
    regions, departments = resolve_multi_geo_from_profile(profile)

    if not job_matches_country(job, country):
        return False
    if regions and not job_matches_region(job, profile):
        return False
    if departments and not job_matches_department(job, profile):
        return False
    if not profile_all_cities(profile):
        cities = resolve_selected_cities(profile)
        if cities and not job_matches_city(job, profile):
            return False

    if mode == "rayon":
        if not user_coords:
            return True

        cache = job_coords_cache if job_coords_cache is not None else {}
        location_raw = str(job.get("location", ""))
        if location_raw not in cache:
            cache[location_raw] = _coords_from_nominatim(location_raw)

        job_coords = cache.get(location_raw)
        if job_coords:
            return haversine_km(user_coords, job_coords) <= radius_km
        return False

    return True


def apply_strict_job_filters(
    jobs: list[dict[str, Any]],
    profile: dict[str, Any],
    cv_profile: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter jobs by contract, geography, experience level and sector."""
    user_contract = normalize_contract_type(str(profile.get("contract_type", "CDI")))
    mode = str(profile.get("geo_filter_mode", "departement"))
    experience_level = resolve_experience_level(profile, cv_profile)
    target_sectors = resolve_target_sectors(profile, cv_profile)

    user_coords: tuple[float, float] | None = None
    job_coords_cache: dict[str, tuple[float, float] | None] = {}
    if mode == "rayon":
        user_coords = _coords_from_nominatim(build_domicile_location(profile))

    filtered: list[dict[str, Any]] = []
    stats = {
        "total": len(jobs),
        "rejected_contract": 0,
        "rejected_geo": 0,
        "rejected_experience": 0,
        "rejected_sector": 0,
        "kept": 0,
        "experience_level": experience_level,
        "target_sectors": target_sectors,
    }

    for job in jobs:
        if not job_matches_contract(job, user_contract):
            stats["rejected_contract"] += 1
            continue
        if not job_matches_geography(
            job,
            profile,
            user_coords=user_coords,
            job_coords_cache=job_coords_cache,
        ):
            stats["rejected_geo"] += 1
            continue
        if not job_matches_experience_level(job, experience_level):
            stats["rejected_experience"] += 1
            continue
        if not job_matches_sector(job, target_sectors):
            stats["rejected_sector"] += 1
            continue
        enriched = dict(job)
        enriched["inferred_contract"] = infer_job_contract(job)
        enriched["inferred_experience"] = infer_job_experience_level(job)
        enriched["inferred_sector"] = infer_job_sector(job)
        filtered.append(enriched)

    stats["kept"] = len(filtered)
    return filtered, stats


def profile_ready_for_matching(profile: dict[str, Any]) -> tuple[bool, str]:
    """Check whether user profile has mandatory matching fields."""
    if not str(profile.get("target_job_title", "")).strip():
        return False, "Indiquez le poste visé dans Mon profil."
    if not str(profile.get("home_city", "")).strip():
        return False, "Renseignez votre ville dans Mon profil."
    if not str(profile.get("postal_code", "")).strip():
        return False, "Renseignez votre code postal dans Mon profil."
    if not str(profile.get("contract_type", "")).strip():
        return False, "Sélectionnez votre type de contrat dans Mon profil."
    regions, departments = resolve_multi_geo_from_profile(profile)
    if not departments:
        return False, "Sélectionnez au moins un département dans Mon profil."
    if not regions:
        return False, "Sélectionnez au moins une région dans Mon profil."
    if not profile_all_cities(profile) and not resolve_selected_cities(profile):
        return False, "Sélectionnez au moins une ville ou activez « Toutes les villes »."
    return True, ""
