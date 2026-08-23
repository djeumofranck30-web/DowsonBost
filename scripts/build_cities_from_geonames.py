"""Build data/world_cities from GeoNames cities5000 (reliable, offline)."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from io import TextIOWrapper
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "world_cities"
GEONAMES_DIR = ROOT / "data" / "geonames"
CITIES5000_URL = "https://download.geonames.org/export/dump/cities5000.zip"
ADMIN1_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
ALIASES_DEST = ROOT / "data" / "country_location_aliases.json"

sys.path.insert(0, str(ROOT))

from world_geo import (  # noqa: E402
    COUNTRY_CODE_TO_NAME,
    COUNTRY_GEO_SCHEMA,
    COUNTRY_NAME_TO_CODE,
    ISO_COUNTRIES,
    normalize_country_name,
)
from world_cities import LEVEL1_OSM_ALIASES  # noqa: E402


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().casefold())


def _zone_slug(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:120] or "zone"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return
    print(f"Downloading {url}…")
    response = requests.get(url, timeout=120, headers={"User-Agent": "DowsonBost/1.0"})
    response.raise_for_status()
    dest.write_bytes(response.content)


def _load_admin1_names() -> dict[tuple[str, str], str]:
    """Map (country_code, admin1_code) -> admin1 display name."""
    path = GEONAMES_DIR / "admin1CodesASCII.txt"
    _download(ADMIN1_URL, path)
    mapping: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            code_parts = parts[0].split(".")
            if len(code_parts) != 2:
                continue
            cc, admin1 = code_parts[0].upper(), code_parts[1]
            name = parts[1].strip() or parts[2].strip()
            if name:
                mapping[(cc, admin1)] = name
    return mapping


def _load_cities(
    admin1_names: dict[tuple[str, str], str],
) -> tuple[dict[str, set[str]], dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    """Parse cities5000.zip into country and zone groupings."""
    zip_path = GEONAMES_DIR / "cities5000.zip"
    _download(CITIES5000_URL, zip_path)

    by_country: dict[str, set[str]] = defaultdict(set)
    by_admin1_code: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_admin1_name: dict[tuple[str, str], set[str]] = defaultdict(set)

    with zipfile.ZipFile(zip_path) as archive:
        member = next(name for name in archive.namelist() if name.endswith(".txt"))
        with archive.open(member) as raw:
            handle = TextIOWrapper(raw, encoding="utf-8", errors="replace")
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 11:
                    continue
                name = parts[1].strip() or parts[2].strip()
                cc = parts[8].strip().upper()
                admin1 = parts[10].strip()
                if not name or not cc:
                    continue
                by_country[cc].add(name)
                if admin1:
                    by_admin1_code[(cc, admin1)].add(name)
                    admin_name = admin1_names.get((cc, admin1), "")
                    if admin_name:
                        by_admin1_name[(cc, _normalize_key(admin_name))].add(name)
    return by_country, by_admin1_code, by_admin1_name


def _zone_name_variants(zone: str) -> set[str]:
    keys = {_normalize_key(zone)}
    for alias in LEVEL1_OSM_ALIASES.get(zone, ()):
        keys.add(_normalize_key(alias))
    return keys


def _cities_for_zone_option(
    country_code: str,
    zone: str,
    by_admin1_name: dict[tuple[str, str], set[str]],
    by_country: dict[str, set[str]],
) -> list[str]:
    cc = country_code.upper()
    collected: set[str] = set()
    for key in _zone_name_variants(zone):
        collected.update(by_admin1_name.get((cc, key), set()))
    if collected:
        return sorted(collected, key=str.casefold)
    # Partial match on admin1 names (e.g. "New York" state)
    for (code, name_key), cities in by_admin1_name.items():
        if code != cc:
            continue
        for variant in _zone_name_variants(zone):
            if variant in name_key or name_key in variant:
                collected.update(cities)
    if collected:
        return sorted(collected, key=str.casefold)
    return sorted(by_country.get(cc, set()), key=str.casefold)[:200]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_country_location_aliases() -> None:
    path = GEONAMES_DIR / "countryInfo.txt"
    _download(COUNTRY_INFO_URL, path)
    aliases: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            code = parts[0].strip().upper()
            english = parts[4].strip()
            french = COUNTRY_CODE_TO_NAME.get(code, "")
            names: list[str] = []
            for item in (french, english, parts[1].strip() if len(parts) > 1 else ""):
                if item and item not in names:
                    names.append(item)
            if names:
                aliases[code] = names
    ALIASES_DEST.parent.mkdir(parents=True, exist_ok=True)
    with ALIASES_DEST.open("w", encoding="utf-8") as handle:
        json.dump(aliases, handle, ensure_ascii=False, indent=2)


def main() -> None:
    _write_country_location_aliases()
    admin1_names = _load_admin1_names()
    by_country, by_admin1_code, by_admin1_name = _load_cities(admin1_names)

    country_codes = {item["code"].upper() for item in ISO_COUNTRIES}
    schema_country_codes = {
        (
            COUNTRY_GEO_SCHEMA[name].get("code")
            or COUNTRY_NAME_TO_CODE.get(normalize_country_name(name), "")
        ).upper()
        for name in COUNTRY_GEO_SCHEMA
        if name != "France"
    }
    written_countries = 0
    written_zones = 0
    written_manifests = 0

    for code in sorted(country_codes):
        cities = sorted(by_country.get(code, set()), key=str.casefold)
        if not cities:
            continue
        country_name = COUNTRY_CODE_TO_NAME.get(code, code)
        _write_json(
            DEST / f"{code}.json",
            {"country": country_name, "code": code, "source": "geonames_cities5000", "cities": cities},
        )
        written_countries += 1

    for country_name, schema in COUNTRY_GEO_SCHEMA.items():
        if country_name == "France":
            continue
        code = schema.get("code") or COUNTRY_NAME_TO_CODE.get(normalize_country_name(country_name), "")
        if not code:
            continue
        code = code.upper()
        zones_dir = DEST / code / "zones"
        for zone in schema.get("level1_options") or []:
            zone_cities = _cities_for_zone_option(code, zone, by_admin1_name, by_country)
            if not zone_cities:
                continue
            _write_json(
                zones_dir / f"{_zone_slug(zone)}.json",
                {
                    "country": country_name,
                    "code": code,
                    "zone": zone,
                    "source": "geonames_cities5000",
                    "cities": zone_cities,
                },
            )
            written_zones += 1

    for code in sorted(country_codes):
        if code in schema_country_codes:
            continue
        country_name = COUNTRY_CODE_TO_NAME.get(code, code)
        zones_dir = DEST / code / "zones"
        regions: list[str] = []
        for (cc, admin1_code), admin_name in sorted(admin1_names.items()):
            if cc != code:
                continue
            zone_cities = sorted(by_admin1_code.get((cc, admin1_code), set()), key=str.casefold)
            if not zone_cities:
                continue
            _write_json(
                zones_dir / f"{_zone_slug(admin_name)}.json",
                {
                    "country": country_name,
                    "code": code,
                    "zone": admin_name,
                    "source": "geonames_cities5000",
                    "cities": zone_cities,
                },
            )
            written_zones += 1
            regions.append(admin_name)
        unique_regions = sorted(set(regions), key=str.casefold)
        if len(unique_regions) >= 2:
            _write_json(
                DEST / code / "manifest.json",
                {
                    "country": country_name,
                    "code": code,
                    "level1_label": "Régions",
                    "city_label": "Villes",
                    "level1_options": unique_regions,
                    "source": "geonames_admin1",
                },
            )
            written_manifests += 1

    print(
        f"Wrote {written_countries} country files, {written_zones} zone files, "
        f"and {written_manifests} manifests to {DEST}"
    )


if __name__ == "__main__":
    main()
