"""Company career-site search (Greenhouse, Lever, Workday, …)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from i18n import job_provider_label
from job_providers import (
    JOB_PROVIDER_CAREER_SITES,
    JOB_PROVIDER_LABELS,
    JOB_PROVIDER_SIDEBAR_ORDER,
    _career_site_google_queries,
    company_from_career_url,
    merge_career_site_results,
    search_jobs_career_sites,
    search_jobs_direct_ats_boards,
    try_search_career_sites,
)


def test_analysis_search_always_merges_career_sites() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "def _with_company_career_sites(" in source
    assert source.count("_with_company_career_sites(") >= 3
    assert "SEARCH_PHASE_CAREER" in source
    assert JOB_PROVIDER_SIDEBAR_ORDER[1] == JOB_PROVIDER_CAREER_SITES
    assert JOB_PROVIDER_SIDEBAR_ORDER[2] == "wttj"

    assert JOB_PROVIDER_CAREER_SITES in JOB_PROVIDER_SIDEBAR_ORDER
    assert "carrière" in JOB_PROVIDER_LABELS[JOB_PROVIDER_CAREER_SITES].lower()
    assert "carrière" in job_provider_label(JOB_PROVIDER_CAREER_SITES).lower()


def test_company_from_career_url() -> None:
    assert (
        company_from_career_url("https://boards.greenhouse.io/stripe/jobs/123")
        == "Stripe"
    )
    assert company_from_career_url("https://jobs.lever.co/datadog/abc") == "Datadog"
    assert (
        company_from_career_url("https://airbus.wd3.myworkdayjobs.com/en-US/Careers/job/1")
        == "Airbus"
    )
    assert (
        company_from_career_url("https://careers.airbus.com/job/python-engineer")
        == "Airbus"
    )
    assert (
        company_from_career_url(
            "https://careers.societegenerale.com/offre/developpeur-python-paris"
        )
        == "Société Générale"
    )
    assert company_from_career_url("https://jobs.atos.net/job/data-engineer") == "Atos"
    assert (
        company_from_career_url(
            "https://group.bnpparibas.com/en/careers/job/analyste"
        )
        == "BNP Paribas"
    )


def _organic_payload(*items: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"organic_results": list(items)}
    response.raise_for_status.return_value = None
    return response


def test_search_jobs_career_sites_parses_ats_and_skips_job_boards() -> None:
    greenhouse = {
        "title": "Développeur Python | Stripe | Greenhouse",
        "link": "https://boards.greenhouse.io/stripe/jobs/4242",
        "snippet": "CDI Python Django — Paris",
        "source": "Greenhouse",
    }
    indeed = {
        "title": "Développeur Python - Indeed",
        "link": "https://fr.indeed.com/viewjob?jk=abc",
        "snippet": "Offre Indeed",
        "source": "Indeed",
    }
    homepage = {
        "title": "Careers at Airbus",
        "link": "https://careers.airbus.com/",
        "snippet": "Join us",
        "source": "Airbus",
    }
    career_job = {
        "title": "Ingénieur data - Airbus",
        "link": "https://careers.airbus.com/job/ingenieur-data-paris",
        "snippet": "Poste CDI data Paris",
        "source": "Airbus",
    }
    sg_job = {
        "title": "Développeur full stack | Société Générale",
        "link": "https://careers.societegenerale.com/offre/developpeur-fullstack",
        "snippet": "CDI Paris — recrutement Société Générale",
        "source": "Société Générale",
    }

    with patch(
        "job_providers.search_jobs_direct_ats_boards",
        return_value=[],
    ), patch(
        "job_providers.requests.get",
        side_effect=[
            _organic_payload(greenhouse, indeed),
            _organic_payload(sg_job),
            _organic_payload(homepage, career_job),
            _organic_payload(),
            _organic_payload(),
        ],
    ) as mocked_get:
        jobs = search_jobs_career_sites(
            "développeur python",
            "Paris",
            "France",
            "test-key",
        )

    assert mocked_get.call_count >= 3
    urls = {job["url"] for job in jobs}
    assert "https://boards.greenhouse.io/stripe/jobs/4242" in urls
    assert "https://careers.airbus.com/job/ingenieur-data-paris" in urls
    assert "https://careers.societegenerale.com/offre/developpeur-fullstack" in urls
    assert not any("indeed.com" in url for url in urls)
    assert not any(job["url"].rstrip("/") == "https://careers.airbus.com" for job in jobs)

    stripe = next(job for job in jobs if "greenhouse" in job["url"])
    assert stripe["company"] == "Stripe"
    assert stripe["title"] == "Développeur Python"
    assert stripe["source"] == "Site carrière entreprise"
    assert stripe["location"] == "Paris"
    sg = next(job for job in jobs if "societegenerale" in job["url"])
    assert sg["company"] == "Société Générale"


def test_career_site_queries_target_major_employers() -> None:
    queries = " ".join(_career_site_google_queries("développeur", "Paris"))
    lowered = queries.lower()
    assert "societegenerale" in lowered
    assert "atos" in lowered
    assert "bnpparibas" in lowered or "bnp paribas" in lowered
    assert "inurl:recrutement" in lowered
    assert "edf.fr" in lowered or "recrute.edf" in lowered


def test_direct_ats_keeps_matching_greenhouse_jobs() -> None:
    payload = {
        "jobs": [
            {
                "title": "Développeur Python",
                "absolute_url": "https://boards.greenhouse.io/datadog/jobs/1",
                "location": {"name": "Paris"},
            },
            {
                "title": "Account Executive",
                "absolute_url": "https://boards.greenhouse.io/datadog/jobs/2",
                "location": {"name": "Paris"},
            },
        ]
    }
    response = MagicMock()
    response.ok = True
    response.json.return_value = payload
    with patch("job_providers.GREENHOUSE_BOARD_TOKENS", (("datadog", "Datadog"),)), patch(
        "job_providers.LEVER_COMPANY_SLUGS", ()
    ), patch("job_providers.SMARTRECRUITERS_COMPANIES", ()), patch(
        "job_providers.requests.get", return_value=response
    ):
        jobs = search_jobs_direct_ats_boards("développeur python", "Paris")
    assert len(jobs) == 1
    assert jobs[0]["company"] == "Datadog"
    assert jobs[0]["source"] == "Site carrière entreprise"
    assert "greenhouse.io" in jobs[0]["url"]


def test_search_jobs_career_sites_empty_without_key() -> None:
    with patch("job_providers.search_jobs_direct_ats_boards", return_value=[]):
        assert search_jobs_career_sites("python", "Paris", "France", "") == []


def test_try_search_career_sites_swallows_http_errors() -> None:
    response = MagicMock()
    response.status_code = 500
    error = requests.HTTPError("boom")
    error.response = response
    with patch("job_providers.requests.get", side_effect=error):
        assert try_search_career_sites("python", "Paris", "France", "key") == []


def test_merge_career_site_results_appends_once(monkeypatch: pytest.MonkeyPatch) -> None:
    extra = [
        {
            "title": "Backend engineer",
            "company": "Stripe",
            "location": "Paris",
            "description": "",
            "url": "https://boards.greenhouse.io/stripe/jobs/1",
            "contract_type": "",
            "source": "Site carrière entreprise",
        }
    ]
    monkeypatch.setattr(
        "job_providers.try_search_career_sites",
        lambda *args, **kwargs: extra,
    )
    first = merge_career_site_results(
        {
            "jobs": [
                {
                    "title": "Dev",
                    "company": "Acme",
                    "url": "https://fr.indeed.com/viewjob?jk=1",
                }
            ],
            "providers_used": ["indeed"],
        },
        query="développeur",
        location="Paris",
        country="France",
        provider="indeed",
        api_key="key",
    )
    assert first["providers_used"] == [JOB_PROVIDER_CAREER_SITES, "indeed"]
    assert len(first["jobs"]) == 2
    assert first["jobs"][0]["url"] == extra[0]["url"]

    skipped = merge_career_site_results(
        first,
        query="développeur",
        provider="indeed",
        api_key="key",
    )
    assert skipped["jobs"] == first["jobs"]

    dedicated = merge_career_site_results(
        {"jobs": extra, "providers_used": [JOB_PROVIDER_CAREER_SITES]},
        query="développeur",
        provider=JOB_PROVIDER_CAREER_SITES,
        api_key="key",
    )
    assert dedicated["providers_used"] == [JOB_PROVIDER_CAREER_SITES]
