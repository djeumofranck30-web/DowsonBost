"""
Auto Job Finder & CV Matcher — Streamlit SaaS MVP
Upload CV (PDF) → AI extraction → Job search → CV matching report
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
from datetime import datetime
from typing import Any

import fitz  # pymupdf
import pdfplumber
import requests
import streamlit as st
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Auto Job Finder & CV Matcher",
    page_icon="🎯",
    layout="wide",
)

JOB_PROVIDER_ADZUNA = "adzuna"
JOB_PROVIDER_SERPAPI = "serpapi"
MIN_CV_TEXT_LENGTH = 50
MAX_OCR_PAGES = 5
CACHE_TTL_SECONDS = 86_400  # 24 h

ADZUNA_COUNTRY_CODES = {
    "France": "fr",
    "Royaume-Uni": "gb",
    "Allemagne": "de",
    "Espagne": "es",
    "Italie": "it",
    "Pays-Bas": "nl",
    "Belgique": "be",
    "Suisse": "ch",
    "États-Unis": "us",
    "Australie": "au",
}


def get_secret(key: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then environment variables."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv(key, default)


def pdf_fingerprint(pdf_bytes: bytes) -> str:
    """Stable hash for cache keys based on PDF content."""
    return hashlib.sha256(pdf_bytes).hexdigest()


# ---------------------------------------------------------------------------
# PDF extraction (native text + OCR fallback)
# ---------------------------------------------------------------------------


def extract_text_native(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF using pdfplumber."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def extract_text_ocr_gemini(pdf_bytes: bytes) -> str:
    """
    OCR fallback for scanned PDFs: render pages as images and send to Gemini Vision.
    Works on Streamlit Cloud without Tesseract system dependencies.
    """
    gemini_key = get_secret("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError(
            "OCR requis pour ce PDF scanné. Configurez GEMINI_API_KEY "
            "(Gemini Vision) dans vos secrets."
        )

    import google.generativeai as genai
    from PIL import Image

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = min(len(doc), MAX_OCR_PAGES)
    text_parts: list[str] = []

    ocr_prompt = (
        "Tu es un OCR expert. Extrais l'intégralité du texte visible de ce CV. "
        "Conserve la structure (sections, listes). "
        "Retourne uniquement le texte brut, sans commentaire ni markdown."
    )

    for page_index in range(page_count):
        page = doc[page_index]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        response = model.generate_content([ocr_prompt, image])
        if response.text:
            text_parts.append(response.text.strip())

    doc.close()
    return "\n".join(text_parts).strip()


def extract_cv_text(pdf_bytes: bytes) -> tuple[str, str]:
    """
    Extract CV text: native PDF text first, OCR fallback if insufficient.
    Returns (text, method) where method is 'native' or 'ocr'.
    """
    native_text = extract_text_native(pdf_bytes)
    if len(native_text) >= MIN_CV_TEXT_LENGTH:
        return native_text, "native"

    ocr_text = extract_text_ocr_gemini(pdf_bytes)
    if len(ocr_text) >= MIN_CV_TEXT_LENGTH:
        return ocr_text, "ocr"

    raise RuntimeError(
        "Impossible d'extraire suffisamment de texte du PDF "
        "(ni extraction native, ni OCR). Vérifiez la qualité du scan."
    )


# ---------------------------------------------------------------------------
# LLM helpers (Gemini or OpenAI)
# ---------------------------------------------------------------------------


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from an LLM response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini (preferred) or OpenAI depending on available API keys."""
    gemini_key = get_secret("GEMINI_API_KEY")
    openai_key = get_secret("OPENAI_API_KEY")

    if gemini_key:
        import google.generativeai as genai

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config={"temperature": 0.2},
        )
        response = model.generate_content(
            f"{system_prompt}\n\n---\n\n{user_prompt}",
        )
        return response.text

    if openai_key:
        from openai import OpenAI

        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"

    raise RuntimeError(
        "Aucune clé IA configurée. Ajoutez GEMINI_API_KEY ou OPENAI_API_KEY "
        "dans .streamlit/secrets.toml ou les variables d'environnement."
    )


