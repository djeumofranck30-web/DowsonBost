"""Verify bundled city/region data for all ISO countries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from world_cities import (  # noqa: E402
    _load_bundled_country_cities,
    _load_bundled_zone_cities,
    fetch_cities_for_zone,
)
from world_geo import (  # noqa: E402
    COUNTRY_GEO_SCHEMA,
    ISO_COUNTRIES,
    country_geo_schema,
    normalize_country_name,
)

DATA_DIR = ROOT / "data" / "world_cities"


def main() -> int:
    issues: list[str] = []
    stats = {
        "total": len(ISO_COUNTRIES),
        "with_country_cities": 0,
        "with_schema": 0,
        "hardcoded_schema": 0,
        "dynamic_schema": 0,
        "schema_zone_ok": 0,
        "schema_zone_fail": 0,
        "no_schema_country_ok": 0,
        "no_schema_country_fail": 0,
        "no_data": 0,
    }

    for entry in ISO_COUNTRIES:
        name = entry["name"]
        code = entry["code"].upper()
        country_file = DATA_DIR / f"{code}.json"
        bundled = _load_bundled_country_cities(code)
        schema = country_geo_schema(name)

        if bundled:
            stats["with_country_cities"] += 1
        elif name != "France":
            stats["no_data"] += 1
            issues.append(f"{name} ({code}): no country city file or empty list")

        if not schema or name == "France":
            if name == "France":
                continue
            if not schema:
                if bundled:
                    stats["no_schema_country_ok"] += 1
                    fetched = fetch_cities_for_zone(name)
                    if not fetched:
                        stats["no_schema_country_fail"] += 1
                        issues.append(f"{name} ({code}): country-level fetch returned 0 cities")
                continue

        stats["with_schema"] += 1
        if name in COUNTRY_GEO_SCHEMA and name != "France":
            stats["hardcoded_schema"] += 1
        else:
            stats["dynamic_schema"] += 1

        options = schema.get("level1_options") or []
        if not options:
            issues.append(f"{name} ({code}): schema without level1_options")
            continue

        manifest_path = DATA_DIR / code / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_opts = manifest.get("level1_options") or []
                if set(manifest_opts) != set(options):
                    issues.append(
                        f"{name} ({code}): manifest options mismatch "
                        f"(manifest={len(manifest_opts)}, schema={len(options)})"
                    )
            except (OSError, json.JSONDecodeError) as exc:
                issues.append(f"{name} ({code}): invalid manifest — {exc}")

        failed_zones: list[str] = []
        for zone in options:
            zone_cities = _load_bundled_zone_cities(code, zone)
            if not zone_cities:
                zone_cities = fetch_cities_for_zone(name, zone)
            if not zone_cities:
                failed_zones.append(zone)

        if failed_zones:
            stats["schema_zone_fail"] += 1
            sample = ", ".join(failed_zones[:3])
            suffix = f" (+{len(failed_zones) - 3} more)" if len(failed_zones) > 3 else ""
            issues.append(
                f"{name} ({code}): {len(failed_zones)}/{len(options)} zones without cities "
                f"[{sample}{suffix}]"
            )
        else:
            stats["schema_zone_ok"] += 1

    print("=== World cities verification ===")
    print(f"Countries in ISO list:        {stats['total']}")
    print(f"With country city file:       {stats['with_country_cities']}")
    print(f"No city data (non-France):    {stats['no_data']}")
    print(f"With region schema:           {stats['with_schema']}")
    print(f"  hardcoded schema:           {stats['hardcoded_schema']}")
    print(f"  dynamic (GeoNames) schema:  {stats['dynamic_schema']}")
    print(f"Schema countries all zones OK:{stats['schema_zone_ok']}")
    print(f"Schema countries zone issues: {stats['schema_zone_fail']}")
    print(f"No-schema countries OK:       {stats['no_schema_country_ok']}")
    print(f"No-schema countries failed:   {stats['no_schema_country_fail']}")
    print()

    if issues:
        print(f"ISSUES ({len(issues)}):")
        for item in issues[:80]:
            print(f"  - {item}")
        if len(issues) > 80:
            print(f"  ... and {len(issues) - 80} more")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
