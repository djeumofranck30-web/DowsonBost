"""French administrative regions and departments for profile location selectors."""

from __future__ import annotations

import functools
import json
import re
from typing import Any

import requests

FRANCE_REGIONS: dict[str, list[tuple[str, str]]] = {
    "Île-de-France": [
        ("75", "Paris"),
        ("77", "Seine-et-Marne"),
        ("78", "Yvelines"),
        ("91", "Essonne"),
        ("92", "Hauts-de-Seine"),
        ("93", "Seine-Saint-Denis"),
        ("94", "Val-de-Marne"),
        ("95", "Val-d'Oise"),
    ],
    "Hauts-de-France": [
        ("02", "Aisne"),
        ("59", "Nord"),
        ("60", "Oise"),
        ("62", "Pas-de-Calais"),
        ("80", "Somme"),
    ],
    "Normandie": [
        ("14", "Calvados"),
        ("27", "Eure"),
        ("50", "Manche"),
        ("61", "Orne"),
        ("76", "Seine-Maritime"),
    ],
    "Grand Est": [
        ("08", "Ardennes"),
        ("10", "Aube"),
        ("51", "Marne"),
        ("52", "Haute-Marne"),
        ("54", "Meurthe-et-Moselle"),
        ("55", "Meuse"),
        ("57", "Moselle"),
        ("67", "Bas-Rhin"),
        ("68", "Haut-Rhin"),
        ("88", "Vosges"),
    ],
    "Bretagne": [
        ("22", "Côtes-d'Armor"),
        ("29", "Finistère"),
        ("35", "Ille-et-Vilaine"),
        ("56", "Morbihan"),
    ],
    "Pays de la Loire": [
        ("44", "Loire-Atlantique"),
        ("49", "Maine-et-Loire"),
        ("53", "Mayenne"),
        ("72", "Sarthe"),
        ("85", "Vendée"),
    ],
    "Centre-Val de Loire": [
        ("18", "Cher"),
        ("28", "Eure-et-Loir"),
        ("36", "Indre"),
        ("37", "Indre-et-Loire"),
        ("41", "Loir-et-Cher"),
        ("45", "Loiret"),
    ],
    "Bourgogne-Franche-Comté": [
        ("21", "Côte-d'Or"),
        ("25", "Doubs"),
        ("39", "Jura"),
        ("58", "Nièvre"),
        ("70", "Haute-Saône"),
        ("71", "Saône-et-Loire"),
        ("89", "Yonne"),
        ("90", "Territoire de Belfort"),
    ],
    "Auvergne-Rhône-Alpes": [
        ("01", "Ain"),
        ("03", "Allier"),
        ("07", "Ardèche"),
        ("15", "Cantal"),
        ("26", "Drôme"),
        ("38", "Isère"),
        ("42", "Loire"),
        ("43", "Haute-Loire"),
        ("63", "Puy-de-Dôme"),
        ("69", "Rhône"),
        ("73", "Savoie"),
        ("74", "Haute-Savoie"),
    ],
    "Nouvelle-Aquitaine": [
        ("16", "Charente"),
        ("17", "Charente-Maritime"),
        ("19", "Corrèze"),
        ("23", "Creuse"),
        ("24", "Dordogne"),
        ("33", "Gironde"),
        ("40", "Landes"),
        ("47", "Lot-et-Garonne"),
        ("64", "Pyrénées-Atlantiques"),
        ("79", "Deux-Sèvres"),
        ("86", "Vienne"),
        ("87", "Haute-Vienne"),
    ],
    "Occitanie": [
        ("09", "Ariège"),
        ("11", "Aude"),
        ("12", "Aveyron"),
        ("30", "Gard"),
        ("31", "Haute-Garonne"),
        ("32", "Gers"),
        ("34", "Hérault"),
        ("46", "Lot"),
        ("48", "Lozère"),
        ("65", "Hautes-Pyrénées"),
        ("66", "Pyrénées-Orientales"),
        ("81", "Tarn"),
        ("82", "Tarn-et-Garonne"),
    ],
    "Provence-Alpes-Côte d'Azur": [
        ("04", "Alpes-de-Haute-Provence"),
        ("05", "Hautes-Alpes"),
        ("06", "Alpes-Maritimes"),
        ("13", "Bouches-du-Rhône"),
        ("83", "Var"),
        ("84", "Vaucluse"),
    ],
    "Corse": [
        ("2A", "Corse-du-Sud"),
        ("2B", "Haute-Corse"),
    ],
}


def get_region_names() -> list[str]:
    return list(FRANCE_REGIONS.keys())


def get_departments(region_name: str) -> list[tuple[str, str]]:
    return list(FRANCE_REGIONS.get(region_name, []))


