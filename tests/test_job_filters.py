"""Strict job filters: publication age can backfill toward the analysis depth."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_filters import apply_strict_job_filters, is_company_career_job

ROOT = Path(__file__).resolve().parents[1]


def _paris_profile(**overrides) -> dict:
    profile = {
        "target_job_title": "Administrateur systemes et reseaux",
        "contract_type": "CDI",
        "country": "France",
        "selected_countries": ["France"],
        "geo_filter_mode": "departement",
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
        "job_max_age_days": 7,
    }
    profile.update(overrides)
    return profile


def _job(
    title: str,
    *,
    location: str = "Paris (75), France",
    published_days_ago: int | None = 2,
    description: str = "CDI administrateur systemes reseaux",
    contract_type: str = "CDI",
) -> dict:
    published_at = None
    if published_days_ago is not None:
        published_at = (
            datetime.now(timezone.utc) - timedelta(days=published_days_ago)
        ).isoformat()
    return {
        "title": title,
        "location": location,
        "description": description,
        "contract_type": contract_type,
        "published_at": published_at,
    }


def test_age_filter_without_min_keep_drops_older_offers() -> None:
    jobs = [
        *[_job(f"Recent {i}", published_days_ago=2) for i in range(5)],
        *[_job(f"Older {i}", published_days_ago=20) for i in range(40)],
        _job("Lyon CDI", location="Lyon (69), France", published_days_ago=2),
        _job("Paris stage", description="Stage 6 mois", contract_type="Stage", published_days_ago=2),
    ]
    kept, stats = apply_strict_job_filters(jobs, _paris_profile())
    assert len(kept) == 5
    assert stats["kept_strict"] == 5
    assert stats["backfilled_older"] == 0
    assert stats["rejected_publication_age"] == 40
    assert stats["rejected_geo"] == 1
    assert stats["rejected_contract"] == 1
    assert all(item["title"].startswith("Recent") for item in kept)


def test_min_keep_backfills_newest_older_matching_offers() -> None:
    jobs = [
        *[_job(f"Recent {i}", published_days_ago=2) for i in range(5)],
        *[_job(f"Older {i:02d}", published_days_ago=10 + i) for i in range(40)],
        _job("Lyon older", location="Lyon (69), France", published_days_ago=15),
        _job(
            "Paris stage older",
            description="Stage 6 mois",
            contract_type="Stage",
            published_days_ago=15,
        ),
    ]
    kept, stats = apply_strict_job_filters(jobs, _paris_profile(), min_keep=25)
    assert len(kept) == 25
    assert stats["kept_strict"] == 5
    assert stats["backfilled_older"] == 20
    assert stats["kept"] == 25
    titles = [item["title"] for item in kept]
    assert titles[:5] == [f"Recent {i}" for i in range(5)]
    assert titles[5:] == [f"Older {i:02d}" for i in range(20)]
    assert "Lyon older" not in titles
    assert "Paris stage older" not in titles


def test_min_keep_prefers_newest_jobs_outside_age_window() -> None:
    jobs = [
        *[_job(f"Recent {i}", published_days_ago=1) for i in range(5)],
        *[_job(f"Older {i:02d}", published_days_ago=10 + i) for i in range(40)],
    ]
    kept, stats = apply_strict_job_filters(jobs, _paris_profile(), min_keep=25)
    assert len(kept) == 25
    assert stats["kept_strict"] == 5
    assert stats["backfilled_older"] == 20
    backfilled = [item["title"] for item in kept[5:]]
    assert backfilled == [f"Older {i:02d}" for i in range(20)]
    assert stats["rejected_publication_age"] == 20


def test_min_keep_cannot_invent_offers_outside_zone_or_contract() -> None:
    jobs = [
        *[_job(f"Recent {i}", published_days_ago=2) for i in range(5)],
        *[_job(f"Lyon {i}", location="Lyon (69), France", published_days_ago=20) for i in range(80)],
    ]
    kept, stats = apply_strict_job_filters(jobs, _paris_profile(), min_keep=100)
    assert len(kept) == 5
    assert stats["kept_strict"] == 5
    assert stats["backfilled_older"] == 0
    assert stats["rejected_geo"] == 80


def test_complet_depth_fills_toward_100_when_age_filter_is_tight() -> None:
    jobs = [
        *[_job(f"Recent {i}", published_days_ago=3) for i in range(27)],
        *[_job(f"Older {i:03d}", published_days_ago=14 + (i % 20)) for i in range(200)],
    ]
    kept, stats = apply_strict_job_filters(jobs, _paris_profile(), min_keep=100)
    assert stats["kept_strict"] == 27
    assert stats["backfilled_older"] == 73
    assert len(kept) == 100


def test_career_site_senior_and_france_wide_kept_for_confirme() -> None:
    jobs = [
        {
            "title": "Senior Software Engineer",
            "location": "Paris, France",
            "description": "Senior Software Engineer",
            "url": "https://boards.greenhouse.io/datadog/jobs/2",
            "contract_type": "",
            "source": "Site carrière entreprise",
            "published_at": None,
        },
        {
            "title": "Software Engineer",
            "location": "France entière",
            "description": "Software Engineer",
            "url": "https://boards.greenhouse.io/doctolib/jobs/3",
            "contract_type": "",
            "source": "Site carrière entreprise",
            "published_at": None,
        },
    ]
    kept, stats = apply_strict_job_filters(
        jobs,
        _paris_profile(experience_level="confirme", target_sectors=[]),
    )
    assert {job["title"] for job in kept} == {
        "Senior Software Engineer",
        "Software Engineer",
    }
    assert stats["rejected_geo"] == 0
    assert stats["rejected_experience"] == 0


def test_career_site_jobs_are_kept_without_cdi_or_level_words() -> None:
    career = {
        "title": "Software Engineer",
        "company": "Datadog",
        "location": "Paris, France",
        "description": "Software Engineer",
        "url": "https://boards.greenhouse.io/datadog/jobs/1",
        "contract_type": "",
        "source": "Site carrière entreprise",
        "_search_phase": "career",
        "published_at": None,
    }
    kept, stats = apply_strict_job_filters(
        [career],
        _paris_profile(experience_level="confirme", target_sectors=[]),
    )
    assert is_company_career_job(career)
    assert [job["title"] for job in kept] == ["Software Engineer"]
    assert stats["rejected_contract"] == 0
    assert stats["rejected_experience"] == 0


def test_backfill_locale_keys_exist() -> None:
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        assert "pipeline.filter_backfill" in data
        assert "{target}" in data["pipeline.filter_backfill"]
        assert "pipeline.filter_shortfall" in data
        assert "{target}" in data["pipeline.filter_shortfall"]


def test_pipeline_passes_min_keep_and_refresh_key() -> None:
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "refresh_key: str = \"\"" in app_src
    assert "search_refresh_key: str = \"\"" in app_src
    assert "min_keep=top_n" in app_src
    assert "pipeline.filter_backfill" in app_src
    worker = (ROOT / "services/analysis_worker.py").read_text(encoding="utf-8")
    assert "search_refresh_key=str(job_id)" in worker
