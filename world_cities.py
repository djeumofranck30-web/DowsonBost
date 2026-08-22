"""City lists for international countries (OpenStreetMap / Overpass, cached)."""

from __future__ import annotations

import functools
import re
from typing import Any

import requests

from world_geo import COUNTRY_NAME_TO_CODE, normalize_country_name

_HTTP_HEADERS = {"User-Agent": "DowsonBost/1.0 (job-matching)"}
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_MAX_CITIES = 600
_PLACE_TYPES = ("city", "town", "village")

# French UI labels -> OSM area name variants
LEVEL1_OSM_ALIASES: dict[str, tuple[str, ...]] = {
    "Quebec": ("Québec",),
    "Catalogne": ("Catalunya", "Catalonia"),
    "Andalousie": ("Andalucía", "Andalusia"),
    "Pays basque": ("Euskadi", "Basque Country"),
    "Castille-et-León": ("Castilla y León",),
    "Castille-La Manche": ("Castilla-La Mancha",),
    "Baleares": ("Illes Balears", "Balearic Islands"),
    "Canaries": ("Canarias", "Canary Islands"),
    "Wallonie": ("Wallonia",),
    "Flandre": ("Vlaanderen", "Flanders"),
    "Bruxelles-Capitale": ("Bruxelles", "Brussels"),
    "Lombardie": ("Lombardia",),
    "Latium": ("Lazio",),
    "Campanie": ("Campania",),
    "Vénétie": ("Veneto",),
    "Sicile": ("Sicilia", "Sicily"),
    "Piémont": ("Piemonte", "Piedmont"),
    "Émilie-Romagne": ("Emilia-Romagna",),
    "Toscane": ("Toscana", "Tuscany"),
    "Pouilles": ("Puglia", "Apulia"),
    "Marches": ("Marche",),
    "Sardaigne": ("Sardegna", "Sardinia"),
    "Bavière": ("Bayern", "Bavaria"),
    "Rhinland-Pfalz": ("Rheinland-Pfalz",),
    "Nordrhein-Westfalen": ("North Rhine-Westphalia",),
}


def _area_name_variants(name: str) -> tuple[str, ...]:
    cleaned = name.strip()
    if not cleaned:
        return ()
    variants = [cleaned]
    aliases = LEVEL1_OSM_ALIASES.get(cleaned, ())
    for alias in aliases:
        if alias not in variants:
            variants.append(alias)
    return tuple(variants)


def _run_overpass(query: str) -> list[dict[str, Any]]:
    try:
        response = requests.post(
            _OVERPASS_URL,
            data={"data": query},
            headers=_HTTP_HEADERS,
            timeout=120,
        )
        if not response.ok:
            return []
        payload = response.json()
        return payload.get("elements") or []
    except (requests.RequestException, ValueError, TypeError):
        return []


def _names_from_elements(elements: list[dict[str, Any]]) -> tuple[str, ...]:
    names = {
        str(item.get("tags", {}).get("name", "")).strip()
        for item in elements
        if item.get("tags", {}).get("name")
    }
    return tuple(sorted(names, key=str.casefold))


@functools.lru_cache(maxsize=512)
def _fetch_cities_overpass_country(country_code: str, limit: int = _MAX_CITIES) -> tuple[str, ...]:
    code = country_code.strip().upper()
    if not code:
        return ()
    query = f"""
[out:json][timeout:90];
area["ISO3166-1"="{code}"][admin_level=2]->.country;
(
  node["place"~"city|town|village"](area.country);
);
out tags {limit};
"""
    return _names_from_elements(_run_overpass(query))


@functools.lru_cache(maxsize=512)
def _fetch_cities_overpass_zone(
    country_code: str,
    zone_name: str,
    level2: str = "",
    limit: int = _MAX_CITIES,
) -> tuple[str, ...]:
    code = country_code.strip().upper()
    zone = zone_name.strip()
    if not code or not zone:
        return ()

    level2 = level2.strip()
    best: tuple[str, ...] = ()
    for variant in _area_name_variants(zone):
        for tag in ("name", "name:fr", "name:en", "name:nl", "name:de", "name:es", "name:it"):
            if level2:
                query = f"""
[out:json][timeout:90];
area["ISO3166-1"="{code}"][admin_level=2]->.country;
(
  area["{tag}"="{variant}"](area.country)->.parent;
  area["name"~"{level2}",i](area.parent)->.zone;
);
(
  node["place"~"city|town|village"](area.zone);
);
out tags {limit};
"""
            else:
                query = f"""
[out:json][timeout:90];
area["ISO3166-1"="{code}"][admin_level=2]->.country;
(
  area["{tag}"="{variant}"](area.country);
)->.zones;
(
  node["place"~"city|town|village"](area.zones);
);
out tags {limit};
"""
            names = _names_from_elements(_run_overpass(query))
            if len(names) > len(best):
                best = names
            if len(best) >= 20:
                return best[:limit]
    return best[:limit]


