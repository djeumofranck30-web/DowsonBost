"""Generate cover letters and adapted CV content via LLM."""

from __future__ import annotations

from typing import Any, Callable

from cv_layout import build_cv_system_addon, cv_text_for_candidate, detect_job_family

COVER_LETTER_SYSTEM_PROMPT = """
Tu es un expert en recrutement francophone. Rédige une lettre de motivation personnalisée,
professionnelle et convaincante (250 à 400 mots), en français.

Structure :
- Objet / accroche liée au poste
- Paragraphe motivation + adéquation profil / offre
- Paragraphe compétences et expériences pertinentes (concret, pas de généralités vides)
- Paragraphe disponibilité / conclusion avec appel à l'action

Ton : professionnel, direct, sans formules creuses. Ne invente pas de diplômes ou d'expériences absentes du CV.
Retourne UNIQUEMENT le texte de la lettre (pas de JSON, pas de markdown).
"""

ADAPTED_CV_SYSTEM_PROMPT = """
Tu es un expert ATS et rédacteur de CV francophone.

Ta mission : produire un NOUVEAU CV complet, réécrit de zéro pour l'offre ciblée,
en t'appuyant sur le CV original du candidat et en appliquant OBLIGATOIREMENT
chaque point de la liste « Modifications ATS à appliquer ».

Règles strictes :
1. Chaque modification ATS listée doit être visible dans le CV final (reformulation, section, mot-clé, ordre).
2. Utilise exactement le « Titre CV recommandé » fourni en en-tête du document.
3. Priorise les expériences et compétences marquées « présentes » ou « partielles » dans l'analyse ATS.
4. Intègre les « mots-clés manquants » UNIQUEMENT si le candidat les possède réellement dans son parcours
   (sinon ne pas inventer — reformule plutôt ce qui existe déjà).
5. Reformule les missions des expériences pertinentes avec le vocabulaire de l'offre (sans mentir).
6. Ne invente JAMAIS de diplôme, entreprise, date, certification ou compétence absente du CV original.
7. C'est une réécriture complète (nouvelle structure, nouvelles formulations), pas un copier-coller du CV actuel.
8. Le document renvoyé est le CV FINAL, prêt à envoyer au recruteur.
   N'ajoute JAMAIS de section « Modifications appliquées », « Modifications à apporter au CV »,
   « MODIFICATIONS APPLIQUÉES » ni aucun journal de changements en fin de document.

Retourne UNIQUEMENT le CV (champs NOM/TITRE/EMAIL puis sections ## du template métier).
"""


def _job_block(job: dict[str, Any]) -> str:
    return (
        f"Titre offre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '')}\n"
        f"Description :\n{str(job.get('description', ''))[:4500]}"
    )


def _skills_list(items: Any) -> str:
    if not isinstance(items, list):
        return "—"
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return ", ".join(cleaned) if cleaned else "—"


def _match_analysis_block(match: dict[str, Any]) -> str:
    """Format ATS analysis for adapted CV generation."""
    skills = match.get("analyse_competences") or {}
    exp = match.get("analyse_experiences") or {}
    modifications = match.get("modifications_cv") or match.get("conseils") or []

    lines = [
        f"Titre CV recommandé : {match.get('titre_cv_recommande', '—')}",
        f"Score ATS global : {match.get('score_correspondance', '—')}%",
        f"Synthèse : {match.get('synthese_ats', '—')}",
        "",
        "Compétences présentes dans le CV : " + _skills_list(skills.get("presentes")),
        "Compétences partielles : " + _skills_list(skills.get("partielles")),
        "Compétences manquantes : " + _skills_list(skills.get("manquantes")),
        "Technos / outils offre : " + _skills_list(skills.get("offre_technos")),
        "Mots-clés ATS manquants dans le CV : " + _skills_list(match.get("mots_cles_manquants")),
        "",
        f"Niveau offre : {exp.get('niveau_offre', '—')} · Niveau CV : {exp.get('niveau_cv', '—')} · "
        f"Alignement : {exp.get('alignement_niveau', '—')}",
    ]

    exp_lines: list[str] = []
    for item in exp.get("experiences_pertinentes") or []:
        if not isinstance(item, dict):
            continue
        header = " — ".join(
            part for part in (item.get("poste"), item.get("duree"), item.get("secteur")) if part
        )
        if header:
            exp_lines.append(f"  • {header}")
            if item.get("missions_liees"):
                exp_lines.append(f"    Missions liées : {item['missions_liees']}")
    if exp_lines:
        lines.append("")
        lines.append("Expériences pertinentes pour cette offre :")
        lines.extend(exp_lines)

    ecarts = exp.get("ecarts") or []
    if ecarts:
        lines.append("")
        lines.append("Écarts identifiés : " + "; ".join(str(e) for e in ecarts[:5]))

    lines.append("")
    lines.append("Modifications ATS à appliquer (OBLIGATOIRE — une par une dans le CV réécrit) :")
    for idx, mod in enumerate(modifications[:10], start=1):
        lines.append(f"  {idx}. {mod}")

    if not modifications:
        lines.append("  (Aucune — adapte quand même titre, profil et mots-clés de l'offre.)")

    return "\n".join(lines)


def _candidate_block(
    cv_text: str,
    match: dict[str, Any],
    user_profile: dict[str, Any],
) -> str:
    name = user_profile.get("full_name", "")
    target = user_profile.get("target_job_title", "")
    return (
        f"Nom candidat : {name}\n"
        f"Poste visé (profil) : {target}\n\n"
        f"=== ANALYSE ATS POUR CETTE OFFRE ===\n"
        f"{_match_analysis_block(match)}\n\n"
        f"=== CV ORIGINAL (source de vérité — ne pas inventer au-delà) ===\n"
        f"{cv_text[:12000]}"
    )


def generate_cover_letter(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
) -> str:
    """Generate a tailored cover letter."""
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"=== OFFRE CIBLÉE ===\n{_job_block(job)}\n\n"
        "Rédige la lettre de motivation."
    )
    return llm_call(COVER_LETTER_SYSTEM_PROMPT, user_prompt).strip()


def generate_adapted_cv(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
) -> str:
    """Rewrite the CV for one offer using the matching profession template."""
    family = detect_job_family(job, match)
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"=== OFFRE CIBLÉE ===\n{_job_block(job)}\n\n"
        "Réécris un CV complet et nouveau pour cette offre. "
        "Applique TOUTES les modifications ATS listées ci-dessus DANS le corps du CV "
        "(reformulations, mots-clés, ordre des sections). "
        "N'ajoute aucune section listant les modifications : le CV s'arrête après les rubriques métier."
    )
    raw = llm_call(
        ADAPTED_CV_SYSTEM_PROMPT + build_cv_system_addon(family),
        user_prompt,
        max_tokens=4800,
    ).strip()
    return cv_text_for_candidate(raw)
