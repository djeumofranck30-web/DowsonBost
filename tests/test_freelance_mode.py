"""Freelance search mode: country platforms, mission matching, honest proposal."""

from __future__ import annotations

from pathlib import Path

from freelance_platforms import (
    SEARCH_MODE_EMPLOI,
    SEARCH_MODE_FREELANCE,
    enrich_query_for_freelance,
    is_freelance_mode,
    job_matches_budget,
    platforms_for_countries,
    profile_search_mode,
    tag_freelance_mission,
)
from document_generation import generate_freelance_proposal
from job_filters import apply_strict_job_filters, enrich_search_query

ROOT = Path(__file__).resolve().parents[1]


def test_profile_search_mode_follows_contract_and_flag() -> None:
    assert profile_search_mode({"contract_type": "CDI"}) == SEARCH_MODE_EMPLOI
    assert profile_search_mode({"contract_type": "Freelance"}) == SEARCH_MODE_FREELANCE
    assert profile_search_mode({"search_mode": "freelance", "contract_type": "CDI"}) == SEARCH_MODE_FREELANCE
    assert is_freelance_mode({"contract_type": "Freelance"})


def test_platforms_are_scoped_to_selected_country() -> None:
    france = platforms_for_countries(["France"])
    canada = platforms_for_countries(["Canada"])
    fr_hosts = {host for _name, host in france}
    ca_hosts = {host for _name, host in canada}
    assert "malt.fr" in fr_hosts
    assert "freelance.com" in fr_hosts
    assert "upwork.com" in ca_hosts
    assert "workhoppers.com" in ca_hosts
    assert "malt.fr" not in ca_hosts


def test_freelance_query_keeps_title_and_adds_keywords() -> None:
    boosted = enrich_query_for_freelance("Développeur Python")
    assert boosted.lower().startswith("développeur python")
    assert "freelance" in boosted.lower()
    assert "mission" in boosted.lower()
    via_profile = enrich_search_query(
        "Admin réseau",
        {"contract_type": "Freelance"},
        "Freelance",
    )
    assert "freelance" in via_profile.lower()


def test_mission_budget_and_duration_are_parsed() -> None:
    job = tag_freelance_mission(
        {
            "title": "Mission DevOps",
            "company": "ClientX",
            "location": "Paris, France",
            "description": "TJM 550 € / jour, durée 3 mois, remote. CDI interdit.",
            "url": "https://www.malt.fr/jobs/1",
        },
        platform="Malt",
    )
    assert job["listing_kind"] == "mission"
    assert job["contract_type"] == "Freelance"
    assert job["mission_budget"] == 550
    assert "3 mois" in job["mission_duration"].lower()
    assert job["source"] == "Malt"


def test_budget_filter_drops_missions_below_tjm() -> None:
    cheap = {"title": "Mission", "description": "TJM 200 € / jour"}
    fair = {"title": "Mission", "description": "TJM 500 € / jour"}
    unknown = {"title": "Mission", "description": "Budget à convenir"}
    assert not job_matches_budget(cheap, 450)
    assert job_matches_budget(fair, 450)
    assert job_matches_budget(unknown, 450)


def test_freelance_filters_keep_matching_missions() -> None:
    profile = {
        "contract_type": "Freelance",
        "selected_countries": ["France"],
        "country": "France",
        "admin_regions": ["Île-de-France"],
        "selected_departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "selected_cities": ["Paris"],
        "experience_level": "tous",
        "target_sectors": [],
        "job_max_age_days": 30,
        "work_mode": "tous",
        "daily_rate": 400,
    }
    jobs = [
        {
            "title": "Mission Python",
            "company": "Malt client",
            "location": "Paris (75), France",
            "description": "CDI interdit, freelance Python TJM 500 € / jour",
            "contract_type": "Freelance",
            "listing_kind": "mission",
            "source": "Malt",
            "published_at": None,
        },
        {
            "title": "Dev CDI",
            "company": "Corp",
            "location": "Paris (75), France",
            "description": "CDI développeur Python",
            "contract_type": "CDI",
            "published_at": None,
        },
    ]
    kept, stats = apply_strict_job_filters(jobs, profile)
    assert [job["title"] for job in kept] == ["Mission Python"]
    assert stats["rejected_contract"] == 1
    assert kept[0]["listing_kind"] == "mission"


def test_proposal_uses_real_skills_and_does_not_invent_projects() -> None:
    proposal = generate_freelance_proposal(
        "CV court sans projets nommés.",
        {"title": "Mission data", "company": "ClientX"},
        {
            "full_name": "Jane Doe",
            "skills_text": "Python, Django, PostgreSQL",
            "daily_rate": 500,
            "experiences_text": "",
        },
    )
    assert "ClientX" in proposal
    assert "Python" in proposal
    assert "Jane Doe" in proposal
    assert "disponible immédiatement" in proposal.lower()
    assert "aucune mission n’est inventée" in proposal or "CV joint" in proposal


def test_app_wires_freelance_search_mode() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "profile.search_mode" in app
    assert "_with_freelance_platforms(" in app
    assert "include_career = not is_freelance_mode(profile)" in app
    assert "try_search_freelance_platforms" in app
    assert "job.apply_mission" in app
    filters = (ROOT / "job_filters.py").read_text(encoding="utf-8")
    assert "SEARCH_PHASE_FREELANCE" in filters
    providers = (ROOT / "job_providers.py").read_text(encoding="utf-8")
    assert "def search_jobs_freelance_platforms(" in providers
