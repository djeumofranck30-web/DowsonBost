"""ISO 3166-1 countries and adaptive administrative subdivisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from i18n import t
from france_geo import (
    parse_selected_cities,
    parse_selected_departments,
    profile_all_cities,
    resolve_multi_geo_from_profile,
    resolve_selected_cities,
    serialize_admin_regions,
    serialize_selected_cities,
    serialize_selected_departments,
)

_DATA_PATH = Path(__file__).resolve().parent / "data" / "iso3166_countries.json"
_BUNDLED_GEO_DIR = Path(__file__).resolve().parent / "data" / "world_cities"
_geo_manifest_cache: dict[str, dict[str, Any] | None] = {}

# level keys: level1 (region/state/province), level2 (dept/county), cities
COUNTRY_GEO_SCHEMA: dict[str, dict[str, Any]] = {
    "France": {
        "code": "FR",
        "level1_label": "Régions",
        "level2_label": "Départements",
        "city_label": "Villes",
        "has_commune_api": True,
        "requires_level1": True,
        "requires_level2": True,
    },
    "États-Unis": {
        "code": "US",
        "level1_label": "États",
        "level2_label": "Comtés",
        "city_label": "Villes",
        "level1_options": [
            "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
            "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
            "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
            "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
            "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
            "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
            "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
            "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
            "Washington", "West Virginia", "Wisconsin", "Wyoming",
        ],
        "level2_free_text": True,
    },
    "Canada": {
        "code": "CA",
        "level1_label": "Provinces / territoires",
        "city_label": "Villes",
        "level1_options": [
            "Alberta", "British Columbia", "Manitoba", "New Brunswick",
            "Newfoundland and Labrador", "Nova Scotia", "Ontario",
            "Prince Edward Island", "Quebec", "Saskatchewan",
            "Northwest Territories", "Nunavut", "Yukon",
        ],
    },
    "Royaume-Uni": {
        "code": "GB",
        "level1_label": "Régions / nations",
        "city_label": "Villes",
        "level1_options": [
            "England", "Scotland", "Wales", "Northern Ireland",
            "London", "South East", "North West", "West Midlands",
            "Yorkshire and the Humber", "East of England", "South West",
        ],
    },
    "Belgique": {
        "code": "BE",
        "level1_label": "Régions",
        "city_label": "Villes",
        "level1_options": ["Bruxelles-Capitale", "Flandre", "Wallonie"],
    },
    "Suisse": {
        "code": "CH",
        "level1_label": "Cantons",
        "city_label": "Villes",
        "level1_options": [
            "Zurich", "Berne", "Vaud", "Genève", "Argovie", "Bâle-Ville", "Bâle-Campagne",
            "Fribourg", "Valais", "Neuchâtel", "Lucerne", "Saint-Gall", "Tessin",
        ],
    },
    "Allemagne": {
        "code": "DE",
        "level1_label": "Länder",
        "city_label": "Villes",
        "level1_options": [
            "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg",
            "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen",
            "Rheinland-Pfalz", "Saarland", "Sachsen", "Sachsen-Anhalt",
            "Schleswig-Holstein", "Thüringen",
        ],
    },
    "Espagne": {
        "code": "ES",
        "level1_label": "Communautés autonomes",
        "city_label": "Villes",
        "level1_options": [
            "Andalousie", "Catalogne", "Madrid", "Valence", "Galice", "Pays basque",
            "Castille-et-León", "Castille-La Manche", "Aragon", "Murcie", "Baleares",
            "Canaries", "Asturies", "Navarre", "Cantabrie", "La Rioja", "Estrémadure",
        ],
    },
    "Italie": {
        "code": "IT",
        "level1_label": "Régions",
        "city_label": "Villes",
        "level1_options": [
            "Lombardie", "Latium", "Campanie", "Vénétie", "Sicile", "Piémont",
            "Émilie-Romagne", "Toscane", "Pouilles", "Ligurie", "Marches", "Sardaigne",
        ],
    },
    "Maroc": {
        "code": "MA",
        "level1_label": "Régions",
        "city_label": "Villes",
        "level1_options": [
            "Casablanca-Settat", "Rabat-Salé-Kénitra", "Marrakech-Safi", "Tanger-Tétouan-Al Hoceïma",
            "Fès-Meknès", "Oriental", "Souss-Massa", "Béni Mellal-Khénifra",
        ],
    },
}

COUNTRY_ALIASES: dict[str, str] = {
    "france": "France",
    "fr": "France",
    "etats-unis": "États-Unis",
    "usa": "États-Unis",
    "us": "États-Unis",
    "united states": "États-Unis",
    "royaume-uni": "Royaume-Uni",
    "uk": "Royaume-Uni",
    "gb": "Royaume-Uni",
    "united kingdom": "Royaume-Uni",
    "belgique": "Belgique",
    "be": "Belgique",
    "suisse": "Suisse",
    "ch": "Suisse",
    "canada": "Canada",
    "ca": "Canada",
    "allemagne": "Allemagne",
    "de": "Allemagne",
    "espagne": "Espagne",
    "es": "Espagne",
    "italie": "Italie",
    "it": "Italie",
    "maroc": "Maroc",
    "ma": "Maroc",
}


def _load_iso_countries() -> list[dict[str, str]]:
    if not _DATA_PATH.is_file():
        return [{"code": "FR", "name": "France"}]
    with _DATA_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return sorted(data, key=lambda item: item.get("name", ""))


ISO_COUNTRIES: list[dict[str, str]] = _load_iso_countries()
COUNTRY_OPTIONS: tuple[str, ...] = tuple(c["name"] for c in ISO_COUNTRIES)
COUNTRY_NAME_TO_CODE: dict[str, str] = {c["name"]: c["code"] for c in ISO_COUNTRIES}
COUNTRY_CODE_TO_NAME: dict[str, str] = {c["code"]: c["name"] for c in ISO_COUNTRIES}


def normalize_country_name(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "France"
    if raw in COUNTRY_NAME_TO_CODE:
        return raw
    alias = COUNTRY_ALIASES.get(raw.lower())
    if alias:
        return alias
    upper = raw.upper()
    if upper in COUNTRY_CODE_TO_NAME:
        return COUNTRY_CODE_TO_NAME[upper]
    return raw


def parse_selected_countries(raw: Any, *, fallback_country: str = "France") -> list[str]:
    if isinstance(raw, list):
        items = [normalize_country_name(str(item)) for item in raw if str(item).strip()]
        return items or [normalize_country_name(fallback_country)]
    if isinstance(raw, str) and raw.strip().startswith("["):
        try:
            return parse_selected_countries(json.loads(raw), fallback_country=fallback_country)
        except json.JSONDecodeError:
            pass
    if isinstance(raw, str) and raw.strip():
        return [normalize_country_name(raw)]
    return [normalize_country_name(fallback_country)]


def serialize_selected_countries(countries: list[str]) -> str:
    cleaned = []
    seen: set[str] = set()
    for item in countries:
        name = normalize_country_name(item)
        if name and name not in seen:
            seen.add(name)
            cleaned.append(name)
    return json.dumps(cleaned, ensure_ascii=False)


def parse_geo_by_country(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        return {normalize_country_name(k): dict(v) for k, v in raw.items()}
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            return parse_geo_by_country(json.loads(raw))
        except json.JSONDecodeError:
            return {}
    return {}


def serialize_geo_by_country(data: dict[str, dict[str, Any]]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load_bundled_geo_manifest(country_code: str) -> dict[str, Any] | None:
    code = country_code.strip().upper()
    if code in _geo_manifest_cache:
        cached = _geo_manifest_cache[code]
        return dict(cached) if cached else None
    path = _BUNDLED_GEO_DIR / code / "manifest.json"
    if not path.is_file():
        _geo_manifest_cache[code] = None
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict) and payload.get("level1_options"):
            _geo_manifest_cache[code] = payload
            return dict(payload)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    _geo_manifest_cache[code] = None
    return None


def country_geo_schema(country: str) -> dict[str, Any] | None:
    country = normalize_country_name(country)
    hardcoded = COUNTRY_GEO_SCHEMA.get(country)
    if hardcoded:
        return hardcoded
    code = COUNTRY_NAME_TO_CODE.get(country, "")
    if not code:
        return None
    return _load_bundled_geo_manifest(code)


def country_has_subdivisions(country: str) -> bool:
    return country_geo_schema(country) is not None


def communes_supported_for_country(country: str) -> bool:
    """City multiselect is available for all ISO countries."""
    return bool(normalize_country_name(country))


def _empty_country_geo() -> dict[str, Any]:
    return {
        "level1": [],
        "level2": [],
        "cities": [],
        "all_cities": False,
        "admin_regions": [],
        "selected_departments": [],
        "selected_cities": [],
    }


def france_geo_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    regions, departments = resolve_multi_geo_from_profile(profile)
    cities = resolve_selected_cities(profile)
    return {
        "level1": list(regions),
        "level2": [d.get("name") or d.get("code", "") for d in departments],
        "cities": list(cities),
        "all_cities": profile_all_cities(profile),
        "admin_regions": list(regions),
        "selected_departments": list(departments),
        "selected_cities": list(cities),
    }


def merge_profile_geo(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build full geo_by_country map from DB fields."""
    geo = parse_geo_by_country(profile.get("geo_by_country"))
    countries = profile_countries(profile)
    for country in countries:
        if country == "France" and not geo.get("France"):
            geo["France"] = france_geo_from_profile(profile)
        geo.setdefault(country, _empty_country_geo())
    if "France" in countries and "France" in geo:
        fr = geo["France"]
        if not fr.get("admin_regions"):
            geo["France"] = france_geo_from_profile(profile)
    return geo


