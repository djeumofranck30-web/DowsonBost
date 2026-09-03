"""Analysis search order: job title, similar titles, then skills/missions."""

from __future__ import annotations

from job_filters import (
    SEARCH_PHASE_SIMILAR,
    SEARCH_PHASE_SKILLS,
    SEARCH_PHASE_TITLE,
    build_skill_mission_search_queries,
    ordered_search_phases,
)


def test_search_phases_are_title_then_similar_then_skills() -> None:
    phases = ordered_search_phases(
        "Développeur Python",
        similar=["Ingénieur logiciel Python", "Développeur backend"],
        skill_queries=["Python Django PostgreSQL", "APIs REST CI/CD"],
        metier="Développeur Python",
    )
    assert [name for name, _ in phases] == [
        SEARCH_PHASE_TITLE,
        SEARCH_PHASE_SIMILAR,
        SEARCH_PHASE_SKILLS,
    ]
    assert phases[0][1] == ["Développeur Python"]
    assert "Ingénieur logiciel Python" in phases[1][1]
    assert phases[2][1][0].startswith("Python")


def test_skill_mission_queries_use_cv_skills_and_duties() -> None:
    queries = build_skill_mission_search_queries(
        {
            "competences_techniques": ["Python", "Django", "PostgreSQL", "Docker"],
            "experiences": [
                {
                    "poste": "Dev",
                    "missions": "Conception d'APIs REST et industrialisation CI/CD GitLab",
                }
            ],
        }
    )
    blob = " ".join(queries).lower()
    assert "python" in blob
    assert "django" in blob
    assert "apis" in blob or "rest" in blob or "gitlab" in blob or "ci/cd" in blob
    assert not any("développeur python" in item.lower() for item in queries)


def test_search_plan_keeps_exact_title_as_first_query() -> None:
    from job_filters import normalize_job_search_plan

    plan = normalize_job_search_plan(
        {
            "metier": "Développeur Python",
            "query_recherche": "Python Django backend",
            "variantes": ["Ingénieur logiciel Python", "Développeur backend"],
        },
        "Développeur Python",
    )
    assert plan["query_recherche"] == "Développeur Python"
    assert "Python Django backend" in plan["variantes"]
    assert "Ingénieur logiciel Python" in plan["variantes"]


def test_phased_queries_keep_title_jobs_first() -> None:
    from job_filters import tag_jobs_search_phase
    from job_providers import merge_job_lists

    title_jobs = tag_jobs_search_phase(
        [{"title": "Développeur Python", "company": "A", "url": "https://a.example/1"}],
        SEARCH_PHASE_TITLE,
    )
    similar_jobs = tag_jobs_search_phase(
        [{"title": "Ingénieur Python", "company": "B", "url": "https://b.example/2"}],
        SEARCH_PHASE_SIMILAR,
    )
    skill_jobs = tag_jobs_search_phase(
        [{"title": "Backend Django", "company": "C", "url": "https://c.example/3"}],
        SEARCH_PHASE_SKILLS,
    )
    merged = merge_job_lists([title_jobs, similar_jobs, skill_jobs])
    assert [job["_search_phase"] for job in merged] == [
        SEARCH_PHASE_TITLE,
        SEARCH_PHASE_SIMILAR,
        SEARCH_PHASE_SKILLS,
    ]


def test_analysis_pipeline_wires_title_then_skill_search() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "query = target_title" in source
    assert "skill_queries=skill_queries" in source
    assert "target_count=pool_size" in source
    assert "build_skill_mission_search_queries" in source
    assert "ordered_search_phases" in source
    assert "SEARCH_PHASE_CAREER" in source
    assert "career:sites" in source