def extract_search_criteria(cv_text: str) -> dict[str, Any]:
    """Use AI to infer job title, location, contract type and keywords from CV."""
    system_prompt = """Tu es un expert RH et recruteur tech.
Analyse le CV fourni et extrais les critères de recherche d'emploi.
Réponds UNIQUEMENT en JSON valide avec cette structure exacte :
{
  "metier": "intitulé du poste visé (ex: Administrateur Systèmes Linux)",
  "ville": "ville ou région principale (ex: Lyon)",
  "pays": "pays en français (ex: France)",
  "type_contrat": "CDI, CDD, Alternance, Stage, Freelance ou Tous",
  "mots_cles": ["liste", "de", "5", "à", "10", "compétences", "clés"],
  "query_recherche": "requête courte optimisée pour moteur d'emploi"
}
Règles :
- Si une info manque, déduis-la du profil (niveau, compétences, expériences).
- query_recherche = metier + compétence principale (sans la ville).
- Réponds en français."""

    user_prompt = f"CV :\n\n{cv_text[:12000]}"
    raw = call_llm(system_prompt, user_prompt)
    return _parse_json_response(raw)


def match_cv_to_job(cv_text: str, job: dict[str, Any]) -> dict[str, Any]:
    """Compare CV against a single job offer and return optimization advice."""
    system_prompt = """Tu es un coach carrière expert en ATS et recrutement.
Compare le CV du candidat à l'offre d'emploi et produis un rapport d'optimisation.
Réponds UNIQUEMENT en JSON valide :
{
  "score_correspondance": 85,
  "titre_cv_recommande": "Titre de CV optimisé pour cette offre",
  "mots_cles_manquants": ["mot1", "mot2"],
  "conseils": [
    "Conseil 1 spécifique et actionnable",
    "Conseil 2 spécifique et actionnable",
    "Conseil 3 spécifique et actionnable"
  ]
}
Règles :
- score_correspondance : entier 0-100 (skills, expérience, séniorité, localisation).
- mots_cles_manquants : 3 à 8 termes présents dans l'offre mais absents ou faibles dans le CV.
- conseils : exactement 3 phrases concrètes adaptées à CETTE offre.
- Réponds en français."""

    job_summary = (
        f"Titre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '')}\n"
        f"Description :\n{job.get('description', '')[:6000]}"
    )
    user_prompt = f"CV candidat :\n{cv_text[:8000]}\n\nOffre :\n{job_summary}"
    raw = call_llm(system_prompt, user_prompt)
    return _parse_json_response(raw)


# ---------------------------------------------------------------------------
# Cached wrappers (24 h TTL — avoids re-billing APIs on Streamlit reruns)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_extract_criteria(cv_text: str) -> dict[str, Any]:
    return extract_search_criteria(cv_text)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_search_jobs(
    provider: str,
    query: str,
    location: str,
    country: str,
) -> list[dict[str, Any]]:
    return search_jobs(provider, query, location, country)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_match_cv_to_job(cv_text: str, job_json: str) -> dict[str, Any]:
    return match_cv_to_job(cv_text, json.loads(job_json))


# ---------------------------------------------------------------------------
# Job search — Adzuna & SerpApi
# ---------------------------------------------------------------------------


def search_jobs_adzuna(
    query: str,
    location: str,
    country_code: str,
    results_per_page: int = 20,
) -> list[dict[str, Any]]:
    """Search jobs via Adzuna REST API."""
    app_id = get_secret("ADZUNA_APP_ID")
    app_key = get_secret("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError(
            "Clés Adzuna manquantes. Configurez ADZUNA_APP_ID et ADZUNA_APP_KEY."
        )

    url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": query,
        "where": location,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    jobs: list[dict[str, Any]] = []
    for item in data.get("results", []):
        jobs.append(
            {
                "title": item.get("title", "N/A"),
                "company": item.get("company", {}).get("display_name", "N/A"),
                "location": item.get("location", {}).get("display_name", "N/A"),
                "description": item.get("description", ""),
                "url": item.get("redirect_url", ""),
                "contract_type": item.get("contract_type", ""),
                "source": "Adzuna",
            }
        )
    return jobs


def search_jobs_serpapi(query: str, location: str) -> list[dict[str, Any]]:
    """Search jobs via SerpApi Google Jobs engine."""
    api_key = get_secret("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Clé SerpApi manquante. Configurez SERPAPI_API_KEY."
        )

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": api_key,
        "hl": "fr",
    }
    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()

    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs_results", []):
        apply_options = item.get("apply_options") or []
        apply_url = apply_options[0].get("link", "") if apply_options else ""
        jobs.append(
            {
                "title": item.get("title", "N/A"),
                "company": item.get("company_name", "N/A"),
                "location": item.get("location", "N/A"),
                "description": item.get("description", ""),
                "url": apply_url or item.get("share_link", ""),
                "contract_type": "",
                "source": "Google Jobs (SerpApi)",
            }
        )
    return jobs


