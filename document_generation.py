"""Generate cover letters and adapted CV content via LLM."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from cv_layout import (
    build_cv_system_addon,
    cv_text_for_candidate,
    detect_job_family,
    labeled_cv_text,
    parse_adapted_cv,
    restore_experience_dates_locations,
    serialize_locked_experiences,
)

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
- Paragraphe expériences : reformule les missions du CV ANALYSÉ avec le vocabulaire de l'annonce.
  N'oublie aucune mission importante de ce CV. Tu peux en citer une supplémentaire si l'offre
  l'exige et que c'est cohérent avec le parcours réel.
  Tu peux adapter le TITRE du poste ; recopie EXACTEMENT les dates et le lieu du CV original.
- Conclusion / disponibilité avec appel à l'action

Règles :
- Applique l'intention de CHAQUE « Modification ATS » (mots-clés, angle, priorités) dans le texte.
- Cite nommément les compétences de l'offre (y compris une techno exigée absente du CV original,
  uniquement comme compétence, sans inventer un poste).
- Reformule les missions du CV d'origine (celui de l'analyse) ; ne les néglige pas.
- Tu peux ajouter une mission seulement si elle reflète un travail déjà présent ou fortement
  impliqué dans ce CV, pour coller à l'offre — pas de fiction.
- Ne invente pas de diplômes, employeurs, dates ou certifications.
- Ne change JAMAIS les dates ni le lieu d'une expérience personnelle (ville, période).
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
3. Réécris ENTIÈREMENT la section ## COMPETENCES : en tête, TOUTES les compétences
   et technos de l'offre (obligatoires, stack, mots-clés ATS), avec les LIBELLÉS EXACTS
   de l'annonce, séparées par « | ». Si une techno est dans l'offre mais pas dans le CV
   original, AJOUTE-LA quand même dans cette section (c'est la seule invention autorisée :
   le mot-clé, pas un faux job). Ensuite, les autres compétences réelles du CV original.
4. Intègre les synonymes de l'offre (JS → JavaScript) et les mots-clés manquants.
5. Missions du CV analysé :
   - Reformule TOUTES les missions d'origine avec le vocabulaire EXACT de l'offre (ne les supprime pas).
   - Tu PEUX ajouter 1 à 3 missions supplémentaires SI elles correspondent à un travail réel
     du CV original (ou fortement impliqué), pour coller à l'offre.
   - N'invente pas une mission entière autour d'une techno absente du parcours : elle va dans COMPETENCES.
   - Tu PEUX adapter le champ POSTE (titre) pour coller à l'offre.
   - Tu NE DOIS PAS modifier PERIODE (dates) ni LIEU, ni l'entreprise : recopie-les tels quels.
6. Ne invente JAMAIS de diplôme, entreprise, date, lieu ou certification.
7. Réécriture complète (nouvelle structure, nouvelles formulations), pas un copier-coller.
8. Document FINAL prêt à envoyer (norme France 2026 : UNE page A4, une colonne, titres ATS classiques).
   Profil court (3-4 lignes). Missions en puces d'une ligne, sans phrases longues.
   N'ajoute JAMAIS de section « Modifications appliquées », « Modifications à apporter au CV »,
   « MODIFICATIONS APPLIQUÉES » ni aucun journal de changements.

Retourne UNIQUEMENT le CV (champs NOM/TITRE/EMAIL puis sections ## du template métier).
"""


_SKILL_ALIASES = {
    "javascript": ("js", "nodejs", "node.js", "node"),
    "typescript": ("ts",),
    "postgresql": ("postgres", "psql", "postgre"),
    "kubernetes": ("k8s", "kube"),
    "continuous integration": ("ci/cd", "cicd"),
    "ci/cd": ("cicd", "continuous integration"),
    "rest": ("api rest", "apis rest", "restful"),
    "react": ("reactjs", "react.js"),
    "vue": ("vuejs", "vue.js"),
    "power bi": ("powerbi",),
    "excel": ("microsoft excel",),
}


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


def _candidate_has_term(term: str, original_fold: str) -> bool:
    """True if the original CV already contains this skill or a known alias."""
    if _term_present(term, original_fold):
        return True
    folded = _fold(term).strip()
    aliases = _SKILL_ALIASES.get(folded, ())
    if any(alias in original_fold for alias in aliases):
        return True
    for canonical, alias_list in _SKILL_ALIASES.items():
        if folded == canonical or folded in alias_list:
            if canonical in original_fold or any(alias in original_fold for alias in alias_list):
                return True
    return False


def _is_skill_label(term: str) -> bool:
    text = str(term or "").strip()
    if len(text) < 2 or len(text) > 48:
        return False
    if text.count(" ") > 5:
        return False
    lowered = _fold(text)
    if lowered.startswith(("ajouter ", "mettre ", "reformuler ", "indiquer ")):
        return False
    return True


def adapted_competences(
    cv_text: str,
    match: dict[str, Any],
) -> list[str]:
    """Offer-worded skills, including offer technologies missing from the original CV."""
    skills = match.get("analyse_competences") or {}
    original_fold = _fold(cv_text)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        text = str(term or "").strip()
        if not _is_skill_label(text):
            return
        key = _fold(text)
        if key in seen:
            return
        seen.add(key)
        ordered.append(text)

    for term in (
        _as_terms(skills.get("offre_obligatoires"))
        + _as_terms(skills.get("offre_technos"))
        + _as_terms(match.get("mots_cles_manquants"))
        + _as_terms(skills.get("manquantes"))
    ):
        _add(term)
    for term in _as_terms(skills.get("presentes")) + _as_terms(skills.get("partielles")):
        _add(term)
    for term in _as_terms(skills.get("cv_outils")) + _as_terms(skills.get("cv_techniques")):
        if _candidate_has_term(term, original_fold):
            _add(term)
    return ordered[:24]