def profile_countries(profile: dict[str, Any]) -> list[str]:
    selected = parse_selected_countries(
        profile.get("selected_countries"),
        fallback_country=profile.get("country", "France"),
    )
    return selected


def profile_primary_country(profile: dict[str, Any]) -> str:
    countries = profile_countries(profile)
    return countries[0] if countries else "France"


def get_country_geo(profile: dict[str, Any], country: str) -> dict[str, Any]:
    country = normalize_country_name(country)
    geo_map = merge_profile_geo(profile)
    return geo_map.get(country, _empty_country_geo())


def validate_country_geo(country: str, geo: dict[str, Any]) -> tuple[bool, str]:
    country = normalize_country_name(country)
    schema = country_geo_schema(country)

    if country == "France":
        regions = geo.get("admin_regions") or geo.get("level1") or []
        departments = geo.get("selected_departments") or []
        if not regions:
            return False, t("geo.select_region", country=country)
        if not departments:
            return False, t("geo.select_department", country=country)
        if not geo.get("all_cities") and not (geo.get("selected_cities") or geo.get("cities")):
            return False, t("geo.select_city", country=country)
        return True, ""

    level1 = geo.get("level1") or []
    level2 = geo.get("level2") or []
    cities = geo.get("cities") or []
    if geo.get("all_cities"):
        if schema:
            if not level1 and not level2:
                label = schema.get("level1_label", "Zone")
                return False, t("geo.select_zone", country=country, zone=label.lower())
            return True, ""
        return True, ""

    if schema:
        if not level1 and not cities:
            label = schema.get("level1_label", "Zone")
            return False, t("geo.select_zone_or_city", country=country, zone=label.lower())
        if not level1 and not level2 and not cities:
            return False, t("geo.select_city_only", country=country)
        return True, ""

    if not cities:
        return False, t("geo.select_city_only", country=country)
    return True, ""


