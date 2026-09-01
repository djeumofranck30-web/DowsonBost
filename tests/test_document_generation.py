"""ATS alignment for adapted CV and cover letter generation."""

from __future__ import annotations

from cv_layout import parse_adapted_cv
from document_generation import (
    adapted_competences,
    collect_alignment_terms,
    generate_adapted_cv,
    generate_cover_letter,
    missing_alignment_gaps,
)


ORIGINAL_CV = """
Jane Doe
Développeuse Python
Paris

Compétences : Python, Django, PostgreSQL, Docker, AWS
Expérience : conception d'APIs REST, CI/CD chez Acme (2022-2025)
"""

FULL_MATCH = {
    "titre_cv_recommande": "Développeuse Python",
    "score_correspondance": 88,
    "analyse_competences": {
        "presentes": ["Python", "Django"],
        "partielles": ["Docker"],
        "offre_technos": ["Python", "Kubernetes"],
        "offre_obligatoires": ["Python"],
    },
    "mots_cles_manquants": ["Django", "Kubernetes"],
    "modifications_cv": [
        "Ajouter Django dans les compétences",
        "Mettre en avant les APIs REST dans l'expérience",
    ],
}

JOB = {
    "title": "Développeuse Python",
    "company": "NovaTech",
    "description": "Python Django APIs REST Docker",
    "location": "Paris",
    "contract_type": "CDI",
}

ALIGNED_CV = """
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
TELEPHONE: +33 6 00 00 00 00
VILLE: Paris

## PROFIL
Développeuse Python spécialisée Django et APIs REST.

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS | Kubernetes

## EXPERIENCE
POSTE: Développeuse Python
ENTREPRISE: Acme
PERIODE: 2022 - 2025
- Conception d'APIs REST
- Mise en place CI/CD Docker
"""

WEAK_CV = """
NOM: Jane Doe
TITRE: Ingénieure logiciel
EMAIL: jane@example.com

## PROFIL
Ingénieure logicielle.

## COMPETENCES
PostgreSQL | AWS
"""


def test_present_and_partial_skills_are_required_alignment_terms():
    alignment = collect_alignment_terms(ORIGINAL_CV, JOB, FULL_MATCH)
    folded = " ".join(alignment["required_terms"]).lower()
    assert "python" in folded
    assert "django" in folded
    assert "docker" in folded
    assert "kubernetes" in folded
    assert alignment["modifications"][0].lower().startswith("ajouter django")
    skills = " ".join(alignment["adapted_skills"]).lower()
    assert "python" in skills
    assert "django" in skills
    assert "kubernetes" in skills


def test_offer_skill_labels_replace_cv_aliases():
    cv = "Compétences : JS, Postgres, React"
    match = {
        "titre_cv_recommande": "Développeur frontend",
        "analyse_competences": {
            "presentes": [],
            "partielles": [],
            "offre_technos": ["JavaScript", "PostgreSQL", "Kubernetes"],
            "offre_obligatoires": ["JavaScript"],
        },
        "mots_cles_manquants": [],
        "modifications_cv": [],
    }
    skills = [item.lower() for item in adapted_competences(cv, match)]
    assert "javascript" in skills
    assert "postgresql" in skills
    assert "kubernetes" in skills


def test_missing_alignment_gaps_detects_unapplied_modifications():
    alignment = collect_alignment_terms(ORIGINAL_CV, JOB, FULL_MATCH)
    gaps = missing_alignment_gaps(WEAK_CV, alignment, kind="cv")
    blob = " ".join(gaps).lower()
    assert "django" in blob or "python" in blob
    assert "titre" in blob or "développeuse" in blob.lower() or "developpeuse" in blob


def test_aligned_cv_has_no_gaps():
    alignment = collect_alignment_terms(ORIGINAL_CV, JOB, FULL_MATCH)
    assert missing_alignment_gaps(ALIGNED_CV, alignment, kind="cv") == []


