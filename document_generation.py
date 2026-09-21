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
    normalize_cover_letter,
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
Tu es un expert RH francophone. Avant d'écrire, mets-toi dans la peau du recruteur
ou de la RH qui ouvrira ce PDF en 8 secondes : le titre, les compétences et la
première phrase doivent prouver que cette lettre est FAITE pour CETTE offre.

Rédige une lettre de motivation MODERNE, sur UNE page A4, ALIGNÉE À 100 % SUR L'OFFRE,
en français.

INTERDIT : un seul paragraphe / un seul bloc. Si tu colles tout ensemble, la lettre est refusée.

STRUCTURE OBLIGATOIRE — une ligne blanche réelle entre CHAQUE bloc :

1) Objet : Candidature au poste de [intitulé EXACT de l'offre] — [entreprise]
2) Madame, Monsieur,
3) INTRODUCTION (1 paragraphe, 4 à 6 lignes) :
   accroche claire — pourquoi CE poste, CETTE entreprise, CE type de contrat ;
   relie le titre CV recommandé à l'intitulé de l'offre.
4) CORPS 1 — compétences (1 paragraphe, 6 à 8 lignes) :
   cite nommément les compétences présentes et partielles de l'analyse ATS
   et les mots-clés de l'offre que le candidat possède déjà (y compris une techno
   exigée absente du CV original, uniquement comme compétence, sans inventer un poste).
5) CORPS 2 — expériences (1 paragraphe, 6 à 8 lignes) :
   reformule les missions du CV ANALYSÉ avec le vocabulaire de l'annonce.
   N'oublie aucune mission importante. Tu peux en citer une supplémentaire si l'offre
   l'exige et que c'est cohérent avec le parcours réel.
   Tu peux adapter le TITRE du poste ; recopie EXACTEMENT les dates et le lieu du CV original.
6) CONCLUSION (1 paragraphe, 3 à 5 lignes) :
   disponibilité, demande d'entretien, remerciement — appel à l'action concret.
7) Cordialement,
8) Prénom Nom du candidat

Règles de forme :
- 280 à 380 mots au total. Une page, pas plus.
- Ton professionnel, vivant, concret : faits du CV, pas de phrases vides.
- Pas de puces, pas de markdown, pas de titres « Introduction » / « Corps » visibles.
- Pas de « Je me permets de » en boucle. Varie les ouvertures de paragraphe.

Règles de fond :
- Applique l'intention de CHAQUE « Modification ATS » (mots-clés, angle, priorités).
- Reformule les missions du CV d'origine ; ne les néglige pas.
- N'invente pas de diplômes, employeurs, dates ou certifications.
- Ne change JAMAIS les dates ni le lieu d'une expérience (ville, période).
- Si un mot-clé de l'offre correspond à une mission déjà décrite, utilise le mot-clé de l'offre.
- Retourne UNIQUEMENT le texte de la lettre (pas de JSON, pas de markdown).
"""

ADAPTED_CV_SYSTEM_PROMPT = """
Tu es un expert ATS et rédacteur de CV francophone.
Avant d'écrire, mets-toi dans la peau du recruteur / de la RH qui scanne le CV
en 8 secondes : le TITRE, la première ligne de PROFIL et les compétences doivent
coller à l'intitulé EXACT de l'offre. Sinon le CV est jeté.

Ta mission : produire un NOUVEAU CV complet, réécrit de zéro, qui correspond à 100 %
à l'offre ciblée : un ATS et un humain doivent y retrouver le titre de l'offre,
toutes les compétences de l'annonce, et l'effet de CHAQUE modification ATS listée.

