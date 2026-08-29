"""Generate cover letters and adapted CV content via LLM."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from cv_layout import build_cv_system_addon, cv_text_for_candidate, detect_job_family

MAX_ALIGNMENT_REWRITES = 2

_STOPWORDS = {
    "alors",
    "avec",
    "dans",
    "dont",
    "etre",
    "fait",
    "leur",
    "leurs",
    "mais",
    "pour",
    "plus",
    "sans",
    "sous",
    "tout",
    "tous",
    "toutes",
    "une",
    "des",
    "les",
    "sur",
    "par",
    "pas",
    "que",
    "qui",
    "aux",
    "du",
    "de",
    "la",
    "le",
    "un",
    "et",
    "ou",
    "en",
    "au",
    "ce",
    "cet",
    "cette",
    "ces",
    "il",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "your",
    "you",
    "ajouter",
    "mettre",
    "integrer",
    "reformuler",
    "indiquer",
    "mentionner",
    "utiliser",
    "appliquer",
    "avant",
    "apres",
    "aussi",
    "comme",
    "entre",
    "notre",
    "votre",
    "faire",
    "avoir",
    "tres",
    "bien",
    "moins",
    "chaque",
    "lors",
    "afin",
    "section",
    "competences",
    "competence",
    "experience",
    "experiences",
    "profil",
    "titre",
    "mot",
    "mots",
    "cle",
    "cles",
    "ats",
    "cv",
    "offre",
    "poste",
}

COVER_LETTER_SYSTEM_PROMPT = """
Tu es un expert en recrutement francophone. Rédige une lettre de motivation personnalisée,
professionnelle et convaincante (250 à 400 mots), en français, ALIGNÉE À 100 % SUR L'OFFRE.

Objectif : le recruteur doit retrouver dans la lettre le vocabulaire, le titre et les
exigences de l'annonce, tout en restant factuel par rapport au CV.

Structure :
- Objet / accroche liée au poste ET à l'entreprise (reprends l'intitulé exact de l'offre)
- Paragraphe motivation + adéquation profil / offre (reprends le titre CV recommandé)
- Paragraphe compétences : cite nommément les compétences présentes et partielles de l'analyse ATS
  et les mots-clés de l'offre que le candidat possède déjà
- Paragraphe expériences : reformule les missions pertinentes avec le vocabulaire de l'annonce
- Conclusion / disponibilité avec appel à l'action

Règles :
- Applique l'intention de CHAQUE « Modification ATS » (mots-clés, angle, priorités) dans le texte.
- Ne invente pas de diplômes, employeurs, dates, certifications ou outils absents du CV original.
- Si un mot-clé de l'offre correspond à une mission déjà décrite, utilise le mot-clé de l'offre.
- Retourne UNIQUEMENT le texte de la lettre (pas de JSON, pas de markdown).
"""

ADAPTED_CV_SYSTEM_PROMPT = """
Tu es un expert ATS et rédacteur de CV francophone.

Ta mission : produire un NOUVEAU CV complet, réécrit de zéro, qui correspond à 100 %
à l'offre ciblée : un ATS doit y retrouver le titre recommandé, toutes les compétences
présentes/partielles, et l'effet de CHAQUE modification ATS listée.

