"""SerpAPI monthly quota must not abort the rest of an analysis."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from job_providers import (
    CAREER_GOOGLE_QUERY_CAP,
    FREELANCE_PLATFORM_CAP,
    _search_career_sites_via_google,
    _serpapi_get,
    search_jobs_career_sites,
    search_jobs_freelance_platforms,
    search_jobs_indeed_serpapi,
    search_jobs_serpapi_google_jobs,
    serpapi_quota_exhausted,
)

ROOT = Path(__file__).resolve().parents[1]


def _json_response(payload: dict, *, status: int = 200, ok: bool | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.ok = (status < 400) if ok is None else ok
    response.json.return_value = payload
    return response


def test_serpapi_caps_stay_small_enough_for_a_250_plan() -> None:
    assert CAREER_GOOGLE_QUERY_CAP <= 3
    assert FREELANCE_PLATFORM_CAP <= 3


def test_exhausted_json_trips_breaker_and_skips_later_calls() -> None:
    payload = {
        "error": "Your searches are exhausted. You can upgrade your plan at https://serpapi.com/pricing"
    }
    response = _json_response(payload, status=200)
    with patch("job_providers.requests.get", return_value=response) as mocked:
        assert _serpapi_get({"engine": "google_jobs", "q": "python", "api_key": "k"}) is None
        assert serpapi_quota_exhausted()
        assert _serpapi_get({"engine": "google_jobs", "q": "django", "api_key": "k"}) is None
    assert mocked.call_count == 1


def test_http_429_trips_breaker() -> None:
    response = _json_response({"error": "Too many requests"}, status=429, ok=False)
    with patch("job_providers.requests.get", return_value=response) as mocked:
        assert _serpapi_get({"engine": "google_jobs", "q": "python", "api_key": "k"}) is None
        assert search_jobs_serpapi_google_jobs("python", "Paris", "France", "key") == []
        assert search_jobs_indeed_serpapi("python", "Paris", "France", "key") == []
    assert mocked.call_count == 1
    assert serpapi_quota_exhausted()


def test_career_google_stops_after_quota_error() -> None:
    response = _json_response(
        {"error": "Your account has run out of searches."},
        status=200,
    )
    with patch("job_providers.requests.get", return_value=response) as mocked:
        assert (
            _search_career_sites_via_google(
                "python", "Paris", "France", "key", limit=80
            )
            == []
        )
    assert mocked.call_count == 1
    assert serpapi_quota_exhausted()


def test_career_sites_skip_google_when_direct_ats_already_filled(monkeypatch) -> None:
    ats_jobs = [
        {
            "title": f"Dev {index}",
            "company": "Acme",
            "location": "Paris",
            "description": "CDI",
            "url": f"https://boards.greenhouse.io/acme/jobs/{index}",
            "source": "Site carrière entreprise",
        }
        for index in range(80)
    ]
    monkeypatch.setattr(
        "job_providers.search_jobs_direct_ats_boards",
        lambda *args, **kwargs: ats_jobs,
    )
    with patch("job_providers._search_career_sites_via_google") as google:
        jobs = search_jobs_career_sites("python", "Paris", "France", "key", limit=80)
    assert len(jobs) == 80
    google.assert_not_called()


def test_freelance_platforms_skip_http_when_quota_already_tripped() -> None:
    from job_providers import mark_serpapi_quota_exhausted

    mark_serpapi_quota_exhausted()
    with patch("job_providers.requests.get") as mocked:
        assert (
            search_jobs_freelance_platforms(
                "python", "Paris", "France", "key", countries=["France"]
            )
            == []
        )
    mocked.assert_not_called()


def test_fusion_queries_all_selected_engines_together(monkeypatch) -> None:
    from app import _search_all_providers_with_fallback
    from job_providers import reset_serpapi_quota_state

    reset_serpapi_quota_state()

    wttj_job = {
        "title": "Développeur Python",
        "company": "Acme",
        "url": "https://www.welcometothejungle.com/fr/companies/acme/jobs/1",
        "source": "Welcome to the Jungle",
    }
    serp_job = {
        "title": "Python engineer",
        "company": "Indeed Co",
        "url": "https://www.indeed.com/viewjob?jk=1",
        "source": "Indeed",
    }
    called: list[str] = []

    def fake_search(engine, *args, **kwargs):
        called.append(engine)
        if engine == "wttj":
            return [wttj_job]
        if engine == "indeed":
            return [serp_job]
        return []

    monkeypatch.setattr("app.search_jobs", fake_search)
    monkeypatch.setattr(
        "app.configured_providers",
        lambda secrets=None: ["wttj", "indeed", "serpapi"],
    )
    monkeypatch.setattr(
        "app.provider_secrets_from_getter",
        lambda getter: {"serpapi_api_key": "k"},
    )

    result = _search_all_providers_with_fallback(
        "python",
        "Paris",
        "France",
        providers=["wttj", "indeed", "serpapi"],
    )
    assert "wttj" in called
    assert "indeed" in called
    assert "serpapi" in called
    urls = {job["url"] for job in result["jobs"]}
    assert wttj_job["url"] in urls
    assert serp_job["url"] in urls


def test_fusion_uses_serpapi_when_free_engines_are_empty(monkeypatch) -> None:
    from app import _search_all_providers_with_fallback
    from job_providers import reset_serpapi_quota_state

    reset_serpapi_quota_state()

    serp_job = {
        "title": "Développeur Python",
        "company": "Indeed Co",
        "url": "https://www.indeed.com/viewjob?jk=1",
        "source": "Indeed",
    }
    called: list[str] = []

    def fake_search(engine, *args, **kwargs):
        called.append(engine)
        if engine == "indeed":
            return [serp_job]
        return []

    monkeypatch.setattr("app.search_jobs", fake_search)
    monkeypatch.setattr(
        "app.configured_providers",
        lambda secrets=None: ["wttj", "indeed"],
    )
    monkeypatch.setattr(
        "app.provider_secrets_from_getter",
        lambda getter: {"serpapi_api_key": "k"},
    )

    result = _search_all_providers_with_fallback(
        "python",
        "Paris",
        "France",
        providers=["wttj", "indeed"],
    )
    assert result["jobs"] == [serp_job]
    assert "wttj" in called
    assert "indeed" in called


def test_fusion_skips_serpapi_when_quota_already_exhausted(monkeypatch) -> None:
    from app import _search_all_providers_with_fallback
    from job_providers import mark_serpapi_quota_exhausted, reset_serpapi_quota_state

    mark_serpapi_quota_exhausted()
    wttj_job = {
        "title": "Développeur Python",
        "company": "Acme",
        "url": "https://www.welcometothejungle.com/fr/companies/acme/jobs/1",
        "source": "Welcome to the Jungle",
    }
    called: list[str] = []

    def fake_search(engine, *args, **kwargs):
        called.append(engine)
        if engine == "wttj":
            return [wttj_job]
        return [{"title": "should-not-run", "url": "https://indeed.test/x"}]

    monkeypatch.setattr("app.search_jobs", fake_search)
    monkeypatch.setattr(
        "app.configured_providers",
        lambda secrets=None: ["wttj", "indeed", "serpapi"],
    )
    monkeypatch.setattr(
        "app.provider_secrets_from_getter",
        lambda getter: {"serpapi_api_key": "k"},
    )

    result = _search_all_providers_with_fallback(
        "python",
        "Paris",
        "France",
        providers=["wttj", "indeed", "serpapi"],
    )
    assert result["jobs"] == [wttj_job]
    assert "wttj" in called
    assert "indeed" not in called
    assert "serpapi" not in called
    reset_serpapi_quota_state()


def test_pipeline_notice_locale_keys_exist() -> None:
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        assert "pipeline.serpapi_exhausted" in data
        assert "SerpAPI" in data["pipeline.serpapi_exhausted"] or "SerpApi" in data[
            "pipeline.serpapi_exhausted"
        ]


def test_pipeline_appends_serpapi_exhausted_notice() -> None:
    from pathlib import Path as _Path

    app_src = _Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
        encoding="utf-8"
    )
    assert "reset_serpapi_quota_state()" in app_src
    assert "pipeline.serpapi_exhausted" in app_src
    assert "provider_uses_serpapi" in app_src
    assert "if serpapi_quota_exhausted():" in app_src
    assert "if not merged and serp_engines and not serpapi_quota_exhausted()" not in app_src
