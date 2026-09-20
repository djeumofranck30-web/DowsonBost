"""Radius / Nominatim geolocation is removed from analysis and the UI."""

from __future__ import annotations

from pathlib import Path

from job_filters import (
    GEO_FILTER_MODES,
    apply_strict_job_filters,
    normalize_geo_filter_mode,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_geo_mode_is_always_country_region_department() -> None:
    assert GEO_FILTER_MODES == ("departement",)
    assert "ville" not in GEO_FILTER_MODES
    assert "rayon" not in GEO_FILTER_MODES
    assert normalize_geo_filter_mode("rayon") == "departement"
    assert normalize_geo_filter_mode("ville") == "departement"
    assert normalize_geo_filter_mode("departement") == "departement"
    assert normalize_geo_filter_mode(None) == "departement"


def test_analysis_filter_never_calls_nominatim() -> None:
    from datetime import datetime, timezone

    profile = {
        "country": "France",
        "selected_countries": ["France"],
        "geo_filter_mode": "rayon",
        "search_radius_km": 20,
        "contract_type": "CDI",
        "admin_regions": ["Île-de-France"],
        "selected_departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "selected_cities": ["Paris"],
        "geo_by_country": {
            "France": {
                "admin_regions": ["Île-de-France"],
                "selected_departments": [{"code": "75", "name": "Paris"}],
                "selected_cities": ["Paris"],
                "all_cities": False,
                "level1": ["Île-de-France"],
                "level2": ["Paris"],
                "cities": ["Paris"],
            }
        },
        "experience_level": "tous",
        "target_sectors": [],
        "job_max_age_days": 30,
        "work_mode": "tous",
        "salary_min": 0,
    }
    jobs = [
        {
            "title": "Développeur Python",
            "company": "Acme",
            "location": "Paris (75), France",
            "description": "CDI Python",
            "url": "https://example.test/1",
            "contract_type": "CDI",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    kept, _stats = apply_strict_job_filters(jobs, profile, min_keep=1)
    assert kept


def test_ui_and_filters_drop_radius_controls() -> None:
    app = _read("app.py")
    filters = _read("job_filters.py")
    assert "register_wiz_radius" not in app
    assert 't("profile.radius")' not in app
    assert 't("auth.register.radius")' not in app
    assert 't("profile.geo_mode")' not in app
    assert 't("auth.register.geo_mode")' not in app
    assert "register_wiz_geo_mode" not in app
    assert "nominatim.openstreetmap.org" not in filters
    assert "def _coords_from_nominatim" not in filters
    assert "def haversine_km" not in filters
    assert "def build_radius_center_location" not in filters
    assert '"rayon"' not in filters.split("def normalize_geo_filter_mode")[0]