def format_department_label(code: str, name: str) -> str:
    return f"{name} ({code})"


def parse_department_label(label: str) -> tuple[str, str]:
    """Parse 'Val-de-Marne (94)' -> ('94', 'Val-de-Marne')."""
    label = label.strip()
    if "(" in label and label.endswith(")"):
        name, code_part = label.rsplit("(", 1)
        return code_part.rstrip(")").strip(), name.strip()
    return "", label


def find_region_for_department_code(code: str) -> str:
    for region, departments in FRANCE_REGIONS.items():
        for dept_code, _ in departments:
            if dept_code == code:
                return region
    return ""


def department_labels_for_region(region_name: str) -> list[str]:
    return [
        format_department_label(code, name)
        for code, name in get_departments(region_name)
    ]


def resolve_department_selection(
    admin_region: str,
    department_code: str,
    department_name: str,
) -> tuple[str, str]:
    """Return (region, department_label) from stored profile values."""
    region = admin_region.strip()
    if not region and department_code:
        region = find_region_for_department_code(department_code)

    if not region:
        region = get_region_names()[0]

    labels = department_labels_for_region(region)
    if department_code and department_name:
        target = format_department_label(department_code, department_name)
        if target in labels:
            return region, target

    if department_code:
        for label in labels:
            code, _ = parse_department_label(label)
            if code == department_code:
                return region, label

    return region, labels[0] if labels else ""


def parse_admin_regions(raw: Any) -> list[str]:
    """Parse region list from JSON string or list."""
    if isinstance(raw, list):
        return [str(r).strip() for r in raw if str(r).strip()]
    if not raw:
        return []
    text = str(raw).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(r).strip() for r in parsed if str(r).strip()]
    except json.JSONDecodeError:
        pass
    if text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def serialize_admin_regions(regions: list[str]) -> str:
    return json.dumps([r for r in regions if r], ensure_ascii=False)


