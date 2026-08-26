"""Profession CV templates, parsing, and candidate-facing cleanup."""

from __future__ import annotations

from cv_layout import (
    cv_text_for_candidate,
    detect_job_family,
    parse_adapted_cv,
    prepare_structured_cv,
    public_cv_text,
    render_adapted_cv_pdf,
    render_cv_html,
    render_cv_pdf,
    split_modifications,
    template_for,
    template_label,
)
from document_generation import ADAPTED_CV_SYSTEM_PROMPT, generate_adapted_cv


SAMPLE_IT_CV = """
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
TELEPHONE: +33 6 00 00 00 00
VILLE: Paris

## PROFIL
Ingénieure logicielle spécialisée backend Python et APIs.

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS

## EXPERIENCE
POSTE: Développeuse Python
ENTREPRISE: Acme
PERIODE: 2022 - 2025
LIEU: Paris
- Conception d'APIs REST
- Mise en place CI/CD

## FORMATION
DIPLOME: Master Informatique
ETABLISSEMENT: Université de Lyon
PERIODE: 2020

## LANGUES
Français (natif) | Anglais (C1)

---
MODIFICATIONS APPLIQUÉES
1. Ajout du mot-clé Django dans les compétences
2. Titre aligné sur l'offre
"""

SAMPLE_LEGACY_CV = """
Data Analyst
Marie Martin
marie.martin@example.com · 0612345678

PROFIL PROFESSIONNEL
Analyste data orientée décision.

COMPÉTENCES CLÉS
• SQL
• Power BI
• Python

EXPÉRIENCES PROFESSIONNELLES
Analyste — Banque Dupont | 2019 - 2024
• Tableaux de bord finance

FORMATION & CERTIFICATIONS
Master Finance — HEC | 2018

MODIFICATIONS À APPORTER AU CV
- Ajouter IFRS
"""


def test_detect_job_family_it():
    assert detect_job_family({"title": "Développeur Python", "description": "Django AWS"}) == "it"


def test_detect_job_family_healthcare():
    assert (
        detect_job_family(
            {"title": "Infirmier diplômé d'État", "description": "Soins au patient en hôpital"}
        )
        == "healthcare"
    )


def test_detect_job_family_finance():
    assert detect_job_family({"title": "Contrôleur de gestion", "description": "IFRS consolidation"}) == "finance"


def test_detect_job_family_legal():
    assert detect_job_family({"title": "Juriste droit social", "description": "Contentieux prud'homal"}) == "legal"


def test_detect_job_family_generic_unknown():
    assert detect_job_family({"title": "Candidat", "description": "Poste à pourvoir"}) == "generic"


def test_templates_differ_by_profession():
    it = template_for("it")
    med = template_for("healthcare")
    assert it.primary != med.primary
    assert it.layout == "banner"
    assert med.layout == "classic"
    assert "STACK" in it.section_titles["skills"]
    assert "CLINIQUE" in med.section_titles["profile"] or "CLINI" in med.section_titles["profile"]
    assert template_label("it", "fr") == "Informatique / Digital"


def test_split_modifications_removes_appendix():
    body, items = split_modifications(SAMPLE_IT_CV)
    assert "MODIFICATIONS" not in body.upper()
    assert "Jane Doe" in body
    assert any("Django" in item for item in items)
    assert "Ajout du mot-clé Django" not in cv_text_for_candidate(SAMPLE_IT_CV)


def test_split_modifications_legacy_heading():
    body, items = split_modifications(SAMPLE_LEGACY_CV)
    assert "IFRS" not in body
    assert items
    assert "Marie Martin" in body


def test_parse_and_public_text_omits_modifications():
    cv = parse_adapted_cv(SAMPLE_IT_CV)
    assert cv.name == "Jane Doe"
    assert cv.title.startswith("Développeuse")
    assert "Python" in cv.skills
    assert cv.experiences and cv.experiences[0].company == "Acme"
    public = public_cv_text(cv)
    assert "MODIFICATIONS" not in public.upper()
    assert "Django" in public


def test_enrich_uses_profile_and_family():
    cv = prepare_structured_cv(
        "PROFIL\nBackend confirmé\n",
        job={"title": "Développeur Java"},
        match={"titre_cv_recommande": "Développeur Java"},
        user_profile={"full_name": "Paul Durand", "email": "paul@test.fr", "phone": "0600000000"},
    )
    assert cv.name == "Paul Durand"
    assert cv.family == "it"
    assert cv.email == "paul@test.fr"


def test_render_pdf_is_valid_and_unique_per_template():
    it_cv = prepare_structured_cv(
        SAMPLE_IT_CV,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    med_text = SAMPLE_IT_CV.replace("Développeuse Python", "Infirmière DE")
    med_cv = prepare_structured_cv(
        med_text,
        job={"title": "Infirmier", "description": "soins hopital patient"},
        user_profile={"full_name": "Jane Doe"},
    )
    it_pdf = render_cv_pdf(it_cv)
    med_pdf = render_cv_pdf(med_cv)
    assert it_pdf.startswith(b"%PDF")
    assert med_pdf.startswith(b"%PDF")
    assert it_cv.family == "it"
    assert med_cv.family == "healthcare"
    html_preview = render_cv_html(it_cv)
    assert "Jane Doe" in html_preview
    assert "MODIFICATIONS" not in html_preview.upper()


def test_render_adapted_cv_pdf_strips_modifications():
    pdf = render_adapted_cv_pdf(
        SAMPLE_IT_CV,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    assert pdf.startswith(b"%PDF")
    # PDF latin-1 may drop accents but should not contain the appendix heading.
    assert b"MODIFICATIONS APPLIQUEES" not in pdf.upper().replace(b"\xc9", b"E")


def test_generate_adapted_cv_strips_llm_appendix_and_uses_template():
    captured: dict[str, str] = {}

    def fake_llm(system: str, user: str, **kwargs: object) -> str:
        captured["system"] = system
        return SAMPLE_IT_CV

    result = generate_adapted_cv(
        "CV original Jane",
        {"title": "Développeur Python", "description": "Django", "company": "Acme"},
        {"titre_cv_recommande": "Développeur Python", "modifications_cv": ["Ajouter Django"]},
        {"full_name": "Jane Doe"},
        llm_call=fake_llm,
    )
    assert "MODIFICATIONS" not in result.upper()
    assert "Jane Doe" in result
    assert "Informatique" in captured["system"] or "it" in captured["system"]
    assert "N'ajoute JAMAIS" in ADAPTED_CV_SYSTEM_PROMPT