Règles strictes :
1. Chaque modification ATS listée doit être visible dans le CV final (reformulation, section, mot-clé, ordre).
2. Le champ TITRE doit être exactement le « Titre CV recommandé ».
3. Place en tête les expériences et compétences marquées « présentes » ou « partielles ».
4. Intègre TOUS les mots-clés ATS et technos de l'offre dès qu'ils correspondent à une compétence
   réelle, même partielle, du CV original (reformule la mission avec le vocabulaire de l'annonce).
5. Reformule les missions des expériences pertinentes avec le vocabulaire EXACT de l'offre.
6. Ne invente JAMAIS de diplôme, entreprise, date, certification ou outil jamais utilisé.
7. Réécriture complète (nouvelle structure, nouvelles formulations), pas un copier-coller.
8. Document FINAL prêt à envoyer (norme France 2026 : une colonne, titres ATS classiques).
   N'ajoute JAMAIS de section « Modifications appliquées », « Modifications à apporter au CV »,
   « MODIFICATIONS APPLIQUÉES » ni aucun journal de changements.

Retourne UNIQUEMENT le CV (champs NOM/TITRE/EMAIL puis sections ## du template métier).
"""


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _distinctive_tokens(text: str, *, min_len: int = 4) -> list[str]:
    folded = _fold(text)
    tokens = re.findall(r"[a-z0-9][a-z0-9+.#/-]{1,}", folded)
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = token.strip(".-/")
        if len(cleaned) < min_len or cleaned in _STOPWORDS or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _as_terms(items: Any) -> list[str]:
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, list):
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        key = _fold(text)
        if key in seen:
            continue
        seen.add(key)
        terms.append(text)
    return terms


def _token_in_document(token: str, folded_document: str) -> bool:
    if token in folded_document:
        return True
    if len(token) >= 6:
        return token[:6] in folded_document
    return False


def _term_present(term: str, folded_document: str) -> bool:
    tokens = _distinctive_tokens(term, min_len=3)
    if not tokens:
        folded = _fold(term).strip()
        return bool(folded) and folded in folded_document
    if len(tokens) == 1 and len(tokens[0]) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(tokens[0])}(?![a-z0-9])", folded_document))
    return all(_token_in_document(token, folded_document) for token in tokens)


def collect_alignment_terms(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    """Terms the generated CV/letter must contain to match the offer."""
    skills = match.get("analyse_competences") or {}
    original_fold = _fold(cv_text)
    required: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        key = _fold(term)
        if not key or key in seen:
            return
        seen.add(key)
        required.append(term)

    for term in _as_terms(skills.get("presentes")) + _as_terms(skills.get("partielles")):
        _add(term)
    for term in (
        _as_terms(skills.get("offre_technos"))
        + _as_terms(skills.get("offre_obligatoires"))
        + _as_terms(match.get("mots_cles_manquants"))
    ):
        if _term_present(term, original_fold):
            _add(term)

    title = str(match.get("titre_cv_recommande") or job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    job_title = str(job.get("title") or "").strip()
    modifications = _as_terms(match.get("modifications_cv") or match.get("conseils") or [])
    return {
        "title": title,
        "company": company,
        "job_title": job_title,
        "required_terms": required[:24],
        "modifications": modifications[:10],
    }


def missing_alignment_gaps(
    document: str,
    alignment: dict[str, Any],
    *,
    kind: str = "cv",
) -> list[str]:
    """Human-readable gaps still missing from a generated document."""
    folded = _fold(document)
    gaps: list[str] = []
    title = str(alignment.get("title") or "").strip()
    if title and not _term_present(title, folded):
        gaps.append(f"Titre recommandé absent : {title}")
    if kind == "letter":
        company = str(alignment.get("company") or "").strip()
        if company and len(company) >= 3 and not _term_present(company, folded):
            gaps.append(f"Entreprise absente : {company}")
        job_title = str(alignment.get("job_title") or "").strip()
        if job_title and job_title != title and not _term_present(job_title, folded):
            gaps.append(f"Intitulé d'offre absent : {job_title}")
    for term in alignment.get("required_terms") or []:
        if not _term_present(str(term), folded):
            gaps.append(f"Mot-clé / compétence ATS manquant : {term}")
    for index, modification in enumerate(alignment.get("modifications") or [], start=1):
        distinctive = [token for token in _distinctive_tokens(str(modification), min_len=5)]
        if not distinctive:
            continue
        hits = sum(1 for token in distinctive if _token_in_document(token, folded))
        needed = max(1, (len(distinctive) + 1) // 2)
        if hits < needed:
            gaps.append(f"Modification ATS {index} non visible : {modification}")
    return gaps[:12]


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
    lines.append("Modifications ATS à appliquer (OBLIGATOIRE — une par une, toutes visibles dans le document) :")
    for idx, mod in enumerate(modifications[:10], start=1):
        lines.append(f"  {idx}. {mod}")

    if not modifications:
        lines.append("  (Aucune liste — aligne quand même titre, profil et 100 % des mots-clés de l'offre déjà présents chez le candidat.)")

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


def _invoke_llm(
    llm_call: Callable[..., str],
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int | None = None,
) -> str:
    if max_tokens is None:
        return str(llm_call(system_prompt, user_prompt) or "").strip()
    try:
        return str(llm_call(system_prompt, user_prompt, max_tokens=max_tokens) or "").strip()
    except TypeError:
        return str(llm_call(system_prompt, user_prompt) or "").strip()


def _alignment_checklist(alignment: dict[str, Any], *, kind: str) -> str:
    lines = [
        "CHECKLIST D'ALIGNEMENT À 100 % (tout doit apparaître nommément dans le document) :",
        f"- Titre / intitulé : {alignment.get('title') or '—'}",
    ]
    if kind == "letter":
        lines.append(f"- Entreprise : {alignment.get('company') or '—'}")
        lines.append(f"- Offre : {alignment.get('job_title') or '—'}")
    lines.append(
        "- Compétences / mots-clés ATS : "
        + (", ".join(alignment.get("required_terms") or []) or "—")
    )
    modifications = alignment.get("modifications") or []
    if modifications:
        lines.append("- Modifications ATS (toutes, visibles dans le texte) :")
        for index, modification in enumerate(modifications, start=1):
            lines.append(f"  {index}. {modification}")
    return "\n".join(lines)


def _rewrite_instruction(kind: str, gaps: list[str]) -> str:
    label = "CV" if kind == "cv" else "lettre de motivation"
    gap_lines = "\n".join(f"- {gap}" for gap in gaps)
    return (
        f"Le {label} précédent n'est PAS encore aligné à 100 % sur l'offre. "
        f"Éléments encore absents :\n{gap_lines}\n\n"
        f"Réécris le {label} COMPLET (pas un diff) en intégrant TOUS ces éléments. "
        "Garde uniquement des faits présents dans le CV original."
    )


def _generate_aligned_document(
    *,
    kind: str,
    system_prompt: str,
    base_user_prompt: str,
    llm_call: Callable[..., str],
    alignment: dict[str, Any],
    max_tokens: int,
    postprocess: Callable[[str], str] | None = None,
) -> str:
    user_prompt = f"{base_user_prompt}\n\n{_alignment_checklist(alignment, kind=kind)}"
    text = _invoke_llm(llm_call, system_prompt, user_prompt, max_tokens=max_tokens)
    if postprocess:
        text = postprocess(text)
    for _attempt in range(MAX_ALIGNMENT_REWRITES):
        gaps = missing_alignment_gaps(text, alignment, kind=kind)
        if not gaps:
            break
        rewrite_prompt = (
            f"{base_user_prompt}\n\n{_alignment_checklist(alignment, kind=kind)}\n\n"
            f"=== DOCUMENT PRÉCÉDENT (incomplet) ===\n{text[:8000]}\n\n"
            f"{_rewrite_instruction(kind, gaps)}"
        )
        text = _invoke_llm(llm_call, system_prompt, rewrite_prompt, max_tokens=max_tokens)
        if postprocess:
            text = postprocess(text)
    return text


def generate_cover_letter(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    llm_call: Callable[..., str],
) -> str:
    """Generate a tailored cover letter aligned with the ATS analysis."""
    alignment = collect_alignment_terms(cv_text, job, match)
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"=== OFFRE CIBLÉE ===\n{_job_block(job)}\n\n"
        "Rédige la lettre de motivation. Elle doit coller à 100 % à cette offre : "
        "reprends le titre, l'entreprise, les compétences ATS présentes/partielles "
        "et l'intention de chaque modification ATS, sans inventer de faits."
    )
    return _generate_aligned_document(
        kind="letter",
        system_prompt=COVER_LETTER_SYSTEM_PROMPT,
        base_user_prompt=user_prompt,
        llm_call=llm_call,
        alignment=alignment,
        max_tokens=1600,
    )


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
    alignment = collect_alignment_terms(cv_text, job, match)
    user_prompt = (
        f"{_candidate_block(cv_text, match, user_profile)}\n\n"
        f"=== OFFRE CIBLÉE ===\n{_job_block(job)}\n\n"
        "Réécris un CV complet et nouveau, aligné à 100 % sur cette offre. "
        "Le champ TITRE = titre CV recommandé. "
        "Applique TOUTES les modifications ATS DANS le corps du CV "
        "(reformulations, mots-clés, ordre des sections). "
        "N'ajoute aucune section listant les modifications : le CV s'arrête après les rubriques métier."
    )
    return _generate_aligned_document(
        kind="cv",
        system_prompt=ADAPTED_CV_SYSTEM_PROMPT + build_cv_system_addon(family),
        base_user_prompt=user_prompt,
        llm_call=llm_call,
        alignment=alignment,
        max_tokens=4800,
        postprocess=cv_text_for_candidate,
    )