Règles strictes :
1. Chaque modification ATS listée doit être visible dans le CV final (reformulation, section, mot-clé, ordre).
2. Le champ TITRE doit être EXACTEMENT l'intitulé de l'offre (ou le « Titre CV recommandé » s'il est plus précis).
3. Réécris ENTIÈREMENT la section ## COMPETENCES : en tête, TOUTES les compétences
   et technos de l'offre (obligatoires, stack, mots-clés ATS), avec les LIBELLÉS EXACTS
   de l'annonce, séparées par « | ». Si une techno est dans l'offre mais pas dans le CV
   original, AJOUTE-LA quand même dans cette section (c'est la seule invention autorisée :
   le mot-clé, pas un faux job). Ensuite, les autres compétences réelles du CV original.
4. Intègre les synonymes de l'offre (JS → JavaScript) et les mots-clés manquants.
5. Missions du CV analysé — adapte-les pour captiver le recruteur de CETTE offre :
   - Reformule TOUTES les missions d'origine avec le vocabulaire EXACT de l'annonce
     (outils, normes, livrables, verbes de l'offre). Ne les supprime pas.
   - UNE seule puce par mission : ne recopie pas l'originale à côté de la version reformulée.
   - Tu PEUX ajouter 1 à 3 missions supplémentaires SI elles correspondent à un travail réel
     du CV original (ou fortement impliqué), pour coller à l'offre, et si elles n'existent pas déjà.
   - N'invente pas une mission entière autour d'une techno absente du parcours : elle va dans COMPETENCES.
   - Tu PEUX adapter le champ POSTE (titre) pour coller à l'offre (ex. « Technicien support »
     → « Technicien support — ISO 27001 / conformité » si l'offre le justifie).
   - Tu NE DOIS PAS modifier PERIODE (dates) ni LIEU, ni l'entreprise : recopie-les tels quels.
6. Ne invente JAMAIS de diplôme, entreprise, date, lieu ou certification.
7. Réécriture complète (nouvelle structure, nouvelles formulations), pas un copier-coller.
8. Document FINAL prêt à envoyer (norme France 2026 : UNE page A4, une colonne, titres ATS classiques).
   Profil court (3-4 lignes) qui paraphrase l'offre, sans recopie de la liste COMPETENCES.
   Missions : 3 à 5 puces max par poste, une idée par puce, phrase complète, sans doublon.
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
    structure = ""
    if kind == "letter":
        structure = (
            " Conserve la structure moderne : Objet, Madame, Monsieur, "
            "INTRODUCTION, CORPS compétences, CORPS expériences, CONCLUSION, "
            "Cordialement — chaque bloc séparé par une ligne vide. Jamais un seul paragraphe."
        )
    return (
        f"Le {label} précédent n'est PAS encore aligné à 100 % sur l'offre. "
        f"Éléments encore absents :\n{gap_lines}\n\n"
        f"Réécris le {label} COMPLET (pas un diff) en intégrant TOUS ces éléments. "
        "Garde les missions du CV original (reformulées, une seule fois chacune) ; "
        "tu peux en ajouter si besoin, sans doublon. "
        "Ne change pas les dates ni le lieu des expériences ; tu peux adapter le titre du poste."
        f"{structure}"
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


def _force_offer_title(
    generated_text: str,
    job: dict[str, Any],
    match: dict[str, Any],
) -> str:
    """Keep the CV headline identical to the offer the recruiter posted."""
    title = str(
        (match or {}).get("titre_cv_recommande") or (job or {}).get("title") or ""
    ).strip()
    if not title:
        return generated_text
    if re.search(r"(?im)^TITRE\s*:", generated_text or ""):
        return re.sub(r"(?im)^TITRE\s*:.*$", f"TITRE: {title}", generated_text, count=1)
    return f"TITRE: {title}\n{generated_text}"


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
        "Rédige la lettre de motivation moderne (introduction / corps / conclusion), "
        "UNE page, paragraphes séparés par une ligne vide — jamais un seul bloc. "
        "Elle doit coller à 100 % à cette offre : "
        "reprends le titre, l'entreprise, et cite nommément les compétences de l'offre "
        "(y compris une techno exigée absente du CV original) ainsi que l'intention "
        "de chaque modification ATS. "
        "Reformule les missions du CV analysé (ne les oublie pas) ; tu peux en ajouter "
        "si l'offre l'exige et que c'est cohérent avec le parcours. "
        "Tu peux adapter le titre d'un poste ; recopie exactement les dates et le lieu "
        "de chaque expérience. Pas de faux employeur, diplôme, date ou ville."
    )

    def _shape_letter(text: str) -> str:
        return normalize_cover_letter(text, job=job, user_profile=user_profile)

    return _generate_aligned_document(
        kind="letter",
        system_prompt=COVER_LETTER_SYSTEM_PROMPT,
        base_user_prompt=user_prompt,
        llm_call=llm_call,
        alignment=alignment,
        max_tokens=2000,
        postprocess=_shape_letter,
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
        "Mets-toi dans la peau du recruteur : le champ TITRE = l'intitulé EXACT de l'offre "
        "(ou le titre CV recommandé s'il est plus précis). "
        "Réécris ## COMPETENCES en entier : d'abord TOUTES les technos et compétences "
        "de l'offre (même celles absentes du CV original — ajoute-les seulement dans "
        "cette liste, sans faux poste), libellés exacts séparés par | , puis le reste du CV. "
        "Applique TOUTES les modifications ATS DANS le corps du CV "
        "(reformulations, mots-clés, ordre des sections). "
        "Tu PEUX changer le POSTE (titre d'expérience) pour coller à l'offre. "
        "Tu NE CHANGES PAS PERIODE ni LIEU ni l'entreprise. "
        "Reformule TOUTES les missions du CV analysé : une puce par mission, "
        "sans recopier l'originale à côté, puis ajoute-en seulement si l'offre le demande "
        "sans inventer un travail jamais fait et sans doublon. "
        "Le CV tient sur UNE page A4 : profil 3-4 lignes, 3 à 5 puces max par poste, "
        "phrases complètes, pas de paragraphes redondants. "
        "N'ajoute aucune section listant les modifications : le CV s'arrête après les rubriques métier."
    )
    generated = _generate_aligned_document(
        kind="cv",
        system_prompt=ADAPTED_CV_SYSTEM_PROMPT + build_cv_system_addon(family),
        base_user_prompt=user_prompt,
        llm_call=llm_call,
        alignment=alignment,
        max_tokens=4800,
        postprocess=lambda text: _force_offer_title(
            cv_text_for_candidate(text), job, match
        ),
    )
    return _restore_experience_anchors(generated, cv_text)


def generate_followup_message(
    job: dict[str, Any],
    user_profile: dict[str, Any],
) -> str:
    """Plain-text follow-up the candidate can paste to the recruiter."""
    name = str(user_profile.get("full_name") or "Candidat").strip()
    title = str(job.get("title") or "le poste").strip()
    company = str(job.get("company") or "votre équipe").strip()
    return (
        f"Bonjour,\n\n"
        f"Je me permets de revenir vers vous au sujet de ma candidature pour {title} "
        f"chez {company}. Je reste très motivé(e) par cette opportunité et disponible "
        f"pour un échange.\n\n"
        f"Vous pouvez me joindre sur {user_profile.get('email') or 'mon e-mail'} "
        f"{('ou au ' + str(user_profile.get('phone'))) if user_profile.get('phone') else ''}"
        f".\n\n"
        f"Cordialement,\n{name}\n"
    ).replace("  ", " ")


def _freelance_skill_lines(user_profile: dict[str, Any], cv_text: str, *, limit: int = 3) -> list[str]:
    raw = str(user_profile.get("skills_text") or "")
    skills = [item.strip(" -•\t") for item in re.split(r"[,;\n]", raw) if item.strip()]
    if len(skills) < limit:
        for token in re.split(r"[,;\n]", cv_text or ""):
            word = token.strip(" -•\t")
            if 2 < len(word) <= 40 and word not in skills:
                skills.append(word)
            if len(skills) >= limit:
                break
    return skills[:limit]


def _freelance_project_lines(user_profile: dict[str, Any], cv_text: str, *, limit: int = 2) -> list[str]:
    """Use only experiences the student actually wrote — never invent missions."""
    _ = cv_text
    chunks: list[str] = []
    for line in str(user_profile.get("experiences_text") or "").splitlines():
        cleaned = line.strip(" -•\t")
        if len(cleaned) < 12:
            continue
        if cleaned not in chunks:
            chunks.append(cleaned[:180])
        if len(chunks) >= limit:
            break
    return chunks[:limit]


def generate_freelance_proposal(
    cv_text: str,
    job: dict[str, Any],
    user_profile: dict[str, Any],
) -> str:
    """Outreach message for a freelance mission (no invented experience)."""
    name = str(user_profile.get("full_name") or "Indépendant").strip()
    title = str(job.get("title") or "Mission").strip()
    company = str(job.get("company") or job.get("client") or "Client").strip()
    skills = _freelance_skill_lines(user_profile, cv_text)
    projects = _freelance_project_lines(user_profile, cv_text)
    rate = int(user_profile.get("daily_rate") or 0)
    portfolio = str(user_profile.get("portfolio_url") or "").strip()
    skill_block = "\n".join(f"- {item}" for item in skills) or "- Compétences détaillées dans le CV joint"
    if projects:
        project_block = "\n".join(f"- {item}" for item in projects)
        project_section = (
            f"J’ai déjà réalisé des projets similaires :\n{project_block}\n"
        )
    else:
        project_section = (
            "Les projets déjà réalisés sont décrits dans le CV joint "
            "(aucune mission n’est inventée).\n"
        )
    rate_line = f"TJM : {rate} € HT / jour.\n" if rate else ""
    portfolio_line = f"Portfolio : {portfolio}\n" if portfolio else ""
    return (
        f"Bonjour,\n\n"
        f"Je suis intéressé par votre mission « {title} » ({company}). "
        f"Voici ce que je peux apporter :\n"
        f"{skill_block}\n\n"
        f"{project_section}\n"
        f"Je suis disponible immédiatement.\n"
        f"{rate_line}{portfolio_line}\n"
        f"Cordialement,\n{name}\n"
    )


def generate_freelance_quote(
    job: dict[str, Any],
    user_profile: dict[str, Any],
    *,
    days: int = 10,
) -> str:
    """Simple quote (devis) the candidate can send for a freelance mission."""
    name = str(user_profile.get("full_name") or "Indépendant").strip()
    title = str(job.get("title") or "Mission").strip()
    company = str(job.get("company") or "Client").strip()
    rate = int(user_profile.get("daily_rate") or 0)
    duration = max(1, min(90, int(days or 10)))
    total = rate * duration if rate else None
    total_line = f"{total} € HT" if total else "sur devis après cadrage"
    rate_line = f"{rate} € HT" if rate else "à convenir"
    return (
        f"DEVIS — {title}\n"
        f"Prestataire : {name}\n"
        f"Client : {company}\n\n"
        f"Prestation : {title}\n"
        f"Durée estimée : {duration} jour(s)\n"
        f"TJM : {rate_line}\n"
        f"Total estimé : {total_line}\n\n"
        f"Valable 30 jours. Hors frais de déplacement.\n"
    )
