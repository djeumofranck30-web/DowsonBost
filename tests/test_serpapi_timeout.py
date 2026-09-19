"""SerpApi timeouts must not abort the rest of an analysis."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from job_providers import (
    _search_career_sites_via_google,
    _search_google_organic,
    _serpapi_get,
    search_jobs_indeed_serpapi,
    search_jobs_serpapi_google_jobs,
)


def _timeout() -> requests.ReadTimeout:
    return requests.ReadTimeout(
        "HTTPSConnectionPool(host='serpapi.com', port=443): Read timed out. (read timeout=45)"
    )


def test_serpapi_get_retries_timeout_then_returns_none() -> None:
    with patch("job_providers.requests.get", side_effect=_timeout()) as mocked:
        assert _serpapi_get({"engine": "google_jobs", "q": "python", "api_key": "k"}) is None
    assert mocked.call_count == 2
    assert mocked.call_args.kwargs["timeout"] == 25


def test_serpapi_get_recovers_after_one_timeout() -> None:
    payload = {"jobs_results": [{"title": "Dev"}]}
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = payload
    with patch("job_providers.requests.get", side_effect=[_timeout(), response]) as mocked:
        assert _serpapi_get({"engine": "google_jobs", "q": "python", "api_key": "k"}) == payload
    assert mocked.call_count == 2


def test_google_jobs_returns_empty_on_read_timeout() -> None:
    with patch("job_providers.requests.get", side_effect=_timeout()):
        assert search_jobs_serpapi_google_jobs("python", "Paris", "France", "key") == []


def test_google_organic_returns_none_on_read_timeout() -> None:
    with patch("job_providers.requests.get", side_effect=_timeout()):
        assert _search_google_organic("python site:careers.airbus.com", "France", "key") is None


def test_career_google_stops_after_first_timeout() -> None:
    with patch("job_providers.requests.get", side_effect=_timeout()) as mocked:
        assert (
            _search_career_sites_via_google(
                "python", "Paris", "France", "key", limit=80
            )
            == []
        )
    assert mocked.call_count == 2


def test_indeed_falls_back_when_both_serpapi_engines_time_out() -> None:
    with patch("job_providers.requests.get", side_effect=_timeout()):
        assert search_jobs_indeed_serpapi("python", "Paris", "France", "key") == []


def test_fusion_keeps_wttj_when_serpapi_times_out(monkeypatch) -> None:
    from app import _search_all_providers_with_fallback

    wttj_job = {
        "title": "Développeur Python",
        "company": "Acme",
        "url": "https://www.welcometothejungle.com/fr/companies/acme/jobs/1",
        "source": "Welcome to the Jungle",
    }

    def fake_search(engine, *args, **kwargs):
        if engine == "wttj":
            return [wttj_job]
        raise _timeout()

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
    assert result["providers_used"] == ["wttj"]


def test_single_provider_fallback_survives_serpapi_timeout(monkeypatch) -> None:
    from app import search_jobs_with_fallback

    monkeypatch.setattr("app.search_jobs", lambda *args, **kwargs: (_ for _ in ()).throw(_timeout()))
    result = search_jobs_with_fallback("serpapi", "python", "Paris", "France")
    assert result["jobs"] == []
    assert result["strategy"] == "aucune"