def _competences_section(document: str) -> str:
    found = re.search(
        r"^##\s*competences?\b(.*?)(?=^##\s|\Z)",
        document or "",
        flags=re.I | re.M | re.S,
    )
    return found.group(1) if found else ""


def collect_alignment_terms(
    cv_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    """Terms the generated CV/letter must contain to match the offer."""
    skills = match.get("analyse_competences") or {}
    adapted_skills = adapted_competences(cv_text, match)
    required: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        key = _fold(term)
        if not key or key in seen:
            return
        seen.add(key)
        required.append(term)

    for term in adapted_skills:
        _add(term)
    for term in _as_terms(skills.get("presentes")) + _as_terms(skills.get("partielles")):
        _add(term)
    for term in (
        _as_terms(skills.get("offre_technos"))
        + _as_terms(skills.get("offre_obligatoires"))
        + _as_terms(match.get("mots_cles_manquants"))
        + _as_terms(skills.get("manquantes"))
    ):
        if _is_skill_label(term):
            _add(term)

    title = str(match.get("titre_cv_recommande") or job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    job_title = str(job.get("title") or "").strip()
    modifications = _as_terms(match.get("modifications_cv") or match.get("conseils") or [])
    return {
        "title": title,
        "company": company,
        "job_title": job_title,
        "adapted_skills": adapted_skills,
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
    if kind == "cv":
        skill_block = _competences_section(document)
        skill_haystack = _fold(skill_block) if skill_block.strip() else folded
        adapted_skills = alignment.get("adapted_skills") or []
        if adapted_skills and not skill_block.strip():
            gaps.append(
                "Section ## COMPETENCES absente — réécris-la avec les compétences adaptées à l'offre."
            )
        for term in adapted_skills:
            if not _term_present(str(term), skill_haystack):
                gaps.append(f"Compétence absente de ## COMPETENCES (libellé offre) : {term}")
    else:
        for term in alignment.get("adapted_skills") or alignment.get("required_terms") or []:
            if not _term_present(str(term), folded):
                gaps.append(f"Compétence ATS absente de la lettre : {term}")
    for term in alignment.get("required_terms") or []:
        if kind == "cv" and term in (alignment.get("adapted_skills") or []):
            continue
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


def _locked_experience_block(cv_text: str) -> str:
    source = parse_adapted_cv(cv_text)
    return serialize_locked_experiences(source.experiences)


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
        f"{_locked_experience_block(cv_text)}\n\n"
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
    adapted = alignment.get("adapted_skills") or alignment.get("required_terms") or []
    if adapted and kind == "cv":
        lines.append(
            "- Section ## COMPETENCES (libellés EXACTS de l'offre, dans cet ordre, séparés par | ) : "
            + " | ".join(adapted)
        )
    elif adapted:
        lines.append(
            "- Compétences à citer nommément (libellés de l'offre) : " + " | ".join(adapted)
        )
    else:
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
        "Garde les missions du CV original (reformulées) ; tu peux en ajouter si besoin. "
        "Ne change pas les dates ni le lieu des expériences ; tu peux adapter le titre du poste."
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


def _restore_experience_anchors(generated_text: str, original_cv: str) -> str:
    """Force original experience dates, locations and dropped missions back onto the CV."""
    cleaned = cv_text_for_candidate(generated_text)
    generated = parse_adapted_cv(cleaned)
    original = parse_adapted_cv(original_cv)
    restored = restore_experience_dates_locations(generated, original)
    return labeled_cv_text(restored, fallback=cleaned) or cleaned


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
        "reprends le titre, l'entreprise, et cite nommément les compétences de l'offre "
        "(y compris une techno exigée absente du CV original) ainsi que l'intention "
        "de chaque modification ATS. "
        "Reformule les missions du CV analysé (ne les oublie pas) ; tu peux en ajouter "
        "si l'offre l'exige et que c'est cohérent avec le parcours. "
        "Tu peux adapter le titre d'un poste ; recopie exactement les dates et le lieu "
        "de chaque expérience. Pas de faux employeur, diplôme, date ou ville."
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
        "Réécris ## COMPETENCES en entier : d'abord TOUTES les technos et compétences "
        "de l'offre (même celles absentes du CV original — ajoute-les seulement dans "
        "cette liste, sans faux poste), libellés exacts séparés par | , puis le reste du CV. "
        "Applique TOUTES les modifications ATS DANS le corps du CV "
        "(reformulations, mots-clés, ordre des sections). "
        "Tu PEUX changer le POSTE (titre d'expérience) pour coller à l'offre. "
        "Tu NE CHANGES PAS PERIODE ni LIEU ni l'entreprise. "
        "Reformule TOUTES les missions du CV analysé, puis ajoute-en si l'offre le demande "
        "sans inventer un travail jamais fait. "
        "Le CV tient sur UNE page A4 : puces courtes, pas de paragraphes longs. "
        "N'ajoute aucune section listant les modifications : le CV s'arrête après les rubriques métier."
    )
    generated = _generate_aligned_document(
        kind="cv",
        system_prompt=ADAPTED_CV_SYSTEM_PROMPT + build_cv_system_addon(family),
        base_user_prompt=user_prompt,
        llm_call=llm_call,
        alignment=alignment,
        max_tokens=4800,
        postprocess=cv_text_for_candidate,
    )
    return _restore_experience_anchors(generated, cv_text)