def search_jobs(
    provider: str,
    query: str,
    location: str,
    country: str,
) -> list[dict[str, Any]]:
    """Dispatch job search to the selected provider."""
    if provider == JOB_PROVIDER_SERPAPI:
        serp_location = f"{location}, {country}" if location else country
        return search_jobs_serpapi(query, serp_location)

    country_code = ADZUNA_COUNTRY_CODES.get(country, "fr")
    return search_jobs_adzuna(query, location, country_code)


def rank_jobs_for_cv(
    jobs: list[dict[str, Any]],
    cv_text: str,
    keywords: list[str],
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Pre-rank jobs by keyword overlap before deep AI matching."""
    cv_lower = cv_text.lower()
    keyword_set = {kw.lower() for kw in keywords}

    def quick_score(job: dict[str, Any]) -> int:
        blob = f"{job.get('title', '')} {job.get('description', '')}".lower()
        hits = sum(1 for kw in keyword_set if kw in blob)
        gaps = sum(1 for kw in keyword_set if kw in blob and kw not in cv_lower)
        return hits * 10 - gaps * 2

    return sorted(jobs, key=quick_score, reverse=True)[:top_n]


# ---------------------------------------------------------------------------
# PDF report export
# ---------------------------------------------------------------------------


def generate_matching_report_pdf(
    criteria: dict[str, Any],
    results: list[dict[str, Any]],
    extraction_method: str,
) -> bytes:
    """Build a downloadable PDF report from analysis results."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    title = "Rapport de Matching CV — Auto Job Finder"

    body_html = f"""
    <h1>{html.escape(title)}</h1>
    <p><em>Généré le {generated_at} · Extraction CV : {html.escape(extraction_method)}</em></p>
    <hr>
    <h2>Critères détectés</h2>
    <ul>
        <li><b>Métier visé :</b> {html.escape(str(criteria.get('metier', '—')))}</li>
        <li><b>Ville :</b> {html.escape(str(criteria.get('ville', '—')))}</li>
        <li><b>Pays :</b> {html.escape(str(criteria.get('pays', '—')))}</li>
        <li><b>Type de contrat :</b> {html.escape(str(criteria.get('type_contrat', '—')))}</li>
        <li><b>Mots-clés :</b> {html.escape(', '.join(criteria.get('mots_cles', [])))}</li>
    </ul>
    """

    for idx, entry in enumerate(results, start=1):
        job = entry["job"]
        match = entry["match"]
        score = int(match.get("score_correspondance", 0))
        missing = ", ".join(match.get("mots_cles_manquants", []))
        tips_html = "".join(
            f"<li>{html.escape(tip)}</li>"
            for tip in match.get("conseils", [])[:3]
        )

        body_html += f"""
        <hr>
        <h2>#{idx} — {html.escape(job.get('title', 'N/A'))} ({score}%)</h2>
        <ul>
            <li><b>Entreprise :</b> {html.escape(job.get('company', 'N/A'))}</li>
            <li><b>Lieu :</b> {html.escape(job.get('location', 'N/A'))}</li>
            <li><b>Contrat :</b> {html.escape(job.get('contract_type', '—') or '—')}</li>
            <li><b>Source :</b> {html.escape(job.get('source', ''))}</li>
            <li><b>Lien :</b> {html.escape(job.get('url', '—'))}</li>
            <li><b>Titre CV recommandé :</b> {html.escape(match.get('titre_cv_recommande', 'N/A'))}</li>
            <li><b>Mots-clés manquants :</b> {html.escape(missing or '—')}</li>
        </ul>
        <h3>Conseils d'optimisation</h3>
        <ol>{tips_html}</ol>
        """

    pdf.write_html(body_html)
    # fpdf2 returns str when dest="" in some versions; output() returns bytes/bytearray
    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------


def run_full_analysis(
    pdf_bytes: bytes,
    job_provider: str,
) -> dict[str, Any]:
    """Execute the full CV → jobs → matching pipeline."""
    cv_text, extraction_method = extract_cv_text(pdf_bytes)
    criteria = cached_extract_criteria(cv_text)

    query = criteria.get("query_recherche") or criteria.get("metier", "")
    location = criteria.get("ville", "")
    country = criteria.get("pays", "France")
    keywords = criteria.get("mots_cles", [])

    jobs = cached_search_jobs(job_provider, query, location, country)
    ranked_jobs = rank_jobs_for_cv(jobs, cv_text, keywords)

    results: list[dict[str, Any]] = []
    for job in ranked_jobs:
        job_json = json.dumps(job, sort_keys=True, ensure_ascii=False)
        match = cached_match_cv_to_job(cv_text, job_json)
        results.append({"job": job, "match": match})

    return {
        "cv_text": cv_text,
        "extraction_method": extraction_method,
        "criteria": criteria,
        "jobs_found": len(jobs),
        "results": results,
        "job_provider": job_provider,
    }


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def render_job_card(job: dict[str, Any], match: dict[str, Any], rank: int) -> None:
    """Render a single job match card."""
    score = int(match.get("score_correspondance", 0))
    score_color = (
        "#22c55e" if score >= 75 else "#eab308" if score >= 50 else "#ef4444"
    )

    st.markdown(f"### #{rank} — {job['title']}")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        st.markdown(f"**Entreprise :** {job['company']}")
        st.markdown(f"**Lieu :** {job['location']}")
        if job.get("contract_type"):
            st.markdown(f"**Contrat :** {job['contract_type']}")
        st.markdown(f"**Source :** {job.get('source', '')}")

    with col2:
        st.markdown(
            f"**Titre CV recommandé :** "
            f"{match.get('titre_cv_recommande', 'N/A')}"
        )
        missing = match.get("mots_cles_manquants", [])
        if missing:
            st.markdown("**Mots-clés manquants :**")
            st.write(", ".join(f"`{kw}`" for kw in missing))

    with col3:
        st.markdown(
            f"<div style='text-align:center;padding:1rem;border-radius:12px;"
            f"background:{score_color}22;border:2px solid {score_color}'>"
            f"<span style='font-size:2rem;font-weight:bold;color:{score_color}'>"
            f"{score}%</span><br><small>Correspondance</small></div>",
            unsafe_allow_html=True,
        )

    st.markdown("**3 conseils d'ajustement du CV :**")
    for i, tip in enumerate(match.get("conseils", [])[:3], start=1):
        st.info(f"{i}. {tip}")

    if job.get("url"):
        st.link_button("Postuler →", job["url"], use_container_width=False)

    st.divider()


def render_analysis_results(analysis: dict[str, Any]) -> None:
    """Display stored analysis results and export button."""
    criteria = analysis["criteria"]
    extraction_method = analysis["extraction_method"]

    method_label = "Texte natif PDF" if extraction_method == "native" else "OCR Gemini Vision"
    st.caption(f"Extraction CV : **{method_label}**")

    with st.expander("Texte extrait du CV", expanded=False):
        cv_preview = analysis["cv_text"]
        st.text(cv_preview[:3000] + ("…" if len(cv_preview) > 3000 else ""))

    st.subheader("Critères détectés automatiquement")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Métier visé", criteria.get("metier", "—"))
    c2.metric("Ville", criteria.get("ville", "—"))
    c3.metric("Type de contrat", criteria.get("type_contrat", "—"))
    c4.metric("Pays", criteria.get("pays", "France"))

    keywords = criteria.get("mots_cles", [])
    if keywords:
        st.markdown(
            "**Mots-clés clés :** " + " · ".join(f"`{kw}`" for kw in keywords)
        )

    st.success(
        f"{analysis['jobs_found']} offre(s) trouvée(s). "
        f"Top {len(analysis['results'])} analysé(s)."
    )

    col_export, col_info = st.columns([1, 2])
    with col_export:
        pdf_bytes = generate_matching_report_pdf(
            criteria,
            analysis["results"],
            method_label,
        )
        st.download_button(
            label="Télécharger le rapport (PDF)",
            data=pdf_bytes,
            file_name=f"rapport_matching_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    with col_info:
        st.caption(
            "Le rapport PDF inclut les 5 offres, scores, mots-clés manquants "
            "et conseils d'optimisation."
        )

    st.subheader("Top 5 — Rapport de matching & optimisation CV")
    for idx, entry in enumerate(analysis["results"], start=1):
        render_job_card(entry["job"], entry["match"], idx)


def main() -> None:
    st.title("Auto Job Finder & CV Matcher")
    st.caption(
        "Déposez votre CV — l'IA extrait vos critères, recherche les offres "
        "et génère un rapport d'optimisation pour les 5 meilleures correspondances."
    )

    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "pdf_fingerprint" not in st.session_state:
        st.session_state.pdf_fingerprint = None

    with st.sidebar:
        st.header("Configuration")
        job_provider = st.selectbox(
            "API de recherche d'emploi",
            [JOB_PROVIDER_ADZUNA, JOB_PROVIDER_SERPAPI],
            format_func=lambda x: "Adzuna (gratuit, recommandé)"
            if x == JOB_PROVIDER_ADZUNA
            else "SerpApi / Google Jobs",
        )

        ai_provider = (
            "Gemini"
            if get_secret("GEMINI_API_KEY")
            else "OpenAI"
            if get_secret("OPENAI_API_KEY")
            else "Non configuré"
        )
        st.markdown(f"**Moteur IA :** {ai_provider}")

        st.markdown("---")
        st.markdown("**Fonctionnalités**")
        st.markdown(
            "- OCR automatique (PDF scannés)\n"
            "- Cache 24 h (économie API)\n"
            "- Export PDF du rapport"
        )

        if st.button("Vider le cache", use_container_width=True):
            st.cache_data.clear()
            st.session_state.analysis = None
            st.session_state.pdf_fingerprint = None
            st.success("Cache vidé.")
            st.rerun()

        st.markdown("---")
        st.markdown(
            "**Clés requises** (`.streamlit/secrets.toml`) :\n"
            "- `GEMINI_API_KEY` *(recommandé, requis pour OCR)*\n"
            "- `OPENAI_API_KEY` *(alternative IA)*\n"
            "- `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`\n"
            "- `SERPAPI_API_KEY` *(optionnel)*"
        )

    uploaded_file = st.file_uploader(
        "Déposez votre CV (PDF)",
        type=["pdf"],
        help="PDF natif ou scanné — l'OCR Gemini s'active automatiquement si besoin.",
    )

    if st.session_state.analysis and not uploaded_file:
        render_analysis_results(st.session_state.analysis)

    if not uploaded_file:
        if not st.session_state.analysis:
            st.info("Uploadez votre CV pour démarrer l'analyse automatique.")
        return

    pdf_bytes = uploaded_file.read()
    current_fp = pdf_fingerprint(pdf_bytes)

    if (
        st.session_state.analysis
        and st.session_state.pdf_fingerprint == current_fp
    ):
        st.info("Résultats en cache pour ce CV — relancez pour forcer une nouvelle analyse.")
        render_analysis_results(st.session_state.analysis)

    if st.button("Lancer l'analyse complète", type="primary", use_container_width=True):
        progress = st.progress(0, text="Initialisation…")

        try:
            progress.progress(10, text="Extraction du texte du CV…")
            cv_text, method = extract_cv_text(pdf_bytes)

            if method == "ocr":
                st.warning(
                    "PDF scanné détecté — extraction via OCR Gemini Vision."
                )

            progress.progress(25, text="Analyse IA du CV (métier, ville, contrat)…")
            criteria = cached_extract_criteria(cv_text)

            query = criteria.get("query_recherche") or criteria.get("metier", "")
            location = criteria.get("ville", "")
            country = criteria.get("pays", "France")
            keywords = criteria.get("mots_cles", [])

            progress.progress(45, text="Recherche d'offres d'emploi en cours…")
            jobs = cached_search_jobs(job_provider, query, location, country)

            if not jobs:
                st.warning(
                    "Aucune offre trouvée pour ces critères. "
                    "Essayez un autre pays ou basculez sur SerpApi."
                )
                return

            progress.progress(60, text="Matching CV ↔ offres (IA)…")
            ranked_jobs = rank_jobs_for_cv(jobs, cv_text, keywords)

            results: list[dict[str, Any]] = []
            for idx, job in enumerate(ranked_jobs, start=1):
                pct = 60 + int(35 * idx / len(ranked_jobs))
                progress.progress(
                    pct,
                    text=f"Analyse offre {idx}/{len(ranked_jobs)} : {job['title'][:40]}…",
                )
                job_json = json.dumps(job, sort_keys=True, ensure_ascii=False)
                match = cached_match_cv_to_job(cv_text, job_json)
                results.append({"job": job, "match": match})

            analysis = {
                "cv_text": cv_text,
                "extraction_method": method,
                "criteria": criteria,
                "jobs_found": len(jobs),
                "results": results,
                "job_provider": job_provider,
            }
            st.session_state.analysis = analysis
            st.session_state.pdf_fingerprint = current_fp

            progress.progress(100, text="Analyse terminée !")
            render_analysis_results(analysis)

        except requests.HTTPError as exc:
            st.error(
                f"Erreur API emploi : {exc.response.status_code} — "
                f"{exc.response.text[:300]}"
            )
        except json.JSONDecodeError:
            st.error("L'IA a renvoyé une réponse invalide. Relancez l'analyse.")
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur inattendue : {exc}")


if __name__ == "__main__":
    main()
