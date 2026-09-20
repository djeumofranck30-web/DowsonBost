"""Analysis search should stop once enough offers are found."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from constants import GEMINI_MODELS_CACHE_TTL_SEC, SEARCH_PROVIDER_MAX_WORKERS
from job_providers import WTTJ_MAX_JOBS, WTTJ_MAX_PAGES


def test_wttj_defaults_do_not_paginate_hundreds_of_pages() -> None:
    assert WTTJ_MAX_PAGES <= 3
    assert WTTJ_MAX_JOBS <= 150
    assert SEARCH_PROVIDER_MAX_WORKERS >= 8
    assert GEMINI_MODELS_CACHE_TTL_SEC >= 600


def test_fusion_queries_providers_in_parallel() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    start = source.index("def _search_all_providers_with_fallback(")
    end = source.index("def search_jobs_adzuna(", start)
    body = source[start:end]
    assert "SEARCH_PROVIDER_MAX_WORKERS" in body
    assert "ThreadPoolExecutor" in body


def test_title_search_stops_when_pool_is_already_filled(monkeypatch) -> None:
    from app import search_jobs_for_profile

    calls: list[str] = []

    def fake_country_search(provider, query, country, locations, metier, *args, **kwargs):
        calls.append(str(query))
        return {
            "jobs": [
                {
                    "title": f"{query} {index}",
                    "company": "Acme",
                    "location": "Paris, France",
                    "description": "CDI Développeur Python",
                    "contract_type": "CDI",
                    "url": f"https://example.test/{query}/{index}",
                }
                for index in range(80)
            ],
            "query_used": query,
            "providers_used": ["wttj"],
        }

    monkeypatch.setattr("app._search_jobs_at_country_locations", fake_country_search)
    monkeypatch.setattr("app._with_company_career_sites", lambda result, **kwargs: result)

    result = search_jobs_for_profile(
        "wttj",
        "Développeur Python",
        "France",
        {"country": "France", "job_max_age_days": 7},
        metier="Développeur Python",
        alternate_queries=["Ingénieur logiciel Python", "Développeur backend"],
        skill_queries=["Python Django PostgreSQL"],
        target_count=25,
    )
    assert calls == ["Développeur Python"]
    assert len(result["jobs"]) == 80


def test_search_continues_until_filtered_depth_target(monkeypatch) -> None:
    from datetime import datetime, timedelta, timezone

    from app import search_jobs_for_profile

    calls: list[str] = []
    now = datetime.now(timezone.utc)

    def fake_country_search(provider, query, country, locations, metier, *args, **kwargs):
        calls.append(str(query))
        old = query == "Développeur Python"
        published = (now - timedelta(days=30 if old else 2)).isoformat()
        count = 80 if old else 150
        return {
            "jobs": [
                {
                    "title": f"{query} {index}",
                    "company": "Acme",
                    "location": "Paris, France",
                    "description": "CDI Développeur Python",
                    "contract_type": "CDI",
                    "published_at": published,
                    "url": f"https://example.test/{query}/{index}",
                }
                for index in range(count)
            ],
            "query_used": query,
            "providers_used": ["wttj"],
        }

    monkeypatch.setattr("app._search_jobs_at_country_locations", fake_country_search)
    monkeypatch.setattr("app._with_company_career_sites", lambda result, **kwargs: result)

    result = search_jobs_for_profile(
        "wttj",
        "Développeur Python",
        "France",
        {
            "country": "France",
            "contract_type": "CDI",
            "job_max_age_days": 7,
        },
        metier="Développeur Python",
        alternate_queries=["Ingénieur logiciel Python", "Développeur backend"],
        skill_queries=["Python Django PostgreSQL"],
        target_count=150,
    )
    assert "Développeur Python" in calls
    assert "Ingénieur logiciel Python" in calls
    assert len(result["jobs"]) == 150
    assert all(
        "Ingénieur logiciel Python" in str(job["title"]) for job in result["jobs"]
    )


def test_gemini_model_list_is_cached(monkeypatch) -> None:
    import app as app_mod

    app_mod._GEMINI_MODELS_CACHE.clear()
    calls = {"n": 0}

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "supportedGenerationMethods": ["generateContent"],
                }
            ]
        }
        return response

    monkeypatch.setattr(app_mod.requests, "get", fake_get)
    first, ok1 = app_mod._fetch_gemini_models_from_api("AQ.cached-key")
    second, ok2 = app_mod._fetch_gemini_models_from_api("AQ.cached-key")
    assert ok1 is True and ok2 is True
    assert first == second == ["gemini-2.5-flash"]
    assert calls["n"] == 1