def parse_selected_departments(raw: Any) -> list[dict[str, str]]:
    """Parse department selections from JSON."""
    if isinstance(raw, list):
        items = raw
    elif not raw:
        return []
    else:
        text = str(raw).strip()
        try:
            parsed = json.loads(text)
            items = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    departments: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            code = str(item.get("code", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            region = str(item.get("region", "")).strip()
            if not region and code:
                region = find_region_for_department_code(code)
            if code:
                departments.append({"code": code, "name": name, "region": region})
        elif isinstance(item, str) and item.strip():
            code, name = parse_department_label(item.strip())
            region = find_region_for_department_code(code) if code else ""
            if code:
                departments.append({"code": code, "name": name, "region": region})
    return departments


def serialize_selected_departments(departments: list[dict[str, str]]) -> str:
    cleaned = []
    for dept in departments:
        code = str(dept.get("code", "")).strip().upper()
        if not code:
            continue
        name = str(dept.get("name", "")).strip()
        region = str(dept.get("region", "")).strip() or find_region_for_department_code(code)
        cleaned.append({"code": code, "name": name, "region": region})
    return json.dumps(cleaned, ensure_ascii=False)


def resolve_multi_geo_from_profile(profile: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    """Return (regions, departments) from profile, including legacy single fields."""
    regions = parse_admin_regions(profile.get("admin_regions"))
    departments = parse_selected_departments(profile.get("selected_departments"))

    if not regions:
        legacy_region = str(
            profile.get("admin_region") or profile.get("region", "")
        ).strip()
        if legacy_region:
            regions = [legacy_region]

    if not departments:
        code = str(profile.get("department_code", "")).strip().upper()
        name = str(profile.get("department_name", "")).strip()
        if code:
            region = regions[0] if regions else find_region_for_department_code(code)
            departments = [{"code": code, "name": name, "region": region}]

    return regions, departments


def department_labels_for_regions(region_names: list[str]) -> list[str]:
    """Labels for departments across multiple regions (with region suffix)."""
    labels: list[str] = []
    multi = len(region_names) > 1
    for region in region_names:
        for code, name in get_departments(region):
            label = format_department_label(code, name)
            labels.append(f"{label} — {region}" if multi else label)
    return labels


def department_from_multiselect_label(label: str) -> dict[str, str]:
    """Parse multiselect label into department dict."""
    label = label.strip()
    if " — " in label:
        dept_part, region = label.rsplit(" — ", 1)
        code, name = parse_department_label(dept_part)
        return {"code": code, "name": name, "region": region.strip()}
    code, name = parse_department_label(label)
    region = find_region_for_department_code(code) if code else ""
    return {"code": code, "name": name, "region": region}


def labels_for_selected_departments(
    departments: list[dict[str, str]],
    selected_regions: list[str],
) -> list[str]:
    """Convert stored departments to multiselect labels."""
    multi = len(selected_regions) > 1
    labels: list[str] = []
    for dept in departments:
        code = dept.get("code", "")
        name = dept.get("name", "")
        region = dept.get("region") or find_region_for_department_code(code)
        label = format_department_label(code, name)
        labels.append(f"{label} — {region}" if multi else label)
    return labels


def parse_selected_cities(raw: Any) -> list[str]:
    """Parse city list from JSON string, list, or newline/comma-separated text."""
    if isinstance(raw, list):
        items = raw
    elif not raw:
        return []
    else:
        text = str(raw).strip()
        try:
            parsed = json.loads(text)
            items = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            items = []
            if text:
                for part in re.split(r"[\n,;]+", text):
                    part = " ".join(part.strip().split())
                    if part:
                        items.append(part)

    cities: list[str] = []
    seen: set[str] = set()
    for item in items:
        city = " ".join(str(item).strip().split())
        key = city.lower()
        if city and key not in seen:
            seen.add(key)
            cities.append(city)
    return cities


def serialize_selected_cities(cities: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for city in cities:
        normalized = " ".join(str(city).strip().split())
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            cleaned.append(normalized)
    return json.dumps(cleaned, ensure_ascii=False)


def resolve_selected_cities(profile: dict[str, Any]) -> list[str]:
    """Return target cities from profile, including legacy home_city."""
    if profile_all_cities(profile):
        return []
    cities = parse_selected_cities(profile.get("selected_cities"))
    if cities:
        return cities
    home = str(profile.get("home_city", "")).strip()
    return [home] if home else []


def profile_all_cities(profile: dict[str, Any]) -> bool:
    """True when user accepts any city within selected departments."""
    value = profile.get("all_cities", False)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def cities_to_text(cities: list[str]) -> str:
    return "\n".join(cities)


def communes_supported_for_country(country: str) -> bool:
    return (country or "France").strip().lower() in ("france", "fr")


@functools.lru_cache(maxsize=128)
def fetch_commune_names(department_code: str) -> tuple[str, ...]:
    """Fetch commune names for a French department (geo.api.gouv.fr)."""
    code = department_code.strip().upper()
    if not code:
        return ()
    try:
        response = requests.get(
            f"https://geo.api.gouv.fr/departements/{code}/communes",
            params={"fields": "nom", "limit": 600},
            headers={"User-Agent": "DowsonBost/1.0 (job-matching)"},
            timeout=20,
        )
        if not response.ok:
            return ()
        names = sorted(
            {
                str(item.get("nom", "")).strip()
                for item in response.json()
                if item.get("nom")
            },
            key=str.casefold,
        )
        return tuple(names)
    except (requests.RequestException, ValueError, TypeError):
        return ()


def format_city_option(city_name: str, dept_code: str, multi_dept: bool) -> str:
    if multi_dept and dept_code:
        return f"{city_name} ({dept_code})"
    return city_name


def parse_city_option(label: str) -> str:
    """Parse multiselect label 'Lyon (69)' -> 'Lyon'."""
    label = label.strip()
    match = re.match(r"^(.+?) \((\d{2,3}|2[AB])\)$", label)
    if match:
        return match.group(1).strip()
    return label


def city_options_for_departments(departments: list[dict[str, str]]) -> list[str]:
    """Build sorted multiselect labels for all communes in selected departments."""
    if not departments:
        return []
    dept_codes = {str(d.get("code", "")).strip().upper() for d in departments if d.get("code")}
    multi = len(dept_codes) > 1
    options: list[str] = []
    seen: set[str] = set()
    for dept in sorted(departments, key=lambda d: str(d.get("code", ""))):
        code = str(dept.get("code", "")).strip().upper()
        if not code:
            continue
        for name in fetch_commune_names(code):
            label = format_city_option(name, code, multi)
            if label not in seen:
                seen.add(label)
                options.append(label)
    return sorted(options, key=str.casefold)


def labels_for_selected_cities(
    cities: list[str],
    departments: list[dict[str, str]],
    available_options: list[str],
) -> list[str]:
    """Map stored city names to multiselect option labels."""
    if not cities or not available_options:
        return []
    multi = len({d.get("code") for d in departments if d.get("code")}) > 1
    option_set = set(available_options)
    labels: list[str] = []
    for city in cities:
        matched = False
        for dept in departments:
            code = str(dept.get("code", "")).strip().upper()
            label = format_city_option(city, code, multi)
            if label in option_set:
                labels.append(label)
                matched = True
                break
        if not matched and city in option_set:
            labels.append(city)
    return list(dict.fromkeys(labels))
