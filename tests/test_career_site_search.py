"""Company career-site search (Greenhouse, Lever, Workday, …)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from i18n import job_provider_label
from job_providers import (
    JOB_PROVIDER_CAREER_SITES,
    JOB_PROVIDER_LABELS,
    JOB_PROVIDER_SIDEBAR_ORDER,
    company_from_career_url,
    merge_career_site_results,
    search_jobs_career_sites,
    try_search_career_sites,
)


def test_career_sites_is_a_sidebar_engine() -> None:
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

    with patch(
        "job_providers.requests.get",
        side_effect=[_organic_payload(greenhouse, indeed), _organic_payload(homepage, career_job)],
    ) as mocked_get:
        jobs = search_jobs_career_sites(
            "développeur python",
            "Paris",
            "France",
            "test-key",
        )

    assert mocked_get.call_count == 2
    urls = {job["url"] for job in jobs}
    assert "https://boards.greenhouse.io/stripe/jobs/4242" in urls
    assert "https://careers.airbus.com/job/ingenieur-data-paris" in urls
    assert not any("indeed.com" in url for url in urls)
    assert not any(job["url"].rstrip("/") == "https://careers.airbus.com" for job in jobs)

    stripe = next(job for job in jobs if "greenhouse" in job["url"])
    assert stripe["company"] == "Stripe"
    assert stripe["title"] == "Développeur Python"
    assert stripe["source"] == "Site carrière entreprise"
    assert stripe["location"] == "Paris"


def test_search_jobs_career_sites_empty_without_key() -> None:
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
    assert first["providers_used"] == ["indeed", JOB_PROVIDER_CAREER_SITES]
    assert len(first["jobs"]) == 2

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