@functools.lru_cache(maxsize=512)
def _fetch_cities_nominatim_zone(
    country_code: str,
    zone_name: str,
    level2: str = "",
) -> tuple[str, ...]:
    """Fallback when Overpass returns few results."""
    code = country_code.strip().lower()
    parts = [part.strip() for part in (level2, zone_name) if part.strip()]
    if not parts:
        return ()
    query = ", ".join(parts)
    try:
        response = requests.get(
            _NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": code,
            },
            headers=_HTTP_HEADERS,
            timeout=25,
        )
        if not response.ok:
            return ()
        geocode = response.json()
        if not geocode:
            return ()
        bbox = geocode[0].get("boundingbox")
        if not bbox or len(bbox) != 4:
            return ()
        viewbox = f"{bbox[2]},{bbox[3]},{bbox[0]},{bbox[1]}"
        names: set[str] = set()
        for feature in _PLACE_TYPES:
            place_response = requests.get(
                _NOMINATIM_URL,
                params={
                    "format": "json",
                    "limit": 50,
                    "featuretype": feature,
                    "viewbox": viewbox,
                    "bounded": 1,
                    "countrycodes": code,
                },
                headers=_HTTP_HEADERS,
                timeout=25,
            )
            if not place_response.ok:
                continue
            payload = place_response.json()
            if not isinstance(payload, list):
                continue
            for item in payload:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if name:
                        names.add(name)
        return tuple(sorted(names, key=str.casefold))
    except (requests.RequestException, ValueError, TypeError):
        return ()


def fetch_cities_for_zone(
    country: str,
    level1: str = "",
    level2: str = "",
) -> tuple[str, ...]:
    """Return sorted city names for a country zone (cached)."""
    country = normalize_country_name(country)
    code = COUNTRY_NAME_TO_CODE.get(country, "")
    if not code:
        return ()

    if level1.strip() or level2.strip():
        names = _fetch_cities_overpass_zone(code, level1, level2)
        if len(names) < 5:
            names = _fetch_cities_nominatim_zone(code, level1, level2) or names
        return names

    names = _fetch_cities_overpass_country(code)
    if len(names) < 5:
        names = _fetch_cities_nominatim_zone(code, country, "")
    return names


def city_options_for_country_zone(
    country: str,
    level1: list[str],
    level2: list[str] | None = None,
) -> list[str]:
    """Build multiselect labels for all cities in selected zones."""
    level2 = level2 or []
    zones = [z.strip() for z in level1 if z.strip()]
    subdiv2 = [z.strip() for z in level2 if z.strip()]
    if not zones and not subdiv2:
        return list(fetch_cities_for_zone(country))

    multi_zone = len(zones) > 1
    options: list[str] = []
    seen: set[str] = set()

    if zones:
        for zone in zones:
            if subdiv2:
                for sub in subdiv2:
                    for name in fetch_cities_for_zone(country, zone, sub):
                        label = format_intl_city_option(name, zone, multi_zone, sub)
                        if label not in seen:
                            seen.add(label)
                            options.append(label)
            else:
                for name in fetch_cities_for_zone(country, zone):
                    label = format_intl_city_option(name, zone, multi_zone)
                    if label not in seen:
                        seen.add(label)
                        options.append(label)
    else:
        for sub in subdiv2:
            for name in fetch_cities_for_zone(country, "", sub):
                label = format_intl_city_option(name, sub, len(subdiv2) > 1)
                if label not in seen:
                    seen.add(label)
                    options.append(label)

    return sorted(options, key=str.casefold)


def format_intl_city_option(
    city_name: str,
    zone: str,
    multi_zone: bool,
    level2: str = "",
) -> str:
    suffix = level2 or zone
    if multi_zone and suffix:
        return f"{city_name} ({suffix})"
    return city_name


def parse_intl_city_option(label: str) -> str:
    label = label.strip()
    match = re.match(r"^(.+?) \((.+)\)$", label)
    if match:
        return match.group(1).strip()
    return label


def labels_for_selected_intl_cities(
    cities: list[str],
    level1: list[str],
    level2: list[str],
    available_options: list[str],
) -> list[str]:
    if not cities or not available_options:
        return []
    multi_zone = len([z for z in level1 if z.strip()]) > 1
    option_set = set(available_options)
    labels: list[str] = []
    for city in cities:
        matched = False
        for zone in level1:
            for sub in level2 or [""]:
                label = format_intl_city_option(city, zone, multi_zone, sub)
                if label in option_set:
                    labels.append(label)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            for zone in level1:
                label = format_intl_city_option(city, zone, multi_zone)
                if label in option_set:
                    labels.append(label)
                    matched = True
                    break
        if not matched and city in option_set:
            labels.append(city)
    return list(dict.fromkeys(labels))


def country_geo_all_cities(geo: dict[str, Any]) -> bool:
    value = geo.get("all_cities", False)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def country_geo_cities(geo: dict[str, Any]) -> list[str]:
    if country_geo_all_cities(geo):
        return []
    return [str(c).strip() for c in (geo.get("cities") or geo.get("selected_cities") or []) if str(c).strip()]
