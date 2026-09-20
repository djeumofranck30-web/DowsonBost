"""Priority employers: search ranking and recruiter e-mail domains."""

from __future__ import annotations

from unittest.mock import patch

from priority_employers import (
    PRIORITY_EMPLOYERS,
    extra_career_page_urls,
    is_priority_employer,
    mailbox_domain_for_company,
    match_priority_employer,
)
from services.hunter import (
    clear_hunter_cache,
    domain_from_company_name,
    find_recruiter_email,
    infer_company_domain,
)


def test_priority_catalogue_covers_first_and_second_lists() -> None:
    names = {item.name for item in PRIORITY_EMPLOYERS}
    for expected in (
        "SNCF",
        "Thales",
        "Arkema",
        "Air Liquide",
        "Saint-Gobain Isover",
        "ArcelorMittal France",
        "Zodiac Aerospace",
        "Pfizer France",
        "Clinique du Parc Lyon",
        "Clinique du Parc Saint-Brieuc",
        "Ramsay Générale de Santé",
    ):
        assert expected in names
    assert len(PRIORITY_EMPLOYERS) >= 240


def test_match_prefers_specific_saint_gobain_brand() -> None:
    matched = match_priority_employer({"company": "Saint-Gobain Isover"})
    assert matched is not None
    assert matched.name == "Saint-Gobain Isover"
    assert matched.domain == "isover.fr"


def test_match_clinique_du_parc_city_and_industry_domains() -> None:
    parc = match_priority_employer({"company": "Clinique du Parc Lyon"})
    assert parc is not None
    assert parc.name == "Clinique du Parc Lyon"
    assert mailbox_domain_for_company("Arkema") == "arkema.com"
    assert mailbox_domain_for_company("Air Liquide") == "airliquide.com"
    assert mailbox_domain_for_company("Zodiac Aerospace") == "safran-group.com"
    assert domain_from_company_name("Nexans") == "nexans.com"
    assert is_priority_employer({"company": "Würth France"})
    assert extra_career_page_urls({"company": "Arkema"})[0].endswith("arkema.com")


def test_indeed_arkema_offer_uses_company_mailbox_domain() -> None:
    job = {
        "company": "Arkema",
        "url": "https://www.indeed.fr/viewjob?jk=arkema",
        "title": "Ingénieur process",
    }
    assert infer_company_domain(job) == "arkema.com"


def test_priority_employer_generic_inbox_when_hunter_has_no_listing() -> None:
    clear_hunter_cache()
    job = {
        "company": "Air Liquide",
        "url": "https://www.indeed.fr/viewjob?jk=airliquide",
        "description": "Postulez en ligne.",
    }
    empty = {"data": {"emails": []}}
    with (
        patch("services.hunter.hunter_api_key", return_value="hunter-test"),
        patch("services.hunter._hunter_get", return_value=empty),
        patch(
            "services.hunter._hunter_verify",
            side_effect=lambda email, _key: email == "recrutement@airliquide.com",
        ) as verified,
    ):
        assert find_recruiter_email(job, api_key="hunter-test") == "recrutement@airliquide.com"
    assert verified.call_count >= 1
    clear_hunter_cache()


def test_rank_jobs_boosts_priority_employers() -> None:
    from app import rank_jobs_for_cv

    jobs = [
        {
            "title": "Développeur Python",
            "company": "Acme",
            "description": "Python Django",
            "url": "https://example.test/acme",
        },
        {
            "title": "Développeur Python",
            "company": "Thales",
            "description": "Python Django",
            "url": "https://careers.thalesgroup.com/job/1",
        },
    ]
    ranked = rank_jobs_for_cv(jobs, "Python Django", ["python", "django"], top_n=2)
    assert ranked[0]["company"] == "Thales"
