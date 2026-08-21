"""Generate cover letters and adapted CV content via LLM."""

from __future__ import annotations

from typing import Any, Callable

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
Tu es un expert ATS et recrutement. Adapte le CV du candidat pour maximiser la correspondance
avec l'offre d'emploi ciblée, en français.

Règles :
- Conserve les faits réels du CV (ne pas inventer)
- Réorganise et reformule pour mettre en avant les compétences et expériences pertinentes pour l'offre
- Intègre naturellement les mots-clés manquants identifiés quand le candidat les possède réellement
- Format texte structuré : Titre CV, Profil (3 lignes), Compétences clés, Expériences (poste — entreprise — missions), Formation
- Longueur : équivalent 1 à 2 pages A4

Retourne UNIQUEMENT le texte du CV adapté (pas de JSON, pas de markdown).
"""


def _job_block(job: dict[str, Any]) -> str:
    return (
        f"Titre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '')}\n"
        f"Description :\n{str(job.get('description', ''))[:4000]}"
    )


def _candidate_block(
    cv_text: str,
    match: dict[str, Any],
    user_profile: dict[str, Any],
) -> str:
    name = user_profile.get("full_name", "")
    target = user_profile.get("target_job_title", "")
    missing = ", ".join(match.get("mots_cles_manquants") or [])
    synthesis = match.get("synthese_ats", "")
    return (
        f"Nom candidat : {name}\n"
        f"Poste visé : {target}\n"
        f"Synthèse ATS : {synthesis}\n"
        f"Mots-clés à valoriser si présents : {missing}\n\n"
        f"CV original :\n{cv_text[:10000]}"
    )


def generate_cover_letter(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[[str, str], str],
) -> str:
    """Generate a tailored cover letter."""
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"Offre ciblée :\n{_job_block(job)}\n\n"
        "Rédige la lettre de motivation."
    )
    return llm_call(COVER_LETTER_SYSTEM_PROMPT, user_prompt).strip()


def generate_adapted_cv(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[[str, str], str],
) -> str:
    """Generate an ATS-optimized CV variant for one offer."""
    modifications = match.get("modifications_cv") or match.get("conseils") or []
    mods_text = "\n".join(f"- {m}" for m in modifications[:8])
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"Offre ciblée :\n{_job_block(job)}\n\n"
        f"Modifications ATS recommandées :\n{mods_text}\n\n"
        "Produis le CV adapté complet."
    )
    return llm_call(ADAPTED_CV_SYSTEM_PROMPT, user_prompt).strip()