def test_generate_adapted_cv_rewrites_until_modifications_appear():
    calls: list[str] = []

    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        calls.append(user)
        if len(calls) == 1:
            return WEAK_CV
        return ALIGNED_CV

    result = generate_adapted_cv(
        ORIGINAL_CV,
        JOB,
        FULL_MATCH,
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    assert len(calls) >= 2
    assert "Django" in result
    assert "Développeuse Python" in result
    assert "incomplet" in calls[1].lower() or "100 %" in calls[1] or "absents" in calls[1]


def test_generate_cover_letter_requires_company_and_keywords():
    calls: list[str] = []

    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        calls.append(user)
        if len(calls) == 1:
            return "Madame, Monsieur, je postule. Cordialement."
        return (
            "Objet : candidature Développeuse Python — NovaTech\n\n"
            "Madame, Monsieur, développeuse Python experte Django, Docker et Kubernetes, "
            "je conçois des APIs REST. Cordialement."
        )

    letter = generate_cover_letter(
        ORIGINAL_CV,
        JOB,
        FULL_MATCH,
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    assert "NovaTech" in letter
    assert "Django" in letter
    assert "Kubernetes" in letter or "kubernetes" in letter.lower()
    assert len(calls) >= 2
    assert "dates" in calls[0].lower() or "lieu" in calls[0].lower()
    assert "EXPÉRIENCES ET MISSIONS" in calls[0] or "missions du cv" in calls[0].lower()


STRUCTURED_ORIGINAL_CV = """
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
VILLE: Lyon

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS

## EXPERIENCE
POSTE: Développeuse Python
ENTREPRISE: Acme
PERIODE: 2022 - 2025
LIEU: Lyon
- Conception d'APIs REST
- Mise en place CI/CD
"""

LLM_CHANGED_DATES_CV = """
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
VILLE: Paris

## PROFIL
Développeuse Python spécialisée Django et APIs REST.

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS | Kubernetes

## EXPERIENCE
POSTE: Ingénieure backend Python
ENTREPRISE: Acme
PERIODE: 2019 - 2024
LIEU: Paris
- Conception d'APIs REST
- Mise en place CI/CD Docker
"""


def test_generate_adapted_cv_restores_original_dates_and_location():
    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        assert "PERIODE" in user or "Dates=" in user
        assert "Lyon" in user
        return LLM_CHANGED_DATES_CV

    result = generate_adapted_cv(
        STRUCTURED_ORIGINAL_CV,
        JOB,
        FULL_MATCH,
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    parsed = parse_adapted_cv(result)
    assert parsed.experiences
    job = parsed.experiences[0]
    assert job.title == "Ingénieure backend Python"
    assert job.period == "2022 - 2025"
    assert job.location == "Lyon"
    assert "2019" not in result
    assert "Django" in result


LLM_DROPPED_MISSION_CV = """
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
VILLE: Paris

## PROFIL
Développeuse Python spécialisée Django et APIs REST.

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS | Kubernetes

## EXPERIENCE
POSTE: Ingénieure backend Python
ENTREPRISE: Acme
PERIODE: 2019 - 2024
LIEU: Paris
- Conception d'APIs REST Django
"""


def test_generate_adapted_cv_restores_dropped_original_missions():
    captured: dict[str, str] = {}

    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        captured["system"] = system
        captured["user"] = user
        return LLM_DROPPED_MISSION_CV

    result = generate_adapted_cv(
        STRUCTURED_ORIGINAL_CV,
        JOB,
        FULL_MATCH,
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    parsed = parse_adapted_cv(result)
    bullets = parsed.experiences[0].bullets
    assert any("APIs REST" in bullet or "Django" in bullet for bullet in bullets)
    assert any("CI/CD" in bullet for bullet in bullets)
    assert "Conception d'APIs REST" in captured["user"] or "Missions d'origine" in captured["user"]
    assert "Reformule TOUTES les missions" in captured["system"] or "missions d'origine" in captured["system"].lower()


def test_generate_cover_letter_prompt_keeps_original_missions():
    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        assert "Conception d'APIs REST" in user
        assert "Mise en place CI/CD" in user
        assert "Reformule les missions" in system or "missions du CV" in system
        return (
            "Objet : candidature Développeuse Python — NovaTech\n\n"
            "Madame, Monsieur, développeuse Python experte Django, Docker et Kubernetes, "
            "je conçois des APIs REST et j'ai mis en place le CI/CD. Cordialement."
        )

    letter = generate_cover_letter(
        STRUCTURED_ORIGINAL_CV,
        JOB,
        FULL_MATCH,
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    assert "NovaTech" in letter
    assert "APIs REST" in letter or "CI/CD" in letter

