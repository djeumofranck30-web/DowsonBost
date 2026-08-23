"""Verify job search + geo filtering follow profile countries and zones."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_filters import (  # noqa: E402
    apply_strict_job_filters,
    build_country_search_locations,
    build_profile_search_locations,
    job_matches_country,
    job_matches_geography,
)
from world_geo import (  # noqa: E402
    ISO_COUNTRIES,
    country_geo_schema,
    merge_profile_geo,
    profile_countries,
    validate_profile_countries_geo,
)


def _profile(countries: list[str], geo_by_country: dict) -> dict:
    profile = {
        "target_job_title": "Developpeur",
        "contract_type": "CDI",
        "selected_countries": countries,
        "geo_by_country": geo_by_country,
        "country": countries[0],
        "geo_filter_mode": "departement",
    }
    return profile


def main() -> int:
    issues: list[str] = []

    cm_geo = {
        "level1": ["Littoral"],
        "level2": [],
        "cities": ["Douala"],
        "all_cities": False,
    }
    profile_cm = _profile(["Cameroun"], {"Cameroun": cm_geo})
    profile_cm["experience_level"] = "confirme"
    profile_cm["target_sectors"] = ["Informatique"]
    ok, msg = validate_profile_countries_geo(profile_countries(profile_cm), merge_profile_geo(profile_cm))
    if not ok:
        issues.append(f"Cameroun validation failed: {msg}")

    locs = build_country_search_locations("Cameroun", cm_geo)
    if not any("Douala" in loc or "Littoral" in loc for loc in locs):
        issues.append(f"Cameroun search locations unexpected: {locs}")

    job_douala = {"title": "Dev", "location": "Douala", "description": ""}
    job_cam_en = {"title": "Dev", "location": "Douala, Cameroon", "description": ""}
    if not job_matches_geography(job_douala, profile_cm):
        issues.append("Douala job rejected (city-only location)")
    if not job_matches_geography(job_cam_en, profile_cm):
        issues.append("Douala, Cameroon job rejected")
    if not job_matches_country(job_cam_en, "Cameroun"):
        issues.append("job_matches_country failed for Cameroon/Cameroun")

    multi = _profile(
        ["France", "Cameroun"],
        {
            "France": {
                "admin_regions": ["Île-de-France"],
                "selected_departments": [{"code": "75", "name": "Paris"}],
                "selected_cities": ["Paris"],
                "all_cities": False,
                "level1": ["Île-de-France"],
                "level2": ["Paris"],
                "cities": ["Paris"],
            },
            "Cameroun": cm_geo,
        },
    )
    multi["admin_regions"] = ["Île-de-France"]
    multi["selected_departments"] = [{"code": "75", "name": "Paris"}]
    multi["selected_cities"] = ["Paris"]
    multi["experience_level"] = "confirme"
    multi["target_sectors"] = ["Informatique"]
    multi_locs = build_profile_search_locations(multi, max_locations=12)
    if not any("Paris" in loc for loc in multi_locs):
        issues.append(f"Multi-country search missing Paris: {multi_locs}")
    if not any("Douala" in loc or "Littoral" in loc for loc in multi_locs):
        issues.append(f"Multi-country search missing Cameroun zones: {multi_locs}")

    raw_jobs = [
        {
            "title": "Developpeur confirme",
            "location": "Paris (75)",
            "description": "CDI informatique 3 ans experience",
            "contract_type": "CDI",
        },
        {
            "title": "Developpeur confirme",
            "location": "Douala",
            "description": "CDI informatique",
            "contract_type": "CDI",
        },
        {
            "title": "Developpeur confirme",
            "location": "Berlin, Germany",
            "description": "CDI informatique",
            "contract_type": "CDI",
        },
    ]
    kept, stats = apply_strict_job_filters(raw_jobs, multi)
    if stats["kept"] != 2:
        issues.append(f"Expected 2 geo-filtered jobs, kept {stats['kept']} stats={stats}")

    schema_count = sum(
        1 for entry in ISO_COUNTRIES
        if entry["name"] != "France" and country_geo_schema(entry["name"])
    )
    print("=== Geo pipeline verification ===")
    print(f"Countries with region schema: {schema_count}")
    print(f"Cameroun search locations: {locs}")
    print(f"Multi-country locations: {multi_locs}")
    print(f"Filtered jobs kept: {stats['kept']}/{stats['total']}")

    if issues:
        print(f"\nISSUES ({len(issues)}):")
        for item in issues:
            print(f"  - {item}")
        return 1

    print("\nAll geo pipeline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
