"""Profession CV templates, parsing, and candidate-facing cleanup."""

from __future__ import annotations

from cv_layout import (
    clean_cv_bullet,
    cv_text_for_candidate,
    list_cv_templates,
    detect_job_family,
    merge_experience_missions,
    normalize_cover_letter,
    parse_adapted_cv,
    polish_structured_cv,
    prepare_structured_cv,
    public_cv_text,
    render_adapted_cv_pdf,
    render_cover_letter_pdf,
    render_cv_html,
    render_cv_pdf,
    restore_experience_dates_locations,
    serialize_locked_experiences,
    split_modifications,
    template_for,
    template_label,
    ats_section_title,
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
    assert detect_job_family({"title": "Employé", "description": "Mission à pourvoir"}) == "generic"


def test_everyday_job_titles_use_a_specific_template():
    cases = {
        "Vendeur H/F": "sales",
        "Vendeuse prêt-à-porter": "sales",
        "Commercial BtoB": "sales",
        "Commerciale itinérante": "sales",
        "Employé de magasin": "sales",
        "Employé de rayon": "sales",
        "Caissier / caissière": "sales",
        "Employé polyvalent": "sales",
        "Employé administratif": "office",
        "Secrétaire": "office",
        "Assistant de direction": "office",
        "Employé de bureau": "office",
        "Agent de sécurité": "security",
        "Coiffeur": "beauty",
        "Esthéticienne": "beauty",
        "Agent immobilier": "realestate",
        "Agent d'entretien": "facilities",
        "Électricien": "construction",
        "Cuisinier": "hospitality",
        "Serveur": "hospitality",
        "Chauffeur livreur": "logistics",
        "Comptable": "finance",
        "Infirmier": "healthcare",
        "Développeur": "it",
        "Conseiller clientèle": "customer",
        "Éducateur spécialisé": "social",
        "Jardinier": "facilities",
        "Agriculteur": "agriculture",
        "Coach sportif": "sports",
    }
    for title, family in cases.items():
        got = detect_job_family({"title": title, "description": ""})
        assert got == family, f"{title!r} -> {got!r}, expected {family!r}"


def test_all_registered_templates_are_complete():
    templates = list_cv_templates()
    families = {tpl.family for tpl in templates}
    assert "sales" in families
    assert "office" in families
    assert "generic" in families
    assert len(templates) >= 20
    for tpl in templates:
        assert tpl.section_order
        assert tpl.llm_sections
        assert tpl.label_fr


def test_templates_differ_by_profession():
    it = template_for("it")
    med = template_for("healthcare")
    assert it.primary != med.primary
    assert it.layout == "banner"
    assert med.layout == "classic"
    assert it.section_order[1] == "skills"  # hybride 2026 : compétences avant l'expérience
    assert med.section_order[1] == "education"  # santé France : diplômes d'État en tête
    assert ats_section_title("experience") == "EXPÉRIENCE PROFESSIONNELLE"
    assert ats_section_title("skills") == "COMPÉTENCES"
    assert template_label("it", "fr") == "Informatique / Digital"


def test_pdf_uses_ats_standard_headings():
    cv = prepare_structured_cv(
        SAMPLE_IT_CV,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    import fitz

    pdf = render_cv_pdf(cv)
    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "COMPÉTENCES" in text or "COMPETENCES" in text
    assert "EXPÉRIENCE PROFESSIONNELLE" in text or "EXPERIENCE PROFESSIONNELLE" in text
    assert "STACK" not in text
    assert "PROFIL CLINIQUE" not in text


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
    assert cv.title == "Développeur Java"


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
    assert "PERIODE" in captured["system"] or "dates" in captured["system"].lower()


def test_restore_experience_keeps_dates_and_place_but_adapted_title():
    original = parse_adapted_cv(
        """
NOM: Jane Doe
TITRE: Développeuse Python
## EXPERIENCE
POSTE: Développeuse Python
ENTREPRISE: Acme
PERIODE: 2022 - 2025
LIEU: Lyon
- APIs REST
"""
    )
    generated = parse_adapted_cv(
        """
NOM: Jane Doe
TITRE: Ingénieure backend
## EXPERIENCE
POSTE: Ingénieure backend Python
ENTREPRISE: Acme
PERIODE: 2020 - 2024
LIEU: Paris
- APIs REST Django
"""
    )
    restored = restore_experience_dates_locations(generated, original)
    job = restored.experiences[0]
    assert job.title == "Ingénieure backend Python"
    assert job.period == "2022 - 2025"
    assert job.location == "Lyon"
    assert job.company == "Acme"
    assert any("APIs REST" in bullet or "Django" in bullet for bullet in job.bullets)


def test_merge_keeps_reformulated_missions_and_restores_dropped_ones():
    merged = merge_experience_missions(
        [
            "Conception d'APIs REST Django pour les clients internes",
            "Participation aux code reviews hebdomadaires",
        ],
        [
            "APIs REST",
            "CI/CD GitLab",
        ],
    )
    assert any("Django" in bullet for bullet in merged)
    assert any("CI/CD" in bullet for bullet in merged)
    assert any("code reviews" in bullet.lower() for bullet in merged)
    rest_like = [bullet for bullet in merged if "APIs REST" in bullet and "Django" not in bullet]
    assert rest_like == []


def test_merge_prefers_original_missions_over_extra_generated_ones():
    extras = [f"Mission inventée {index}" for index in range(8)]
    merged = merge_experience_missions(extras, ["Pilotage du support N2", "Formation des nouveaux arrivants"])
    assert "Pilotage du support N2" in merged
    assert "Formation des nouveaux arrivants" in merged


def test_restore_keeps_original_job_if_generated_dropped_it():
    original = parse_adapted_cv(
        """
NOM: Jane Doe
## EXPERIENCE
POSTE: Dev ACME
ENTREPRISE: ACME
PERIODE: 2021 - 2024
LIEU: Paris
- APIs REST

POSTE: Stage Beta
ENTREPRISE: Beta
PERIODE: 2020
LIEU: Lyon
- Support utilisateurs
"""
    )
    generated = parse_adapted_cv(
        """
NOM: Jane Doe
## EXPERIENCE
POSTE: Développeur backend
ENTREPRISE: ACME
PERIODE: 2021 - 2024
LIEU: Paris
- Conception d'APIs REST
"""
    )
    restored = restore_experience_dates_locations(generated, original)
    assert len(restored.experiences) == 2
    assert restored.experiences[1].company == "Beta"
    assert "Support utilisateurs" in restored.experiences[1].bullets


def test_locked_experiences_prompt_lists_original_missions():
    original = parse_adapted_cv(
        """
## EXPERIENCE
POSTE: Dev
ENTREPRISE: ACME
PERIODE: 2021-2024
LIEU: Paris
- APIs REST
- CI/CD GitLab
"""
    )
    text = serialize_locked_experiences(original.experiences)
    assert "APIs REST" in text
    assert "CI/CD GitLab" in text
    assert "Ne les supprime pas" in text
    assert "Missions d'origine" in text


def _pdf_page_count(pdf_bytes: bytes) -> int:
    import fitz

    return fitz.open(stream=pdf_bytes, filetype="pdf").page_count


def test_generated_cv_pdf_fits_on_one_a4_page():
    cv = prepare_structured_cv(
        SAMPLE_IT_CV,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    assert _pdf_page_count(render_cv_pdf(cv)) == 1


def test_long_generated_cv_pdf_stays_on_one_a4_page():
    bullets = "\n".join(
        f"- Conception et industrialisation d'APIs REST Django {index} avec tests et CI/CD"
        for index in range(1, 9)
    )
    jobs = []
    for year, company in ((2023, "Alpha"), (2020, "Beta"), (2017, "Gamma"), (2014, "Delta")):
        jobs.append(
            f"POSTE: Ingénieur logiciel\nENTREPRISE: {company}\n"
            f"PERIODE: {year} - {year + 3}\nLIEU: Paris\n{bullets}\n"
        )
    text = f"""
NOM: Jane Doe
TITRE: Développeuse Python
EMAIL: jane@example.com
TELEPHONE: +33 6 00 00 00 00
VILLE: Paris

## PROFIL
Ingénieure backend Python spécialisée APIs, cloud et industrialisation. {"Parcours détaillé. " * 40}

## COMPETENCES
Python | Django | PostgreSQL | Docker | AWS | Kubernetes | Redis | Celery | React | TypeScript | CI/CD | Terraform

## EXPERIENCE
{"".join(jobs)}

## FORMATION
DIPLOME: Master Informatique
ETABLISSEMENT: Université de Lyon
PERIODE: 2012 - 2014

## LANGUES
Français (natif) | Anglais (C1)
"""
    cv = prepare_structured_cv(
        text,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    pdf = render_cv_pdf(cv)
    assert pdf.startswith(b"%PDF")
    assert _pdf_page_count(pdf) == 1


def test_merge_drops_near_duplicate_original_and_rewrite():
    merged = merge_experience_missions(
        ["Conception d'APIs REST Django pour les clients internes"],
        ["APIs REST", "Conception d'APIs REST"],
    )
    assert len(merged) == 1
    assert "Django" in merged[0]


def test_polish_merges_duplicate_jobs_and_skills():
    cv = parse_adapted_cv(
        """
NOM: Jane Doe
## COMPETENCES
Python | python | Django
## EXPERIENCE
POSTE: Développeuse
ENTREPRISE: Acme
PERIODE: 2022 - 2025
- APIs REST
POSTE: Ingénieure backend
ENTREPRISE: Acme
PERIODE: 2022 - 2025
- Conception d'APIs REST Django
"""
    )
    polished = polish_structured_cv(cv)
    assert len(polished.experiences) == 1
    assert len(polished.experiences[0].bullets) == 1
    assert "Django" in polished.experiences[0].bullets[0]
    folded_skills = [item.lower() for item in polished.skills]
    assert folded_skills.count("python") == 1


def test_html_preview_justifies_phrases():
    cv = prepare_structured_cv(
        SAMPLE_IT_CV,
        job={"title": "Développeur Python"},
        user_profile={"full_name": "Jane Doe"},
    )
    preview = render_cv_html(cv)
    assert "text-align:justify" in preview
    assert "Jane Doe" in preview
    layout = (__import__("pathlib").Path(__file__).resolve().parents[1] / "cv_layout.py").read_text(
        encoding="utf-8"
    )
    assert 'align="J"' in layout
    assert "sans doublon" in layout or "Une seule puce par mission" in layout


def test_normalize_cover_letter_splits_single_paragraph_and_unescapes():
    wall = (
        r"Objet : Candidature — ISO 27001\n\nMadame, Monsieur,\n\n"
        "Actuellement étudiant en Master 2 je candidate chez Galadrim. "
        "Mon profil combine Windows, Linux et ISO 27001. "
        "Chez mon employeur actuel j'ai déployé un serveur sécurisé. "
        "En tant que technicien j'ai configuré des VLAN. "
        "Mon stage Java a renforcé l'automatisation. "
        "Je suis autonome et disponible immédiatement. "
        "Cordialement, Jordan Wankam"
    )
    letter = normalize_cover_letter(
        wall,
        job={"title": "Alternance Chargé(e) de projet ISO 27001", "company": "Galadrim"},
        user_profile={"full_name": "Jordan Wankam"},
    )
    assert "\\n" not in letter
    assert "Madame, Monsieur," in letter
    assert "Cordialement," in letter
    parts = [part for part in letter.split("\n\n") if part.strip()]
    assert len(parts) >= 5
    assert any(part.startswith("Objet") for part in parts)


def test_cover_letter_pdf_is_one_page_and_not_a_single_block():
    letter = normalize_cover_letter(
        "Madame, Monsieur, je candidate au poste. "
        "J'ai travaillé sur ISO 27001 et la gouvernance. "
        "J'ai déployé un firewall et rédigé des politiques. "
        "Je reste disponible pour un entretien. Cordialement.",
        job={"title": "Chargé de projet ISO 27001", "company": "Galadrim"},
        user_profile={"full_name": "Jordan Wankam", "email": "jordan@test.fr"},
    )
    pdf = render_cover_letter_pdf(
        letter,
        job={"title": "Chargé de projet ISO 27001", "company": "Galadrim"},
        user_profile={"full_name": "Jordan Wankam", "email": "jordan@test.fr"},
    )
    assert pdf.startswith(b"%PDF")
    assert _pdf_page_count(pdf) == 1
    import fitz

    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "Madame, Monsieur" in text
    assert "Cordialement" in text
    assert text.count("\n") >= 8


def test_clean_cv_bullet_strips_word_dingbat_and_question_mark():
    from cv_layout import normalize_extracted_cv_text

    assert clean_cv_bullet("?Déploiement TLS via PKI interne") == "Déploiement TLS via PKI interne"
    assert clean_cv_bullet("? Rédaction de la documentation") == "Rédaction de la documentation"
    assert clean_cv_bullet("\uf0b7Configuration des VLAN") == "Configuration des VLAN"
    assert clean_cv_bullet("● Mise en place de Nagios") == "Mise en place de Nagios"
    assert clean_cv_bullet("- Conception d'APIs REST") == "Conception d'APIs REST"
    raw = (
        "Stagiaire Administrateur\n"
        "\uf0b7Déploiement TLS via PKI interne\n"
        "?Rédaction de la documentation\n"
    )
    cleaned = normalize_extracted_cv_text(raw)
    assert "?Déploiement" not in cleaned
    assert "?Rédaction" not in cleaned
    assert "Déploiement TLS via PKI interne" in cleaned
    assert "Rédaction de la documentation" in cleaned


def test_parse_and_html_drop_leading_question_marks_on_missions():
    text = """
NOM: Jordan
TITRE: Administrateur systèmes
## EXPERIENCE
POSTE: Stagiaire Administrateur systèmes et réseaux
ENTREPRISE: Thales
PERIODE: 2024
- ?Déploiement TLS via PKI interne
- \uf0b7Rédaction de la documentation
- ●Mise en réseau LAN
"""
    parsed = parse_adapted_cv(text)
    bullets = parsed.experiences[0].bullets
    assert bullets
    assert all(not item.startswith("?") for item in bullets)
    assert "Déploiement TLS via PKI interne" in bullets
    assert "Rédaction de la documentation" in bullets
    html_preview = render_cv_html(parsed)
    assert "?Déploiement" not in html_preview
    assert "?Rédaction" not in html_preview
    assert "Déploiement TLS via PKI interne" in html_preview


def test_restore_missions_strips_question_marks_from_original():
    generated = parse_adapted_cv(
        """
NOM: Jordan
TITRE: Administrateur
## EXPERIENCE
POSTE: Stagiaire
ENTREPRISE: Thales
PERIODE: 2024
- Configuration VLAN
"""
    )
    original = parse_adapted_cv(
        """
NOM: Jordan
TITRE: Administrateur
## EXPERIENCE
POSTE: Stagiaire
ENTREPRISE: Thales
PERIODE: 2024
- ?Déploiement TLS via PKI interne
- ?Rédaction de la documentation
"""
    )
    restored = restore_experience_dates_locations(generated, original)
    blob = " ".join(restored.experiences[0].bullets)
    assert "?" not in blob
    assert "Déploiement TLS via PKI interne" in blob
    assert "Rédaction de la documentation" in blob

