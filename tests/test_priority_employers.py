"""Priority employers: search ranking and recruiter e-mail domains."""

from __future__ import annotations

from unittest.mock import patch

from priority_employers import (
    PRIORITY_EMPLOYERS,
    employers_for_countries,
    extra_career_page_urls,
    is_priority_employer,
    mailbox_domain_for_company,
    match_priority_employer,
    normalize_employer_country,
    priority_employer_countries,
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


def test_catalogue_covers_requested_countries() -> None:
    names = {item.country: set() for item in PRIORITY_EMPLOYERS}
    for item in PRIORITY_EMPLOYERS:
        names[item.country].add(item.name)
    assert "Shopify" in names["Canada"]
    assert "Proximus" in names["Belgique"]
    assert "Nestlé" in names["Suisse"]
    assert "Apple" in names["Etats-Unis"]
    assert "HSBC" in names["Royaume-Uni"]
    assert "Siemens" in names["Allemagne"]
    assert "Inditex" in names["Espagne"]
    assert "Enel" in names["Italie"]
    assert "EDP" in names["Portugal"]
    assert "ASML" in names["Pays-Bas"]
    assert "Spotify" in names["Suede"]
    assert "Equinor" in names["Norvege"]
    assert "Novo Nordisk" in names["Danemark"]
    assert "Nokia" in names["Finlande"]
    assert "BHP" in names["Australie"]
    assert "Fonterra" in names["Nouvelle-Zelande"]
    assert "OCP Group" in names["Maroc"]
    assert any("Orange" in n for n in names["Cote d Ivoire"])
    assert "Sonatel" in names["Senegal"]
    assert "Safaricom" in names["Kenya"]
    assert "MTN Nigeria" in names["Nigeria"]
    assert "Sasol" in names["Afrique du Sud"]
    assert "Sonatrach" in names["Algerie"]
    assert "Telecom Egypt" in names["Egypte"]
    assert "Bank of Kigali" in names["Rwanda"]
    extra = [c for c in priority_employer_countries() if c != "France"]
    assert extra[:3] == ["Canada", "Belgique", "Suisse"]
    for country in extra:
        assert len(employers_for_countries([country])) >= 10


def test_normalize_employer_country_folds_accents() -> None:
    assert normalize_employer_country("Côte d’Ivoire") == "Cote d Ivoire"
    assert normalize_employer_country("États-Unis") == "Etats-Unis"
    assert normalize_employer_country("Suède") == "Suede"
    assert normalize_employer_country("Nouvelle-Zélande") == "Nouvelle-Zelande"


def test_country_pool_prefers_local_brand() -> None:
    shopify = match_priority_employer({"company": "Shopify"}, countries=["Canada"])
    assert shopify is not None
    assert shopify.country == "Canada"
    assert shopify.domain == "shopify.com"
    apple = match_priority_employer({"company": "Apple"}, countries=["États-Unis"])
    assert apple is not None
    assert apple.country == "Etats-Unis"
    orange_ci = match_priority_employer(
        {"company": "Orange Côte d’Ivoire"},
        countries=["Côte d’Ivoire"],
    )
    assert orange_ci is not None
    assert orange_ci.country == "Cote d Ivoire"
    assert orange_ci.domain == "orange.ci"
    assert is_priority_employer({"company": "Shopify"}, countries=["Canada"])
    assert not is_priority_employer({"company": "SNCF"}, countries=["Canada"])
    assert mailbox_domain_for_company("SNCF") == "sncf.fr"


def test_rank_jobs_boosts_selected_country_employers() -> None:
    from app import rank_jobs_for_cv

    jobs = [
        {
            "title": "Développeur Python",
            "company": "SNCF",
            "description": "Python Django",
            "url": "https://emplois.sncf.com/job/1",
        },
        {
            "title": "Développeur Python",
            "company": "Shopify",
            "description": "Python Django",
            "url": "https://careers.shopify.com/jobs/1",
        },
    ]
    ranked = rank_jobs_for_cv(
        jobs,
        "Python Django",
        ["python", "django"],
        top_n=2,
        user_profile={"selected_countries": ["Canada"], "country": "Canada"},
    )
    assert ranked[0]["company"] == "Shopify"