def validate_profile_countries_geo(
    countries: list[str],
    geo_by_country: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    if not countries:
        return False, t("geo.select_countries")
    for country in countries:
        ok, msg = validate_country_geo(country, geo_by_country.get(country, {}))
        if not ok:
            return False, msg
    return True, ""


def sync_france_legacy_fields(
    profile: dict[str, Any],
    france_geo: dict[str, Any],
) -> dict[str, Any]:
    """Copy France geo into legacy profile keys for backward compatibility."""
    regions = france_geo.get("admin_regions") or france_geo.get("level1") or []
    departments = france_geo.get("selected_departments") or []
    cities = france_geo.get("selected_cities") or france_geo.get("cities") or []
    all_cities = bool(france_geo.get("all_cities"))
    profile = dict(profile)
    profile["admin_regions"] = list(regions)
    profile["selected_departments"] = list(departments)
    profile["selected_cities"] = list(cities) if not all_cities else []
    profile["all_cities"] = all_cities
    if regions:
        profile["admin_region"] = regions[0]
        profile["region"] = regions[0]
    if departments:
        profile["department_code"] = departments[0].get("code", "")
        profile["department_name"] = departments[0].get("name", "")
    if cities and not all_cities:
        profile["home_city"] = cities[0]
    return profile


def format_countries_summary(profile: dict[str, Any]) -> str:
    countries = profile_countries(profile)
    if len(countries) == 1:
        return countries[0]
    if len(countries) <= 3:
        return ", ".join(countries)
    return f"{', '.join(countries[:2])} (+{len(countries) - 2})"
