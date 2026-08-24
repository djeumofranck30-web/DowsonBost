"""CV ↔ job matching normalization and scoring."""

from __future__ import annotations

import re
from typing import Any


def as_str_list(value: Any, *, max_items: int = 20) -> list[str]:
    """Coerce LLM output to a clean string list."""
    if isinstance(value, str):
        items = [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        items = []
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:max_items]


def normalize_score(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def normalize_skills_analysis(raw: Any) -> dict[str, list[str]]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "cv_techniques": as_str_list(data.get("cv_techniques")),
        "cv_transversales": as_str_list(data.get("cv_transversales")),
        "cv_outils": as_str_list(data.get("cv_outils")),
        "cv_certifications": as_str_list(data.get("cv_certifications")),
        "cv_langages": as_str_list(data.get("cv_langages")),
        "offre_obligatoires": as_str_list(data.get("offre_obligatoires")),
        "offre_souhaitees": as_str_list(data.get("offre_souhaitees")),
        "offre_technos": as_str_list(data.get("offre_technos")),
        "presentes": as_str_list(data.get("presentes")),
        "partielles": as_str_list(data.get("partielles")),
        "manquantes": as_str_list(data.get("manquantes")),
    }


def normalize_experience_analysis(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    relevant: list[dict[str, str]] = []
    for item in (data.get("experiences_pertinentes") or [])[:6]:
        if isinstance(item, dict):
            relevant.append(
                {
                    "poste": str(item.get("poste", "")).strip(),
                    "duree": str(item.get("duree", "")).strip(),
                    "missions_liees": str(item.get("missions_liees", "")).strip(),
                    "secteur": str(item.get("secteur", "")).strip(),
                }
            )
        elif isinstance(item, str) and item.strip():
            relevant.append(
                {"poste": item.strip(), "duree": "", "missions_liees": "", "secteur": ""}
            )
    return {
        "niveau_offre": str(data.get("niveau_offre", "")).strip(),
        "niveau_cv": str(data.get("niveau_cv", "")).strip(),
        "alignement_niveau": str(data.get("alignement_niveau", "")).strip(),
        "experiences_pertinentes": relevant,
        "ecarts": as_str_list(data.get("ecarts"), max_items=8),
    }


def compute_ats_score(data: dict[str, Any]) -> int:
    """Weighted ATS score from sub-scores when provided."""
    components = (
        ("score_competences", 0.40),
        ("score_experiences", 0.25),
        ("score_titre", 0.20),
        ("score_localisation", 0.15),
    )
    weighted_parts: list[tuple[int, float]] = []
    for key, weight in components:
        if data.get(key) is not None:
            weighted_parts.append((normalize_score(data.get(key)), weight))
    if len(weighted_parts) == len(components):
        return round(sum(score * weight for score, weight in weighted_parts))
    return normalize_score(data.get("score_correspondance"))


def normalize_match_result(
    data: dict[str, Any],
    job: dict[str, Any] | None = None,
    *,
    fallback: bool = False,
) -> dict[str, Any]:
    """Ensure a job-match payload has the expected ATS shape."""
    score = compute_ats_score(data)

    conseils_raw = data.get("conseils", [])
    if isinstance(conseils_raw, str):
        conseils = [conseils_raw]
    elif isinstance(conseils_raw, list):
        conseils = [str(c).strip() for c in conseils_raw if str(c).strip()]
    else:
        conseils = []
    while len(conseils) < 3:
        conseils.append(
            "Relancez l'analyse pour obtenir des conseils personnalisés sur cette offre."
        )
    conseils = conseils[:5]

    mods_raw = data.get("modifications_cv") or data.get("modifications") or []
    if isinstance(mods_raw, str):
        modifications = [mods_raw]
    elif isinstance(mods_raw, list):
        modifications = [str(m).strip() for m in mods_raw if str(m).strip()]
    else:
        modifications = []
    if not modifications:
        modifications = conseils[:5]
    modifications = modifications[:8]

    mots_raw = data.get("mots_cles_manquants", [])
    skills = normalize_skills_analysis(data.get("analyse_competences"))
    if not mots_raw and skills["manquantes"]:
        mots = skills["manquantes"][:8]
    else:
        mots = as_str_list(mots_raw, max_items=8)

    default_title = job.get("title", "Profil candidat") if job else "Profil candidat"
    titre = str(data.get("titre_cv_recommande") or default_title).strip()
    synthese = str(data.get("synthese_ats", "") or data.get("resume_ats", "")).strip()

    result: dict[str, Any] = {
        "score_correspondance": score,
        "score_competences": normalize_score(data.get("score_competences"), score),
        "score_experiences": normalize_score(data.get("score_experiences"), score),
        "score_titre": normalize_score(data.get("score_titre"), score),
        "score_localisation": normalize_score(data.get("score_localisation"), score),
        "titre_cv_recommande": titre,
        "synthese_ats": synthese,
        "analyse_competences": skills,
        "analyse_experiences": normalize_experience_analysis(data.get("analyse_experiences")),
        "mots_cles_manquants": mots,
        "modifications_cv": modifications,
        "conseils": conseils,
    }
    if fallback:
        result["_fallback"] = True
    return result


def fallback_match_result(job: dict[str, Any]) -> dict[str, Any]:
    """Minimal ATS match report when the LLM response cannot be parsed."""
    return normalize_match_result(
        {
            "score_correspondance": 50,
            "score_competences": 50,
            "score_experiences": 50,
            "score_titre": 50,
            "score_localisation": 50,
            "titre_cv_recommande": job.get("title", "Profil candidat"),
            "synthese_ats": "Analyse partielle — relancez l'analyse pour un rapport ATS complet.",
            "analyse_competences": {
                "manquantes": [],
                "presentes": [],
                "partielles": [],
            },
            "analyse_experiences": {
                "alignement_niveau": "indéterminé",
                "ecarts": ["Analyse expérience non disponible"],
            },
            "mots_cles_manquants": [],
            "modifications_cv": [
                "Relancez l'analyse après avoir vidé le cache pour un matching ATS détaillé.",
                "Alignez le titre de votre CV sur l'intitulé exact de l'offre.",
                "Reprenez les compétences techniques listées dans la description de l'offre.",
            ],
            "conseils": [
                "Analyse partielle — relancez l'analyse pour des conseils détaillés.",
                "Alignez le titre de votre CV sur l'intitulé exact de l'offre.",
                "Reprenez les compétences techniques listées dans la description.",
            ],
        },
        job,
        fallback=True,
    )
