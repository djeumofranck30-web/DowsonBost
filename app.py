"""
DowsonBost
Plateforme de recherche d'emploi et matching CV par IA.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import html
import io
import json
import os
import re
import time
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable

import requests
import streamlit as st
from fpdf import FPDF

from france_geo import (
    city_options_for_departments,
    communes_supported_for_country,
    department_from_multiselect_label,
    department_labels_for_regions,
    format_department_label,
    get_region_names,
    labels_for_selected_cities,
    labels_for_selected_departments,
    parse_city_option,
    profile_all_cities,
    resolve_multi_geo_from_profile,
    resolve_selected_cities,
)
from job_filters import (
    CONTRACT_TYPES,
    COUNTRY_OPTIONS,
    EXPERIENCE_LEVELS,
    GEO_FILTER_MODES,
    SECTOR_OPTIONS,
    build_country_search_locations,
    apply_strict_job_filters,
    build_profile_search_locations,
    enrich_query_for_contract,
    format_filter_rejection_hint,
    format_job_published_label,
    job_max_age_label,
    JOB_MAX_AGE_DAYS_OPTIONS,
    normalize_job_max_age_days,
    profile_ready_for_matching,
    resolve_experience_level,
    resolve_target_sectors,
)
from i18n import (
    LOCALE_LABELS,
    SUPPORTED_LOCALES,
    analysis_depth_label,
    application_status_label,
    application_method_label,
    contract_label,
    experience_label,
    geo_mode_label,
    get_locale,
    init_locale,
    job_age_label,
    job_provider_label,
    nav_label,
    sector_label,
    set_locale,
    sort_label,
    t,
    weekday_label,
)
from world_cities import (
    city_options_for_country_zone,
    country_geo_all_cities,
    country_geo_cities,
    labels_for_selected_intl_cities,
    parse_intl_city_option,
)
from world_geo import (
    country_geo_schema,
    country_has_subdivisions,
    format_countries_summary,
    get_country_geo,
    merge_profile_geo,
    profile_countries,
    profile_primary_country,
)
from config import export_streamlit_secrets_to_environ, get_secret, get_secret_raw, normalize_secret
from constants import (
    ANALYSIS_DEPTH_OPTIONS,
    ANALYSIS_DEPTH_POOL,
    ANALYSIS_DEPTH_TOP,
    ANALYSIS_JOB_POLL_SECONDS,
    APP_NAME,
    ATS_MATCH_MAX_TOKENS,
    CACHE_TTL_SECONDS,
    CV_MATCH_TEXT_LIMIT_WITH_PROFILE,
    GROQ_INTER_CALL_DELAY_SEC,
    GROQ_MATCH_BATCH_SIZE,
    GROQ_RATE_LIMIT_RETRY_SEC,
    MATCHING_CANDIDATE_POOL,
    MAX_OCR_PAGES,
    MIN_CV_TEXT_LENGTH,
    NAV_PAGE_KEYS,
    PARALLEL_MATCH_KEYS_PER_PROVIDER,
    PARALLEL_MATCH_MAX_WORKERS,
    PROFILE_SECTION_KEYS,
    SEARCH_LOCATION_MAX_WORKERS,
    TOP_MATCHING_JOBS,
    JOB_CARDS_PER_PAGE,
    HISTORY_ROWS_PER_PAGE,
    APPLICATION_CHANNEL_KEYS,
)
from services.analysis_queue import (
    enqueue_analysis_job,
    get_analysis_job,
    get_latest_analysis_job,
)
from services.analysis_worker import (
    ensure_embedded_analysis_worker,
    kick_embedded_analysis_worker,
)
from services.application import (
    build_application_profile,
    format_application_autofill_text,
    format_application_profile_text,
    job_listing_open_script,
    notify_candidate_application,
    prepare_manual_application,
    submit_application_automatically,
)
from services.support import (
    mark_user_support_read,
    render_support_thread_html,
    send_user_support_message,
    start_user_support_conversation,
    user_support_conversations,
    user_support_thread,
    user_support_unread,
)
from services.profile_photo import (
    cached_profile_photo_data_url,
    cached_sidebar_photo_data_url,
    clear_profile_photo_cache,
    remove_profile_photo,
    save_profile_photo,
)
from services.matching import (
    as_str_list as _as_str_list,
    compute_ats_score as _compute_ats_score,
    fallback_match_result,
    normalize_experience_analysis as _normalize_experience_analysis,
    normalize_match_result as _normalize_match_result,
    normalize_score as _normalize_score,
    normalize_skills_analysis as _normalize_skills_analysis,
)


class GroqRateLimitError(RuntimeError):
    """Groq rate limit — quota org-wide, other models won't help immediately."""

from job_providers import (
    CONNECTABLE_JOB_PROVIDERS,
    JOB_PROVIDER_ADZUNA,
    JOB_PROVIDER_ALL,
    JOB_PROVIDER_CAREER_SITES,
    JOB_PROVIDER_GLASSDOOR,
    JOB_PROVIDER_HELLOWORK,
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_JOBTEASER,
    JOB_PROVIDER_JOOBLE,
    JOB_PROVIDER_LINKEDIN,
    JOB_PROVIDER_MONSTER,
    JOB_PROVIDER_OPTIONCARRIERE,
    JOB_PROVIDER_SERPAPI,
    JOB_PROVIDER_SIDEBAR_ORDER,
    JOB_PROVIDER_TALENT,
    JOB_PROVIDER_WTTJ,
    configured_providers,
    default_job_provider,
    job_board_display_name,
    job_board_signup_url,
    merge_career_site_results,
    merge_job_lists,
    normalize_careerjet_referer,
    provider_key_from_job_source,
    provider_secrets_from_getter,
    resolve_careerjet_user_ip,
    search_jobs_career_sites,
    search_jobs_glassdoor_serpapi,
    search_jobs_hellowork,
    search_jobs_indeed_serpapi,
    search_jobs_jobteaser,
    search_jobs_jooble,
    search_jobs_linkedin_serpapi,
    search_jobs_monster,
    search_jobs_optioncarriere,
    search_jobs_serpapi_google_jobs,
    search_jobs_talent,
    search_jobs_wttj,
    test_hellowork_connection,
    test_jobteaser_connection,
    test_jooble_connection,
    test_monster_connection,
    test_optioncarriere_connection,
    test_serpapi_platform_connection,
    test_talent_connection,
    test_wttj_connection,
    is_public_routable_ip,
)
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


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_PREFERRED_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-3-flash-preview",
)
GEMINI_FALLBACK_MODELS = GEMINI_PREFERRED_MODELS
# Interactions API — modèles 3.x uniquement (2.x renvoie souvent 404)
GEMINI_INTERACTION_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
)
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_MODEL = "gpt-4o-mini"
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_API_BASE = "https://api.groq.com/openai/v1"
# Modèles Groq actuels (2025–2026) — les anciens llama-3.x / gemma2 sont décommissionnés.
GROQ_PREFERRED_MODELS = (
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "groq/compound-mini",
    "compound-beta-mini",
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
)
GROQ_FALLBACK_MODELS = GROQ_PREFERRED_MODELS
# Uniquement les modèles non-chat (pas les llama-4 / gpt-oss / qwen).
GROQ_SKIP_MODEL_SUBSTRINGS = (
    "whisper",
    "embed",
    "guard",
    "distil-whisper",
    "orpheus",
    "canopylabs",
)
from auth import (
    EMAIL_PATTERN,
    authenticate_user,
    change_password,
    complete_verified_password_reset,
    delete_user_account,
    format_member_since,
    get_user_by_id,
    init_db,
    join_full_name,
    register_user,
    request_password_reset_code,
    reset_code_seconds_remaining,
    split_full_name,
    update_user_preferred_language,
    update_user_profile,
    verify_password_reset_code,
)
from database import (
    DatabaseConfigError,
    configure_database,
    connect,
    database_connection_hint,
    database_status,
    format_database_exception,
)
from document_generation import generate_adapted_cv, generate_cover_letter
from cv_layout import (
    cv_pdf_filename,
    cv_text_for_candidate,
    letter_pdf_filename,
    prepare_structured_cv,
    public_cv_text,
    render_cover_letter_pdf,
    render_cv_html,
    render_cv_pdf,
    template_label,
)
from email_service import email_configured, maybe_send_analysis_alert
from persistence import (
    APPLICATION_STATUSES,
    AUTO_SEARCH_WEEKDAYS,
    analysis_to_session_dict,
    connect_job_account,
    count_user_applications,
    disconnect_job_account,
    get_active_cv_document,
    get_analysis,
    get_analysis_apply_context,
    get_analysis_result,
    get_analysis_results_by_ids,
    get_connected_job_account,
    get_notification_settings,
    is_auto_search_due,
    list_analyses,
    list_connected_job_accounts,
    list_dashboard_results,
    list_user_applications,
    log_scheduled_run,
    mark_alert_sent,
    mark_auto_search_completed,
    record_application,
    save_analysis,
    save_generated_documents,
    save_notification_settings,
    update_application_status,
    upsert_active_cv_document,
)
from ui.theme import (
    THEME,
    nav_label_with_icon,
    render_app_styles,
    render_auth_styles,
)

# Theme tokens (re-exported from ui.theme for legacy references in app.py)
THEME_BG_GRADIENT = THEME["bg_gradient"]
THEME_PRIMARY = THEME["primary"]
THEME_PRIMARY_DARK = THEME["primary_dark"]
THEME_PRIMARY_DEEP = THEME["primary_deep"]
THEME_SURFACE = THEME["surface"]
THEME_SURFACE_SOFT = THEME["surface_soft"]
THEME_MUTED = THEME["muted"]
THEME_ACCENT = THEME["accent"]

APP_VERSION = "3.13.0-modern-ui"

try:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:  # noqa: BLE001 — already set when imported from pages/dashboard.py
    pass

GROQ_KEY_PLACEHOLDERS = {
    "",
    "gsk_...",
    "your_api_key",
    "votre_cle",
    "votre_cle_groq",
}

GEMINI_KEY_PLACEHOLDERS = {
    "",
    "votre_cle_gemini",
    "your_api_key",
    "your_gemini_api_key",
    "aiza...",
    "aizasy...",
}


def resolve_streamlit_client_ip() -> str:
    """Best-effort visitor IP from Streamlit / reverse-proxy headers."""
    try:
        headers = getattr(getattr(st, "context", None), "headers", None) or {}
        forwarded = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for") or ""
        if forwarded:
            for part in forwarded.split(","):
                ip = part.strip()
                if is_public_routable_ip(ip):
                    return ip
        for header_name in (
            "X-Real-Ip",
            "x-real-ip",
            "Cf-Connecting-Ip",
            "cf-connecting-ip",
        ):
            value = headers.get(header_name)
            if value and is_public_routable_ip(str(value).strip()):
                return str(value).strip()
    except Exception:  # noqa: BLE001 — optional Streamlit context
        pass
    return ""


def resolve_careerjet_referer(configured: str) -> str:
    """Referer header required by Careerjet — auto-detect deployed app URL when possible."""
    cleaned = normalize_careerjet_referer(configured)
    if cleaned not in ("https://localhost/", "http://localhost/"):
        return cleaned
    try:
        headers = getattr(getattr(st, "context", None), "headers", None) or {}
        host = headers.get("Host") or headers.get("host")
        if host:
            proto = (
                headers.get("X-Forwarded-Proto")
                or headers.get("x-forwarded-proto")
                or "https"
            )
            return normalize_careerjet_referer(f"{proto}://{host}/")
    except Exception:  # noqa: BLE001
        pass
    return cleaned


def _split_api_keys(raw: Any) -> list[str]:
    """Parse one or many API keys from a secret (string, list, comma/newline separated)."""
    candidates: list[str] = []
    if isinstance(raw, list):
        candidates = [str(item) for item in raw]
    elif raw:
        candidates = re.split(r"[\n,;]+", str(raw))

    keys: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = normalize_secret(item)
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _is_valid_provider_key(provider: str, key: str) -> bool:
    lower = key.lower()
    if provider == "groq":
        if lower in GROQ_KEY_PLACEHOLDERS or "..." in key or "votre_cle" in lower:
            return False
        return key.startswith("gsk_") and len(key) >= 50
    if provider == "gemini":
        if lower in GEMINI_KEY_PLACEHOLDERS or "votre_cle" in lower:
            return False
        return (key.startswith("AIza") and len(key) >= 35) or (
            key.startswith("AQ.") and len(key) >= 20
        )
    if provider == "openai":
        return key.startswith("sk-") and len(key) > 20
    return bool(key)


def get_provider_api_keys(provider: str) -> list[str]:
    """Return all configured API keys for a provider (singular + plural secrets)."""
    plural_names = {
        "groq": "GROQ_API_KEYS",
        "gemini": "GEMINI_API_KEYS",
        "openai": "OPENAI_API_KEYS",
    }
    singular_names = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    collected = _split_api_keys(get_secret_raw(plural_names[provider], ""))
    single = get_secret(singular_names[provider])
    if single and single not in collected:
        collected.insert(0, single)

    valid: list[str] = []
    seen: set[str] = set()
    for key in collected:
        if key in seen or not _is_valid_provider_key(provider, key):
            continue
        seen.add(key)
        valid.append(key)
    return valid


def collect_parallel_llm_slots(
    max_per_provider: int = PARALLEL_MATCH_KEYS_PER_PROVIDER,
) -> list[tuple[str, str]]:
    """Build Groq + Gemini key slots (up to 3 each) for parallel ATS matching."""
    slots: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    groq_ok = not st.session_state.get("groq_quota_exhausted")

    for provider in ("groq", "gemini"):
        if provider == "groq" and not groq_ok:
            continue
        for key in get_provider_api_keys(provider)[:max_per_provider]:
            pair = (provider, key)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            slots.append(pair)

    if not slots:
        for provider in ("openai",):
            for key in get_provider_api_keys(provider)[:max_per_provider]:
                pair = (provider, key)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    slots.append(pair)

    return slots


def count_parallel_keys_by_provider() -> dict[str, int]:
    slots = collect_parallel_llm_slots(PARALLEL_MATCH_KEYS_PER_PROVIDER)
    return {
        "groq": sum(1 for provider, _ in slots if provider == "groq"),
        "gemini": sum(1 for provider, _ in slots if provider == "gemini"),
        "openai": sum(1 for provider, _ in slots if provider == "openai"),
        "total": len(slots),
    }


def parallel_match_summary() -> str:
    """Human-readable summary of parallel matching keys."""
    counts = count_parallel_keys_by_provider()
    if counts["total"] == 0:
        return "aucune clé IA"
    parts: list[str] = []
    if counts["groq"]:
        parts.append(f"{counts['groq']} Groq")
    if counts["gemini"]:
        parts.append(f"{counts['gemini']} Gemini")
    if counts["openai"]:
        parts.append(f"{counts['openai']} OpenAI")
    workers = min(PARALLEL_MATCH_MAX_WORKERS, counts["total"])
    if counts["total"] == 1:
        slots = collect_parallel_llm_slots(PARALLEL_MATCH_KEYS_PER_PROVIDER)
        provider, key = slots[0]
        labels = {"groq": "Groq", "gemini": "Gemini", "openai": "OpenAI"}
        return f"1 clé {labels.get(provider, provider)} ({key[:8]}…)"
    return f"{counts['total']} clés ({' + '.join(parts)}) · {workers} workers parallèles"


def gemini_key_status() -> tuple[str, str]:
    """Return (status, message) for Gemini API key diagnostics."""
    key = get_secret("GEMINI_API_KEY")
    if not key:
        return "missing", "Clé absente"
    if key.lower() in GEMINI_KEY_PLACEHOLDERS or "votre_cle" in key.lower():
        return "placeholder", "Placeholder détecté — remplacez par une vraie clé"
    if not (key.startswith("AIza") or key.startswith("AQ.")):
        return "invalid", "Format invalide (doit commencer par AIza ou AQ.)"
    if key.startswith("AIza") and len(key) < 35:
        return "invalid", "Clé AIza trop courte (copie incomplète ?)"
    if key.startswith("AQ.") and len(key) < 20:
        return "invalid", "Clé AQ. trop courte (copie incomplète ?)"
    prefix = key[:8] if key.startswith("AIza") else key[:6]
    return "ok", f"Format OK ({prefix}…)"


def validate_groq_api_key(key: str = "") -> tuple[bool, str]:
    """Check Groq API key format (does not call the network)."""
    value = normalize_secret(key) if key else get_secret("GROQ_API_KEY")
    if not value:
        return False, "GROQ_API_KEY absente dans les secrets."
    lower = value.lower()
    if lower in GROQ_KEY_PLACEHOLDERS or "..." in value or "votre_cle" in lower:
        return False, "Placeholder détecté — remplacez par une vraie clé `gsk_...`."
    if not value.startswith("gsk_"):
        return False, "Format invalide : la clé Groq doit commencer par `gsk_`."
    if len(value) < 50:
        return False, (
            f"Clé trop courte ({len(value)} caractères) — "
            "recopiez la clé complète depuis console.groq.com/keys."
        )
    return True, "format OK"


def render_groq_key_help() -> None:
    """Actionable help when Groq rejects the API key."""
    st.markdown(
        """
**Clé Groq refusée (401 Invalid API Key)**

1. Créez une **nouvelle clé** sur [console.groq.com/keys](https://console.groq.com/keys)
2. **Streamlit Cloud** : *Manage app → Settings → Secrets* :
   ```toml
   GROQ_API_KEY = "gsk_votre_cle_complete"
   GEMINI_API_KEY = "AQ...."   # ou AIza... — secours auto si quota Groq
   ```
3. **Save** puis **Reboot app** (obligatoire après changement de secrets)
4. Vérifiez : pas d'espace avant/après, guillemets doubles, clé non révoquée

*En local*, mettez la même clé dans `.streamlit/secrets.toml`.
        """
    )


def verify_groq_api_key_live() -> tuple[bool, str, list[str], bool]:
    """Validate Groq key format and ping GET /models."""
    format_ok, format_msg = validate_groq_api_key()
    if not format_ok:
        return False, format_msg, [], False

    api_key = get_secret("GROQ_API_KEY")
    try:
        response = requests.get(
            f"{GROQ_API_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Réseau Groq inaccessible : {exc}", list(GROQ_PREFERRED_MODELS), False

    if response.status_code == 401:
        return False, (
            "Clé Groq refusée (401 Invalid API Key). "
            "Recréez une clé sur console.groq.com/keys et mettez à jour vos secrets "
            "(Streamlit Cloud → Save → Reboot app)."
        ), [], False

    if not response.ok:
        return (
            False,
            f"Groq API erreur HTTP {response.status_code}.",
            list(GROQ_PREFERRED_MODELS),
            False,
        )

    model_ids = [
        item["id"]
        for item in response.json().get("data", [])
        if not _is_groq_model_skipped(item["id"])
    ]
    if not model_ids:
        return True, "Clé valide — liste modèles vide.", list(GROQ_PREFERRED_MODELS), False
    return True, f"Clé valide — {len(model_ids)} modèle(s) chat.", model_ids, True


def render_gemini_key_help() -> None:
    """Show actionable help when Gemini rejects the API key."""
    st.error("Clé Gemini invalide ou refusée par Google.")
    st.markdown(
        """
**Corrections à vérifier :**

1. **Clé Gemini** sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   *(format `AIza...` ou nouveau format `AQ....`)*.
2. **Collez la clé complète**, sans espace avant/après.
3. **Streamlit Cloud** : *Manage app → Settings → Secrets* :
   ```toml
   GEMINI_API_KEY = "AQ.Ab8..."
   ```
4. **Redéployez** l'app après modification (*Reboot app*).
        """
    )


def pdf_fingerprint(pdf_bytes: bytes) -> str:
    """Stable hash for cache keys based on PDF content."""
    return hashlib.sha256(pdf_bytes).hexdigest()


# ---------------------------------------------------------------------------
# PDF extraction (native text + OCR fallback)
# ---------------------------------------------------------------------------


def extract_text_native(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF using pdfplumber."""
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _extract_gemini_text(data: dict[str, Any]) -> str:
    """Parse text from a Gemini generateContent JSON response."""
    candidates = data.get("candidates", [])
    if not candidates:
        block_reason = data.get("promptFeedback", {})
        raise RuntimeError(f"Gemini : réponse vide. {block_reason or data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini n'a renvoyé aucun texte.")
    return text


def is_aq_gemini_key(key: str = "") -> bool:
    """Detect Google authorization keys (AQ.) issued by AI Studio since 2025."""
    value = key.strip() if key else get_secret("GEMINI_API_KEY")
    return value.startswith("AQ.")


def should_use_gemini(**_kwargs: Any) -> bool:
    """Whether a Gemini API key is configured."""
    return bool(get_secret("GEMINI_API_KEY"))


def can_use_gemini_fallback() -> bool:
    """Gemini key present — may be used when Groq quota is hit."""
    return bool(get_secret("GEMINI_API_KEY"))


def get_ai_provider_preference() -> str:
    """Legacy secret — analysis always uses automatic provider selection."""
    pref = get_secret("AI_PROVIDER", "auto").lower().strip()
    if pref in {"groq", "gemini", "openai", "auto"}:
        return pref
    return "auto"


def configured_llm_backends() -> dict[str, bool]:
    """Which LLM backends have API keys configured."""
    gemini_key = get_secret("GEMINI_API_KEY")
    return {
        "groq": bool(get_secret("GROQ_API_KEY")),
        "gemini": bool(gemini_key),
        "openai": bool(get_secret("OPENAI_API_KEY")),
    }


def prefers_groq_batching() -> bool:
    """Whether to use Groq-optimized batch matching."""
    if st.session_state.get("groq_quota_exhausted"):
        return False
    active = st.session_state.get("llm_backend_active")
    if active:
        return active == "groq"
    chain = get_llm_provider_chain()
    return bool(chain and chain[0] == "groq")


def get_llm_provider_chain() -> list[str]:
    """Auto order: Groq (free) → Gemini → OpenAI; skips exhausted backends."""
    backends = configured_llm_backends()
    chain: list[str] = []

    sticky = st.session_state.get("llm_backend_active", "")
    if sticky in {"groq", "gemini", "openai"} and backends.get(sticky):
        chain.append(sticky)

    if backends.get("groq") and not st.session_state.get("groq_quota_exhausted"):
        if "groq" not in chain:
            chain.append("groq")
    if backends.get("gemini") and "gemini" not in chain:
        chain.append("gemini")
    if backends.get("openai") and "openai" not in chain:
        chain.append("openai")

    return chain


def resolve_llm_provider() -> str:
    """Primary backend for display — first available in auto chain."""
    chain = get_llm_provider_chain()
    return chain[0] if chain else "none"


def ai_setup_status() -> tuple[bool, str]:
    """Return (ready, message) for AI configuration."""
    backends = configured_llm_backends()
    chain = get_llm_provider_chain()
    labels = [name for name, ok in backends.items() if ok]

    if chain:
        names = {"groq": "Groq", "gemini": "Gemini", "openai": "OpenAI"}
        order = " → ".join(names[p] for p in chain)
        return True, f"Sélection auto IA — ordre de bascule : {order}."

    if labels:
        exhausted = st.session_state.get("groq_quota_exhausted") and backends.get("groq")
        if exhausted and not backends.get("gemini") and not backends.get("openai"):
            return False, (
                "Quota Groq atteint. Ajoutez GEMINI_API_KEY ou OPENAI_API_KEY "
                "en secours, ou attendez 1–2 minutes."
            )

    return False, (
        "Aucune clé IA. Ajoutez au moins GROQ_API_KEY (gratuit) "
        "dans `.streamlit/secrets.toml` ou Streamlit Cloud Secrets."
    )


def render_ai_setup_help() -> None:
    """Blocking help when AI is not configured."""
    st.error("Configuration IA requise")
    _, message = ai_setup_status()
    st.markdown(message)
    st.markdown(
        """
### Clés IA (sélection automatique)

L'analyse choisit **automatiquement** le moteur disponible : Groq → Gemini → OpenAI.

1. **Groq** (gratuit) — [console.groq.com/keys](https://console.groq.com/keys)
2. **Gemini** (secours, gratuit) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey) *(AIza ou AQ.)*
3. **OpenAI** (secours, crédits) — optionnel

```toml
GROQ_API_KEY = "gsk_votre_cle"
GEMINI_API_KEY = "AQ...."   # ou AIza... — secours auto si quota Groq
```

Redémarrez : `Ctrl+C` puis `streamlit run app.py`
        """
    )


def _chat_completion(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
) -> str:
    """Shared chat completion helper for OpenAI-compatible APIs."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if "429" in err or "insufficient_quota" in err or "credit_balance" in err:
            raise RuntimeError(
                "Crédits OpenAI épuisés (429). Utilisez Groq gratuit : "
                "console.groq.com/keys → GROQ_API_KEY (+ GEMINI_API_KEY en secours)"
            ) from exc
        raise

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Le modèle IA n'a renvoyé aucun texte.")
    try:
        from services.llm_usage import record_chat_usage

        record_chat_usage(
            provider="openai",
            model=model,
            usage=getattr(response, "usage", None),
            prompt_text=f"{system_prompt}\n{user_prompt}",
            completion_text=content,
        )
    except Exception:  # noqa: BLE001
        pass
    return content


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_groq_model_ids(api_key_fingerprint: str) -> tuple[list[str], bool]:
    """Fetch live chat model list from Groq API (cached when API responds OK)."""
    models, live, _error = _fetch_groq_models_from_api()
    return models, live


def _fetch_groq_models_from_api() -> tuple[list[str], bool, str]:
    """Return (model_ids, live_from_api, error_message)."""
    ok, message, models, live = verify_groq_api_key_live()
    if not ok:
        return list(GROQ_PREFERRED_MODELS), False, message
    return models, live, ""


def _groq_model_rank(model_id: str) -> tuple[int, str]:
    """Sort key: lower = higher priority."""
    try:
        return GROQ_PREFERRED_MODELS.index(model_id), model_id
    except ValueError:
        pass
    lower = model_id.lower()
    if "gpt-oss-20b" in lower:
        return 10, model_id
    if "scout" in lower and "llama-4" in lower:
        return 15, model_id
    if "qwen" in lower:
        return 20, model_id
    if "kimi" in lower:
        return 25, model_id
    if "compound-mini" in lower or "compound-beta-mini" in lower:
        return 30, model_id
    if "llama-2" in lower:
        return 35, model_id
    if "gpt-oss-120b" in lower:
        return 45, model_id
    if "maverick" in lower:
        return 50, model_id
    if lower.startswith("llama-3") or lower.startswith("llama3"):
        return 90, model_id
    return 40, model_id


def _is_groq_model_skipped(model_id: str) -> bool:
    """Skip audio, embedding and moderation-only models."""
    lower = model_id.lower()
    if any(token in lower for token in GROQ_SKIP_MODEL_SUBSTRINGS):
        return True
    return False


def build_groq_model_priority(
    live_models: list[str],
    custom_model: str = "",
    *,
    live_from_api: bool = True,
) -> list[str]:
    """Build model try-order from the account's live model list."""
    live_set = set(live_models)
    ordered: list[str] = []

    cached = st.session_state.get("groq_working_model", "")
    if cached and (not live_from_api or cached in live_set):
        ordered.append(cached)

    if custom_model and (not live_from_api or custom_model in live_set):
        if custom_model in ordered:
            ordered.remove(custom_model)
        ordered.insert(0, custom_model)

    candidates = [
        model
        for model in live_models
        if not _is_groq_model_skipped(model) and (not live_from_api or model in live_set)
    ]
    candidates.sort(key=_groq_model_rank)

    for model in candidates:
        if model not in ordered:
            ordered.append(model)

    if not live_from_api:
        for model in GROQ_PREFERRED_MODELS:
            if model not in ordered:
                ordered.append(model)

    seen: set[str] = set()
    return [m for m in ordered if m and not (m in seen or seen.add(m))]


def _groq_chat_raw(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str | None = None,
    max_tokens: int = 1200,
) -> str:
    """Direct HTTP call to Groq chat completions (no json_mode — better compatibility)."""
    groq_key = api_key or get_secret("GROQ_API_KEY")
    json_instruction = (
        "\n\nIMPORTANT : réponds UNIQUEMENT avec un objet JSON valide, sans markdown."
    )
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = requests.post(
        f"{GROQ_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code} — {response.text[:250]}")

    data = response.json()
    content = data["choices"][0]["message"]["content"]
    if not content:
        raise RuntimeError("Réponse Groq vide.")
    content = content.strip()
    try:
        from services.llm_usage import record_chat_usage

        record_chat_usage(
            provider="groq",
            model=model,
            usage=data.get("usage"),
            prompt_text=f"{system_prompt}\n{user_prompt}",
            completion_text=content,
        )
    except Exception:  # noqa: BLE001
        pass
    return content


def _classify_groq_error(exc: Exception) -> str:
    """Short label for Groq model errors."""
    err = str(exc)
    lower = err.lower()
    if "429" in err or "rate limit" in lower or "limite" in lower:
        return "quota / rate limit"
    if "401" in err or "invalid api key" in lower:
        return "clé API invalide"
    if "404" in err or "n'existe pas" in lower or "does not exist" in lower:
        return "modèle indisponible"
    if "400" in err and ("décommission" in lower or "decommission" in lower or "hors service" in lower):
        return "modèle décommissionné"
    if "400" in err and ("terms" in lower or "conditions" in lower):
        return "conditions d'utilisation non acceptées"
    if "réponse groq vide" in lower or "empty" in lower:
        return "réponse vide"
    return err[:100]


def _is_groq_rate_limit(exc: Exception) -> bool:
    label = _classify_groq_error(exc)
    return "quota" in label or "rate limit" in label or "429" in str(exc)


def call_groq_text(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str | None = None,
    max_tokens: int = 1200,
) -> str:
    """Call Groq — uses live account models, caches the first working one."""
    if api_key:
        model = get_secret("GROQ_MODEL") or st.session_state.get("groq_working_model") or GROQ_MODEL
        for attempt in range(2):
            try:
                return _groq_chat_raw(
                    model,
                    system_prompt,
                    user_prompt,
                    api_key=api_key,
                    max_tokens=max_tokens,
                )
            except Exception as exc:  # noqa: BLE001
                if _is_groq_rate_limit(exc) and attempt == 0:
                    time.sleep(GROQ_RATE_LIMIT_RETRY_SEC)
                    continue
                raise
        raise RuntimeError("Appel Groq échoué avec la clé fournie.")

    format_ok, format_msg = validate_groq_api_key()
    if not format_ok:
        raise RuntimeError(format_msg)

    live_models, live_from_api, fetch_error = _fetch_groq_models_from_api()
    if fetch_error:
        raise RuntimeError(fetch_error)

    custom_model = get_secret("GROQ_MODEL")
    unique_models = build_groq_model_priority(
        live_models,
        custom_model,
        live_from_api=live_from_api,
    )

    errors: list[str] = []
    invalid_key = 0
    for model in unique_models:
        for attempt in range(2):
            try:
                result = _groq_chat_raw(model, system_prompt, user_prompt)
                st.session_state.groq_working_model = model
                st.session_state.active_llm_provider = f"Groq ({model})"
                return result
            except Exception as exc:  # noqa: BLE001
                label = _classify_groq_error(exc)
                if _is_groq_rate_limit(exc):
                    if attempt == 0:
                        time.sleep(GROQ_RATE_LIMIT_RETRY_SEC)
                        continue
                    raise GroqRateLimitError(
                        "Quota Groq atteint (rate limit). Attendez 1–2 minutes "
                        "ou configurez GEMINI_API_KEY / OPENAI_API_KEY en secours."
                    ) from exc
                errors.append(f"{model}: {label}")
                if "clé api invalide" in label or "401" in str(exc):
                    invalid_key += 1
                if st.session_state.get("groq_working_model") == model:
                    st.session_state.pop("groq_working_model", None)
                break

    if invalid_key and invalid_key >= len(unique_models):
        raise RuntimeError(
            "Clé Groq refusée (401 Invalid API Key) sur tous les appels.\n\n"
            "La clé dans vos secrets Streamlit Cloud est invalide, expirée ou révoquée.\n"
            "Recréez une clé sur console.groq.com/keys → Secrets → Save → Reboot app."
        )

    if not live_from_api:
        raise RuntimeError(
            "Impossible de joindre l'API Groq avec votre clé.\n"
            + "\n".join(errors[:4])
        )

    available = ", ".join(unique_models[:8]) if unique_models else "aucun"
    raise RuntimeError(
        "Aucun modèle Groq utilisable sur votre compte.\n"
        + "\n".join(errors[:8])
        + f"\n\nModèles listés par l'API : {available}.\n"
        "Laissez `GROQ_MODEL` vide pour la détection auto, ou définissez un modèle "
        "de la liste sur console.groq.com/docs/models."
    )


def call_gemini_text(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str | None = None,
) -> str:
    """Call Gemini via native REST API."""
    return _gemini_generate_content(
        parts=[{"text": user_prompt}],
        system_prompt=system_prompt,
        api_key=api_key,
    )


def call_openai_text(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str | None = None,
) -> str:
    """Call OpenAI chat completions."""
    openai_key = api_key or get_secret("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY manquante.")

    return _chat_completion(
        api_key=openai_key,
        base_url=None,
        model=OPENAI_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def call_openai_vision(ocr_prompt: str, image_b64: str) -> str:
    """OCR a single page via OpenAI vision."""
    openai_key = get_secret("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY manquante pour l'OCR.")

    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ocr_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def _fetch_gemini_models_from_api(api_key: str | None = None) -> tuple[list[str], bool]:
    """List models supporting generateContent for this API key."""
    gemini_key = api_key or get_secret("GEMINI_API_KEY")
    if not gemini_key:
        return list(GEMINI_PREFERRED_MODELS), False

    try:
        response = requests.get(
            f"{GEMINI_API_BASE}/models",
            headers={"x-goog-api-key": gemini_key},
            timeout=30,
        )
        if not response.ok:
            return list(GEMINI_PREFERRED_MODELS), False

        model_ids = [
            item["name"].replace("models/", "")
            for item in response.json().get("models", [])
            if "generateContent" in item.get("supportedGenerationMethods", [])
        ]
        if model_ids:
            return model_ids, True
        return list(GEMINI_PREFERRED_MODELS), False
    except Exception:  # noqa: BLE001
        return list(GEMINI_PREFERRED_MODELS), False


def _gemini_model_rank(model_id: str) -> tuple[int, str]:
    try:
        return GEMINI_PREFERRED_MODELS.index(model_id), model_id
    except ValueError:
        pass
    lower = model_id.lower()
    if "2.5-flash-lite" in lower:
        return 5, model_id
    if "2.5-flash" in lower:
        return 3, model_id
    if "3" in lower and "flash" in lower:
        return 8, model_id
    if "flash" in lower:
        return 15, model_id
    return 50, model_id


def build_gemini_model_priority(live_models: list[str], *, live_from_api: bool) -> list[str]:
    """Order Gemini models: preferred that exist on account, then other live models."""
    if not live_from_api:
        return list(GEMINI_PREFERRED_MODELS)

    live_set = set(live_models)
    ordered: list[str] = []
    for model in GEMINI_PREFERRED_MODELS:
        if model in live_set:
            ordered.append(model)
    rest = sorted(
        [m for m in live_models if m not in ordered and "embed" not in m.lower()],
        key=_gemini_model_rank,
    )
    ordered.extend(rest)
    for model in GEMINI_PREFERRED_MODELS:
        if model not in ordered:
            ordered.append(model)
    seen: set[str] = set()
    return [m for m in ordered if m and not (m in seen or seen.add(m))]


def _gemini_supports_interactions(model: str) -> bool:
    lower = model.lower()
    return any(token in lower for token in ("gemini-3", "gemini-3.")) or model in GEMINI_INTERACTION_MODELS


@contextlib.contextmanager
def _gemini_isolated_credentials():
    """Avoid mixing Application Default Credentials with API-key auth (AQ. keys)."""
    saved: dict[str, str] = {}
    for var in (
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCLOUD_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_GENAI_USE_VERTEXAI",
    ):
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        yield
    finally:
        os.environ.update(saved)


@st.cache_resource(show_spinner=False)
def _cached_gemini_client(api_key_fingerprint: str, api_key: str):
    """Singleton Gemini SDK client per API key."""
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options=types.HttpOptions(api_version="v1beta"),
    )


def _gemini_client_for_key(api_key: str):
    fp = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return _cached_gemini_client(fp, api_key)


def _gemini_client():
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY manquante.")
    return _gemini_client_for_key(api_key)


def _parts_to_sdk(parts: list[dict[str, Any]]) -> list[Any]:
    from google.genai import types

    sdk_parts: list[Any] = []
    for part in parts:
        if "text" in part:
            sdk_parts.append(types.Part.from_text(text=part["text"]))
        elif "inline_data" in part:
            inline = part["inline_data"]
            sdk_parts.append(
                types.Part.from_bytes(
                    data=base64.standard_b64decode(inline["data"]),
                    mime_type=inline["mime_type"],
                )
            )
    return sdk_parts


def _parts_to_interaction_input(parts: list[dict[str, Any]]) -> Any:
    """Build Interactions API input (text + optional image)."""
    interaction_input: list[dict[str, Any]] = []
    for part in parts:
        if "text" in part:
            interaction_input.append({"type": "text", "text": part["text"]})
        elif "inline_data" in part:
            inline = part["inline_data"]
            interaction_input.append(
                {
                    "type": "image",
                    "data": inline["data"],
                    "mime_type": inline.get("mime_type", "image/png"),
                }
            )
    if len(interaction_input) == 1 and interaction_input[0]["type"] == "text":
        return interaction_input[0]["text"]
    return interaction_input


def _gemini_via_interactions(
    parts: list[dict[str, Any]],
    system_prompt: str | None,
    model: str,
) -> tuple[str | None, str | None]:
    """Try Gemini Interactions API (Gemini 3.x models only)."""
    try:
        with _gemini_isolated_credentials():
            client = _gemini_client()
            kwargs: dict[str, Any] = {
                "model": model,
                "input": _parts_to_interaction_input(parts),
            }
            if system_prompt:
                kwargs["system_instruction"] = system_prompt
            interaction = client.interactions.create(**kwargs)
            output = getattr(interaction, "output_text", None)
            if output and str(output).strip():
                return str(output).strip(), None
            return None, f"{model}/Interactions: réponse vide"
    except Exception as exc:  # noqa: BLE001
        return None, f"{model}/Interactions: {str(exc)[:160]}"


def _gemini_via_sdk(
    parts: list[dict[str, Any]],
    system_prompt: str | None,
    model: str,
    *,
    api_key: str,
) -> tuple[str | None, str | None]:
    """Try Gemini generateContent via google-genai SDK."""
    try:
        from google.genai import types

        with _gemini_isolated_credentials():
            client = _gemini_client_for_key(api_key)
            config = types.GenerateContentConfig(temperature=0.2)
            if system_prompt:
                config.system_instruction = system_prompt
            response = client.models.generate_content(
                model=model,
                contents=_parts_to_sdk(parts),
                config=config,
            )
            if response.text:
                try:
                    from services.llm_usage import record_llm_usage, usage_from_gemini_payload

                    prompt_n, completion_n, total_n = usage_from_gemini_payload(response)
                    record_llm_usage(
                        provider="gemini",
                        model=model,
                        prompt_tokens=prompt_n,
                        completion_tokens=completion_n,
                        total_tokens=total_n,
                        prompt_text=system_prompt or "",
                        completion_text=response.text.strip(),
                    )
                except Exception:  # noqa: BLE001
                    pass
                return response.text.strip(), None
            return None, f"{model}/SDK: réponse vide"
    except Exception as exc:  # noqa: BLE001
        return None, f"{model}/SDK: {str(exc)[:160]}"


def _gemini_via_rest(
    parts: list[dict[str, Any]],
    system_prompt: str | None,
    model: str,
    *,
    api_key: str,
) -> tuple[str | None, str | None]:
    """Try Gemini REST generateContent (AIza and AQ. keys via x-goog-api-key)."""
    if not api_key:
        return None, "REST: clé absente"

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2},
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    header_attempts: list[dict[str, str]] = [
        {"Content-Type": "application/json", "x-goog-api-key": api_key},
    ]
    if is_aq_gemini_key(api_key):
        header_attempts.append(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        )

    last_error = ""
    for headers in header_attempts:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=90)
            if response.ok:
                data = response.json()
                text = _extract_gemini_text(data)
                try:
                    from services.llm_usage import record_llm_usage, usage_from_gemini_payload

                    prompt_n, completion_n, total_n = usage_from_gemini_payload(data)
                    record_llm_usage(
                        provider="gemini",
                        model=model,
                        prompt_tokens=prompt_n,
                        completion_tokens=completion_n,
                        total_tokens=total_n,
                        prompt_text=system_prompt or "",
                        completion_text=text,
                    )
                except Exception:  # noqa: BLE001
                    pass
                return text, None
            last_error = f"HTTP {response.status_code} — {response.text[:120]}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:120]

    return None, f"{model}/REST: {last_error}"


def _gemini_generate_content(
    parts: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    api_key: str | None = None,
) -> str:
    """Call Gemini — supports AIza and AQ. authorization keys."""
    gemini_key = api_key or get_secret("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY manquante.")

    key_label = "AQ." if is_aq_gemini_key(gemini_key) else "AIza"
    live_models, live_from_api = _fetch_gemini_models_from_api(gemini_key)
    models_to_try = build_gemini_model_priority(live_models, live_from_api=live_from_api)

    errors: list[str] = []
    for model in models_to_try:
        text, err = _gemini_via_sdk(parts, system_prompt, model, api_key=gemini_key)
        if text:
            if not api_key:
                st.session_state.active_llm_provider = f"Gemini ({model}, SDK, {key_label})"
            return text
        if err:
            errors.append(err)

        text, err = _gemini_via_rest(parts, system_prompt, model, api_key=gemini_key)
        if text:
            if not api_key:
                st.session_state.active_llm_provider = f"Gemini ({model}, REST, {key_label})"
            return text
        if err:
            errors.append(err)

        if _gemini_supports_interactions(model):
            text, err = _gemini_via_interactions(parts, system_prompt, model)
            if text:
                if not api_key:
                    st.session_state.active_llm_provider = (
                        f"Gemini ({model}, Interactions, {key_label})"
                    )
                return text
            if err:
                errors.append(err)

    available = ", ".join(models_to_try[:6]) if models_to_try else "aucun"
    raise RuntimeError(
        f"Connexion Gemini impossible (clé {key_label}).\n"
        + "\n".join(errors[:6])
        + f"\n\nModèles testés : {available}.\n"
        "Vérifiez aistudio.google.com/apikey — activez Generative Language API "
        "sur votre projet Google Cloud."
    )


def test_gemini_connection() -> tuple[bool, str]:
    """Quick Gemini connectivity check (AIza or AQ. keys)."""
    status, message = gemini_key_status()
    if status != "ok":
        return False, message
    try:
        reply = _gemini_generate_content(
            parts=[{"text": 'Réponds uniquement: {"status":"OK"}'}],
            system_prompt="Réponds en JSON valide uniquement.",
        )
        return True, f"Connexion OK — {reply[:40]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:400]


def test_groq_connection() -> tuple[bool, str]:
    key_ok, key_msg, _models, live = verify_groq_api_key_live()
    if not key_ok:
        return False, key_msg
    try:
        reply = call_groq_text('Réponds en JSON.', '{"status":"OK"}')
        prefix = "Connexion OK"
        if live:
            prefix += " (modèles API vérifiés)"
        return True, f"{prefix} — {reply[:40]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:400]


def test_openai_connection() -> tuple[bool, str]:
    """Quick OpenAI connectivity check."""
    try:
        reply = call_openai_text(
            "Réponds uniquement en JSON.", '{"status":"OK"}'
        )
        return True, f"Connexion OK — {reply[:40]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


def test_ai_connection() -> tuple[bool, str, str]:
    """Test auto LLM chain — returns (ok, message, provider label)."""
    ready, status_msg = ai_setup_status()
    if not ready:
        return False, status_msg, "—"

    try:
        reply = call_llm('Réponds en JSON.', '{"status":"OK"}')
        label = st.session_state.get("active_llm_provider", "Auto")
        return True, f"Connexion OK — {reply[:40]}", label
    except RuntimeError as exc:
        st.session_state.pop("llm_backend_active", None)
        return False, str(exc)[:400], "—"


def extract_text_ocr(pdf_bytes: bytes) -> str:
    """OCR fallback using Gemini vision, or OpenAI vision if Gemini fails."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = min(len(doc), MAX_OCR_PAGES)
    text_parts: list[str] = []

    ocr_prompt = (
        "Tu es un OCR expert. Extrais l'intégralité du texte visible de ce CV. "
        "Conserve la structure (sections, listes). "
        "Retourne uniquement le texte brut, sans commentaire ni markdown."
    )

    gemini_failed = False
    for page_index in range(page_count):
        page = doc[page_index]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        image_b64 = base64.standard_b64encode(pixmap.tobytes("png")).decode("ascii")

        page_text = ""
        if configured_llm_backends().get("gemini") and not gemini_failed:
            try:
                page_text = _gemini_generate_content(
                    parts=[
                        {"text": ocr_prompt},
                        {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    ],
                )
            except RuntimeError:
                gemini_failed = True

        if not page_text and get_secret("OPENAI_API_KEY"):
            page_text = call_openai_vision(ocr_prompt, image_b64)

        if page_text:
            text_parts.append(page_text.strip())

    doc.close()

    if not text_parts and not get_secret("OPENAI_API_KEY") and not get_secret("GEMINI_API_KEY"):
        raise RuntimeError("OCR requis — configurez GEMINI_API_KEY ou OPENAI_API_KEY.")

    return "\n".join(text_parts).strip()


def extract_text_ocr_gemini(pdf_bytes: bytes) -> str:
    """Backward-compatible alias."""
    return extract_text_ocr(pdf_bytes)


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
    """Extract and parse JSON from an LLM response (tolerates markdown / extra text)."""
    if not raw or not raw.strip():
        raise json.JSONDecodeError("Réponse vide", raw or "", 0)

    text = raw.strip()

    if "```" in text:
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()

    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        for variant in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
            try:
                parsed = json.loads(variant)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

    raise last_error or json.JSONDecodeError("JSON introuvable", raw, 0)


ATS_MATCH_SYSTEM_PROMPT = """Tu es un expert ATS (Applicant Tracking System) et recruteur senior.
Analyse en profondeur la correspondance entre le CV du candidat et l'offre d'emploi.

MÉTHODOLOGIE OBLIGATOIRE :

1) COMPÉTENCES (cœur de l'analyse)
   Du CV, identifie : compétences techniques, compétences transversales, outils, certifications, langages.
   De l'offre, extrais : compétences obligatoires, compétences souhaitées, technos/stack de l'entreprise.
   Compare et classe chaque compétence clé de l'offre en : presente / partielle / manquante.

2) EXPÉRIENCES PROFESSIONNELLES
   Du CV : intitulés de postes, missions réalisées, durées, secteurs.
   De l'offre : niveau demandé (junior, confirmé, senior), type de missions attendues.
   Détermine si le candidat a déjà réalisé ce qui est demandé.

3) SCORE ATS (0-100) — calcule chaque sous-score puis le score global pondéré :
   - score_competences (40 %) : matching compétences techniques + outils + langages + certifications
   - score_experiences (25 %) : adéquation parcours, missions passées, durée, secteur, niveau
   - score_titre (20 %) : alignement poste visé / titre CV / intitulé offre
   - score_localisation (15 %) : lieu et type de contrat

Réponds UNIQUEMENT en JSON valide, sans markdown :
{
  "score_correspondance": 78,
  "score_competences": 82,
  "score_experiences": 70,
  "score_titre": 85,
  "score_localisation": 90,
  "synthese_ats": "Phrase de synthèse en 1-2 lignes sur la pertinence globale",
  "titre_cv_recommande": "Titre de CV optimisé pour cette offre",
  "analyse_competences": {
    "cv_techniques": ["compétence1"],
    "cv_transversales": ["support"],
    "cv_outils": ["Jira"],
    "cv_certifications": ["CCNA"],
    "cv_langages": ["Python"],
    "offre_obligatoires": ["compétence exigée"],
    "offre_souhaitees": ["compétence souhaitée"],
    "offre_technos": ["techno entreprise"],
    "presentes": ["compétence matchée"],
    "partielles": ["compétence partielle"],
    "manquantes": ["compétence absente"]
  },
  "analyse_experiences": {
    "niveau_offre": "confirme",
    "niveau_cv": "confirme",
    "alignement_niveau": "bon|moyen|faible",
    "experiences_pertinentes": [
      {"poste": "...", "duree": "...", "missions_liees": "...", "secteur": "..."}
    ],
    "ecarts": ["écart concret par rapport à l'offre"]
  },
  "mots_cles_manquants": ["mot1", "mot2"],
  "modifications_cv": [
    "Modification 1 concrète et actionnable sur le CV pour cette offre",
    "Modification 2",
    "Modification 3",
    "Modification 4",
    "Modification 5"
  ],
  "conseils": ["Conseil 1", "Conseil 2", "Conseil 3"]
}

Règles :
- Sois strict et réaliste comme un ATS professionnel (ne mets pas 90% si des compétences clés manquent).
- modifications_cv : 5 à 8 actions précises (formulations CV, sections à ajouter, mots-clés ATS à intégrer).
- mots_cles_manquants : 3 à 10 termes de l'offre absents ou faibles dans le CV.
- Réponds en français."""


def _call_llm_backend(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str | None = None,
    max_tokens: int = 1200,
) -> str:
    """Invoke a single LLM backend by id."""
    try:
        from services.llm_usage import bind_current_user_from_streamlit

        bind_current_user_from_streamlit()
    except Exception:  # noqa: BLE001
        pass
    if provider == "groq":
        if not api_key:
            st.session_state.active_llm_provider = "Groq (gratuit)"
        return call_groq_text(
            system_prompt,
            user_prompt,
            api_key=api_key,
            max_tokens=max_tokens,
        )
    if provider == "gemini":
        if not api_key:
            st.session_state.active_llm_provider = "Gemini"
        return call_gemini_text(system_prompt, user_prompt, api_key=api_key)
    if provider == "openai":
        if not api_key:
            st.session_state.active_llm_provider = "OpenAI"
        return call_openai_text(system_prompt, user_prompt, api_key=api_key)
    raise RuntimeError(f"Moteur IA inconnu : {provider}")


def call_llm_direct(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str,
    max_tokens: int = ATS_MATCH_MAX_TOKENS,
) -> str:
    """Thread-safe LLM call with an explicit provider/key (parallel matching)."""
    return _call_llm_backend(
        provider,
        system_prompt,
        user_prompt,
        api_key=api_key,
        max_tokens=max_tokens,
    )


def _append_llm_switch_notice(from_provider: str, to_provider: str, reason: str) -> None:
    labels = {"groq": "Groq", "gemini": "Gemini", "openai": "OpenAI"}
    st.session_state.setdefault("analysis_notices", []).append(
        {
            "level": "warning",
            "text": (
                f"{labels.get(from_provider, from_provider)} indisponible ({reason}) — "
                f"bascule sur {labels.get(to_provider, to_provider)}."
            ),
        }
    )


def call_llm(system_prompt: str, user_prompt: str, *, max_tokens: int = 1200) -> str:
    """Auto-select Groq, Gemini or OpenAI — no manual preference required."""
    chain = get_llm_provider_chain()
    if not chain:
        raise RuntimeError(
            "Aucune clé IA utilisable. Ajoutez GROQ_API_KEY, GEMINI_API_KEY ou OPENAI_API_KEY."
        )

    errors: list[str] = []
    for idx, provider in enumerate(chain):
        try:
            result = _call_llm_backend(
                provider,
                system_prompt,
                user_prompt,
                max_tokens=max_tokens,
            )
            st.session_state.llm_backend_active = provider
            return result
        except GroqRateLimitError as exc:
            st.session_state.groq_quota_exhausted = True
            if st.session_state.get("llm_backend_active") == "groq":
                st.session_state.pop("llm_backend_active", None)
            errors.append(f"Groq : quota / rate limit")
            if idx + 1 < len(chain):
                _append_llm_switch_notice("groq", chain[idx + 1], "quota atteint")
            continue
        except RuntimeError as exc:
            err = str(exc)
            errors.append(f"{provider} : {err[:120]}")
            if "401" in err or "invalid api key" in err.lower():
                if provider == "groq":
                    st.session_state.groq_quota_exhausted = True
            if idx + 1 < len(chain):
                _append_llm_switch_notice(provider, chain[idx + 1], "erreur")
            continue

    raise RuntimeError(
        "Aucun moteur IA disponible pour cette requête.\n"
        + "\n".join(errors[:4])
        + "\n\nAjoutez plusieurs clés (Groq + Gemini AQ./AIza…) pour la bascule auto, "
        "ou attendez 1–2 minutes si seul Groq est configuré."
    )


CRITERIA_PLACEHOLDER_HINTS = (
    "intitulé du poste",
    "ville ou région",
    "pays en français",
    "requête courte optimisée",
    "moteur d'emploi",
    "compétences clés",
    "alternance, stage, freelance ou tous",
)

CRITERIA_SYSTEM_PROMPT = """Tu es un expert RH et recruteur tech.
Analyse le CV fourni et extrais un profil candidat complet pour la recherche d'emploi.

INTERDIT : ne recopie jamais les instructions, placeholders ou descriptions de champs.
Chaque valeur doit provenir du contenu du CV (ou être déduite du profil).

Retourne UNIQUEMENT un objet JSON valide avec ces clés :
- metier : intitulé de poste concret visé
- query_recherche : requête courte pour moteur d'emploi (métier + compétence clé, sans ville)
- competences_techniques : tableau de compétences techniques (ex: Windows Server, VMware, Cisco, PHP…)
- soft_skills : tableau de compétences transversales (ex: support, gestion incidents, documentation…)
- outils : tableau d'outils maîtrisés (ex: Jira, Git, Mailcow, Active Directory…)
- langages : tableau de langages (ex: Python, Java, PHP…)
- experiences : tableau d'objets {poste, entreprise, duree, missions, secteur}
- diplomes_certifications : tableau de diplômes et certifications
- secteurs : tableau de secteurs d'activité
- niveau_experience : junior, confirme ou senior
- mots_cles : tableau de 5 à 10 mots-clés dominants
- mobilite_geographique : texte libre (si mentionné dans le CV, sinon "")
- disponibilites : texte libre (si mentionné, sinon "")

Exemple valide :
{"metier":"Technicien Systèmes et Réseau","query_recherche":"Technicien systèmes réseau Linux","competences_techniques":["Linux","Windows Server","VMware","Cisco"],"soft_skills":["Support N2","Gestion incidents","Documentation"],"outils":["Active Directory","Mailcow","Git"],"langages":["Python","Bash"],"experiences":[{"poste":"Technicien support","entreprise":"ACME","duree":"2020-2024","missions":"Administration serveurs Linux, virtualisation VMware","secteur":"Informatique"}],"diplomes_certifications":["BTS SIO","Certification Cisco CCNA"],"secteurs":["Informatique","Télécoms"],"niveau_experience":"confirme","mots_cles":["Linux","Réseau","Active Directory"],"mobilite_geographique":"Île-de-France","disponibilites":"Immédiate"}"""

CRITERIA_RETRY_PROMPT = CRITERIA_SYSTEM_PROMPT + """

RAPPEL CRITIQUE : ta réponse précédente a recopié le modèle au lieu du CV.
Relis le CV ligne par ligne. Remplis metier, ville et mots_cles avec des termes EXACTS du document.
Réponds UNIQUEMENT en JSON, sans markdown."""

JOB_SEARCH_PLAN_PROMPT = """Tu es un expert recrutement.
Le candidat vise le poste : « {title} ».

Retourne UNIQUEMENT un objet JSON valide avec :
- metier : intitulé normalisé du poste visé
- query_recherche : requête courte pour moteur d'emploi (2 à 6 mots, sans ville)
- variantes : tableau de 2 à 4 intitulés proches ou synonymes (même famille de métier)

Exemple pour « Développeur Python » :
{{"metier":"Développeur Python","query_recherche":"Développeur Python backend","variantes":["Ingénieur logiciel Python","Développeur backend","Software engineer Python"]}}"""


def normalize_job_search_plan(raw: dict[str, Any], fallback_title: str) -> dict[str, Any]:
    """Normalize LLM job search plan with safe fallbacks."""
    title = " ".join(fallback_title.strip().split())
    metier = str(raw.get("metier") or title).strip() or title
    query = str(raw.get("query_recherche") or metier).strip() or title
    variants_raw = raw.get("variantes") or []
    variants: list[str] = []
    if isinstance(variants_raw, list):
        for item in variants_raw:
            text = str(item).strip()
            if text and text.lower() not in {metier.lower(), query.lower(), title.lower()}:
                variants.append(text)
    return {
        "metier": metier,
        "query_recherche": query,
        "variantes": variants[:4],
        "source_title": title,
    }


def build_job_search_plan(target_job_title: str) -> dict[str, Any]:
    """Use IA to derive search queries and similar titles from the user's target role."""
    title = " ".join(target_job_title.strip().split())
    if not title:
        return normalize_job_search_plan({}, "")

    system_prompt = "Tu réponds uniquement en JSON valide, sans markdown."
    user_prompt = JOB_SEARCH_PLAN_PROMPT.format(title=title)
    try:
        raw = call_llm(system_prompt, user_prompt)
        parsed = _parse_json_response(raw)
        if isinstance(parsed, dict):
            return normalize_job_search_plan(parsed, title)
    except Exception:  # noqa: BLE001
        pass
    return normalize_job_search_plan({"metier": title, "query_recherche": title}, title)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_build_job_search_plan(target_job_title: str) -> dict[str, Any]:
    return build_job_search_plan(target_job_title)


def criteria_looks_like_placeholder(criteria: dict[str, Any]) -> bool:
    """Detect when the LLM echoed prompt placeholders instead of CV data."""
    if not criteria:
        return True

    blob = json.dumps(criteria, ensure_ascii=False).lower()
    if sum(1 for hint in CRITERIA_PLACEHOLDER_HINTS if hint in blob) >= 2:
        return True

    metier = str(criteria.get("metier", "")).strip().lower()
    if len(metier) < 4 or "intitulé" in metier or "poste visé" in metier:
        return True

    query = str(criteria.get("query_recherche", "")).strip().lower()
    if "requête courte" in query or "optimisée pour" in query or len(query) < 4:
        return True

    mots = criteria.get("mots_cles") or criteria.get("competences_techniques") or []
    if not isinstance(mots, list) or len(mots) < 2:
        return True
    generic = {"liste", "de", "à", "a", "compétences", "clés", "cles", "5", "10"}
    if sum(1 for m in mots if str(m).lower().strip() in generic) >= 3:
        return True

    return False


def clean_job_title_from_line(line: str) -> str:
    """Remove address / postal-code prefix from a CV header line."""
    title = line.strip()
    title = re.sub(r"^.*?\(\d{5}\)\s*", "", title)
    title = re.sub(r"^\d{5}\s+", "", title)
    title = re.sub(r"^[0-9\s,.-]+\s+", "", title)
    return title.strip()[:100] or line.strip()[:100]


def heuristic_criteria_from_cv(cv_text: str) -> dict[str, Any]:
    """Fallback extraction when the LLM returns placeholder text."""
    lines = [line.strip() for line in cv_text.splitlines() if line.strip()]

    city_match = re.search(
        r"\b("
        r"Paris|Lyon|Marseille|Toulouse|Nice|Nantes|Montpellier|Strasbourg|"
        r"Bordeaux|Lille|Rennes|Reims|Grenoble|Dijon|Angers|Nîmes|Clermont-Ferrand|"
        r"Tours|Metz|Besançon|Orléans|Rouen|Caen|Mulhouse|Nancy|Avignon|Poitiers|"
        r"Limeil-Brévannes|Douala|Yaoundé|Libreville|Abidjan|Dakar|Bruxelles|Genève|Montréal"
        r")\b",
        cv_text,
        re.IGNORECASE,
    )
    ville = city_match.group(1).title() if city_match else ""

    skill_catalog = [
        "linux", "windows", "réseau", "reseau", "système", "systeme", "serveur",
        "active directory", "vmware", "docker", "kubernetes", "python", "java",
        "sql", "azure", "aws", "cybersécurité", "cybersecurite", "devops",
        "administrateur", "technicien", "support", "infrastructure", "cisco",
        "firewall", "backup", "virtualisation", "powershell", "bash",
    ]
    cv_lower = cv_text.lower()
    mots_cles = []
    for skill in skill_catalog:
        if skill in cv_lower and skill not in mots_cles:
            mots_cles.append(skill.title() if skill.isascii() else skill.capitalize())
        if len(mots_cles) >= 8:
            break

    job_keywords = (
        "administrateur", "technicien", "ingénieur", "ingenieur",
        "développeur", "developpeur", "consultant", "réseau", "systeme", "système",
    )
    metier = "Profil informatique"
    for line in lines[:12]:
        lower = line.lower()
        if any(k in lower for k in job_keywords):
            metier = clean_job_title_from_line(line)
            break

    query_parts = [metier]
    if mots_cles:
        query_parts.append(mots_cles[0])
    query_recherche = " ".join(query_parts)[:80]

    pays = "France"
    if ville.lower() in ("douala", "yaoundé", "libreville"):
        pays = "Cameroun"

    return {
        "metier": metier,
        "ville": ville,
        "pays": pays,
        "type_contrat": "CDI",
        "mots_cles": mots_cles or ["Informatique"],
        "competences_techniques": mots_cles or ["Informatique"],
        "soft_skills": [],
        "outils": [],
        "langages": [],
        "experiences": [],
        "diplomes_certifications": [],
        "secteurs": ["Informatique"],
        "niveau_experience": "confirme",
        "mobilite_geographique": "",
        "disponibilites": "",
        "query_recherche": query_recherche,
        "_heuristic": True,
    }


def normalize_cv_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize AI/heuristic CV profile payload."""
    metier = str(raw.get("metier", "")).strip()
    mots_raw = raw.get("mots_cles") or raw.get("competences_techniques") or []
    if isinstance(mots_raw, str):
        mots_cles = [m.strip() for m in mots_raw.split(",") if m.strip()]
    elif isinstance(mots_raw, list):
        mots_cles = [str(m).strip() for m in mots_raw if str(m).strip()]
    else:
        mots_cles = []

    query = str(raw.get("query_recherche", "")).strip()
    if not query:
        query = metier

    def as_str_list(key: str) -> list[str]:
        value = raw.get(key, [])
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    experiences = raw.get("experiences", [])
    if not isinstance(experiences, list):
        experiences = []

    return {
        "metier": metier,
        "query_recherche": query,
        "competences_techniques": as_str_list("competences_techniques") or mots_cles[:8],
        "soft_skills": as_str_list("soft_skills"),
        "outils": as_str_list("outils"),
        "langages": as_str_list("langages"),
        "experiences": experiences[:8],
        "diplomes_certifications": as_str_list("diplomes_certifications"),
        "secteurs": as_str_list("secteurs"),
        "niveau_experience": str(raw.get("niveau_experience", "")).strip() or "confirme",
        "mots_cles": mots_cles[:10],
        "mobilite_geographique": str(raw.get("mobilite_geographique", "")).strip(),
        "disponibilites": str(raw.get("disponibilites", "")).strip(),
        "pays": str(raw.get("pays", "France")).strip() or "France",
    }


def normalize_criteria(criteria: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible alias used by legacy code paths."""
    profile = normalize_cv_profile(criteria)
    profile["ville"] = str(criteria.get("ville", "")).strip()
    profile["type_contrat"] = str(criteria.get("type_contrat", "")).strip()
    if criteria.get("_heuristic"):
        profile["_heuristic"] = True
    return profile


def extract_cv_profile(cv_text: str) -> dict[str, Any]:
    """Use AI to build a rich candidate profile from CV text."""
    user_prompt = f"CV du candidat — extrais les VRAIES valeurs :\n\n{cv_text[:12000]}"
    last_valid: dict[str, Any] | None = None

    for system_prompt in (CRITERIA_SYSTEM_PROMPT, CRITERIA_RETRY_PROMPT):
        try:
            raw = call_llm(system_prompt, user_prompt)
            parsed = normalize_cv_profile(_parse_json_response(raw))
            if not criteria_looks_like_placeholder(parsed):
                return parsed
            last_valid = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    if last_valid and not criteria_looks_like_placeholder(last_valid):
        return last_valid

    fallback = normalize_cv_profile(heuristic_criteria_from_cv(cv_text))
    fallback["_heuristic"] = True
    return fallback


def extract_search_criteria(cv_text: str) -> dict[str, Any]:
    """Backward-compatible wrapper."""
    return extract_cv_profile(cv_text)


def match_cv_to_job(
    cv_text: str,
    job: dict[str, Any],
    *,
    cv_profile: dict[str, Any] | None = None,
    target_job_title: str = "",
    user_profile: dict[str, Any] | None = None,
    llm_provider: str | None = None,
    llm_api_key: str | None = None,
) -> dict[str, Any]:
    """Compare CV against a single job offer and return ATS optimization advice."""
    system_prompt = ATS_MATCH_SYSTEM_PROMPT

    desc_limit = 5000
    job_summary = (
        f"Titre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '') or job.get('inferred_contract', '')}\n"
        f"Description :\n{job.get('description', '')[:desc_limit]}"
    )
    candidate_block = build_cv_match_context(
        cv_text,
        cv_profile,
        target_job_title,
        user_profile=user_profile,
    )
    user_prompt = f"{candidate_block}\n\nOffre à évaluer :\n{job_summary}"

    for attempt in range(2):
        try:
            prompt = system_prompt
            if attempt == 1:
                prompt += (
                    "\n\nRAPPEL CRITIQUE : retourne UNIQUEMENT l'objet JSON, "
                    "rien avant ni après. Pas de commentaire."
                )
            if llm_provider and llm_api_key:
                raw = call_llm_direct(
                    llm_provider,
                    prompt,
                    user_prompt,
                    api_key=llm_api_key,
                )
            else:
                raw = call_llm(prompt, user_prompt)
            return _normalize_match_result(_parse_json_response(raw), job)
        except (json.JSONDecodeError, TypeError, ValueError):
            if attempt == 0:
                continue
        except GroqRateLimitError:
            raise
        except RuntimeError as exc:
            if llm_provider and llm_api_key and attempt == 0:
                continue
            if llm_provider and llm_api_key:
                return fallback_match_result(job)
            raise exc

    return fallback_match_result(job)


BATCH_MATCH_SYSTEM_PROMPT = ATS_MATCH_SYSTEM_PROMPT + """

MODE BATCH : retourne un TABLEAU JSON avec EXACTEMENT un objet par offre, dans le MÊME ordre."""


def build_cv_match_context(
    cv_text: str,
    cv_profile: dict[str, Any] | None = None,
    target_job_title: str = "",
    user_profile: dict[str, Any] | None = None,
) -> str:
    """Structured candidate summary for matching prompts."""
    sections: list[str] = []

    if target_job_title.strip():
        sections.append(f"Poste visé (profil utilisateur) : {target_job_title.strip()}")

    if user_profile:
        from world_geo import format_profile_geo_summary

        geo_summary = format_profile_geo_summary(user_profile)
        if geo_summary:
            sections.append(f"Périmètre géographique cible (profil) : {geo_summary}")

    if cv_profile:
        metier = str(cv_profile.get("metier", "")).strip()
        if metier:
            sections.append(f"Métier extrait du CV : {metier}")
        niveau = str(cv_profile.get("niveau_experience", "")).strip()
        if niveau:
            sections.append(f"Niveau d'expérience : {niveau}")
        competences = (
            cv_profile.get("competences_techniques")
            or cv_profile.get("mots_cles")
            or []
        )
        if competences:
            sections.append(
                f"Compétences techniques : {', '.join(str(c) for c in competences[:20])}"
            )
        soft = cv_profile.get("soft_skills") or []
        if soft:
            sections.append(f"Compétences transversales : {', '.join(str(s) for s in soft[:12])}")
        outils = cv_profile.get("outils") or []
        if outils:
            sections.append(f"Outils : {', '.join(str(o) for o in outils[:15])}")
        langages = cv_profile.get("langages") or []
        if langages:
            sections.append(f"Langages : {', '.join(str(l) for l in langages[:10])}")
        certs = cv_profile.get("diplomes_certifications") or []
        if certs:
            sections.append(f"Certifications / diplômes : {', '.join(str(c) for c in certs[:10])}")
        secteurs = cv_profile.get("secteurs") or []
        if secteurs:
            sections.append(f"Secteurs : {', '.join(str(s) for s in secteurs[:6])}")
        experiences = cv_profile.get("experiences") or []
        exp_lines: list[str] = []
        for exp in experiences[:6]:
            if isinstance(exp, dict):
                poste = exp.get("poste") or exp.get("title") or exp.get("role") or ""
                entreprise = exp.get("entreprise") or exp.get("company") or ""
                duree = exp.get("duree") or exp.get("period") or ""
                missions = exp.get("missions") or exp.get("description") or ""
                secteur = exp.get("secteur") or exp.get("sector") or ""
                header = " — ".join(p for p in (poste, entreprise, duree) if p)
                if header:
                    detail = f"- {header}"
                    if secteur:
                        detail += f" [{secteur}]"
                    if missions:
                        detail += f" : {str(missions)[:200]}"
                    exp_lines.append(detail)
            elif isinstance(exp, str) and exp.strip():
                exp_lines.append(f"- {exp.strip()}")
        if exp_lines:
            sections.append("Expériences professionnelles :\n" + "\n".join(exp_lines))

    sections.append(f"Texte intégral du CV :\n{cv_text[:CV_MATCH_TEXT_LIMIT_WITH_PROFILE if cv_profile else 9000]}")
    return "\n\n".join(sections)


def _job_summary_for_match(job: dict[str, Any], desc_limit: int = 5000) -> str:
    return (
        f"Titre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '') or job.get('inferred_contract', '')}\n"
        f"Description :\n{job.get('description', '')[:desc_limit]}"
    )


def match_cv_to_jobs_batch(
    cv_text: str,
    jobs: list[dict[str, Any]],
    *,
    cv_profile: dict[str, Any] | None = None,
    target_job_title: str = "",
) -> list[dict[str, Any]]:
    """Compare CV against several job offers in one LLM call (saves Groq quota)."""
    if not jobs:
        return []
    if len(jobs) == 1:
        return [
            match_cv_to_job(
                cv_text,
                jobs[0],
                cv_profile=cv_profile,
                target_job_title=target_job_title,
            )
        ]

    offers_block = "\n\n".join(
        f"--- OFFRE {idx} ---\n{_job_summary_for_match(job)}"
        for idx, job in enumerate(jobs, start=1)
    )
    candidate_block = build_cv_match_context(cv_text, cv_profile, target_job_title)
    user_prompt = f"{candidate_block}\n\nOffres à évaluer (dans l'ordre) :\n{offers_block}"

    for attempt in range(2):
        try:
            prompt = BATCH_MATCH_SYSTEM_PROMPT
            if attempt == 1:
                prompt += (
                    "\n\nRAPPEL : retourne UNIQUEMENT le tableau JSON, "
                    f"avec exactement {len(jobs)} objet(s), dans l'ordre des offres."
                )
            raw = call_llm(prompt, user_prompt)
            parsed = _parse_json_response(raw)
            if not isinstance(parsed, list):
                raise ValueError("Réponse batch invalide (attendu: tableau JSON).")

            results: list[dict[str, Any]] = []
            for idx, job in enumerate(jobs):
                item = parsed[idx] if idx < len(parsed) else {}
                if isinstance(item, dict) and item.get("score_correspondance") is not None:
                    results.append(_normalize_match_result(item, job))
                else:
                    results.append(
                        match_cv_to_job(
                            cv_text,
                            job,
                            cv_profile=cv_profile,
                            target_job_title=target_job_title,
                        )
                    )
            return results
        except GroqRateLimitError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError):
            if attempt == 0:
                continue
            break
        except RuntimeError as exc:
            if "quota" in str(exc).lower() or "rate limit" in str(exc).lower():
                raise
            break

    return [
        match_cv_to_job(
            cv_text,
            job,
            cv_profile=cv_profile,
            target_job_title=target_job_title,
        )
        for job in jobs
    ]


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
    country: str,
    profile_json: str,
    metier: str = "",
    contract_type: str = "",
    alternate_queries: tuple[str, ...] = (),
    refresh_key: str = "",
) -> dict[str, Any]:
    # refresh_key is unused in the body: Streamlit includes it in the cache key
    # so each analysis launch can refetch instead of reusing the 24 h snapshot.
    _ = refresh_key
    profile = json.loads(profile_json)
    boosted_query = enrich_query_for_contract(query, contract_type)
    boosted_metier = enrich_query_for_contract(metier, contract_type)
    return search_jobs_for_profile(
        provider,
        boosted_query,
        country,
        profile,
        boosted_metier,
        contract_type,
        list(alternate_queries),
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_match_cv_to_job(
    cv_text: str,
    job_json: str,
    profile_json: str = "",
    target_job_title: str = "",
) -> dict[str, Any]:
    cv_profile = json.loads(profile_json) if profile_json else None
    return match_cv_to_job(
        cv_text,
        json.loads(job_json),
        cv_profile=cv_profile,
        target_job_title=target_job_title,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_match_cv_to_jobs_batch(
    cv_text: str,
    jobs_json: str,
    profile_json: str = "",
    target_job_title: str = "",
) -> list[dict[str, Any]]:
    cv_profile = json.loads(profile_json) if profile_json else None
    return match_cv_to_jobs_batch(
        cv_text,
        json.loads(jobs_json),
        cv_profile=cv_profile,
        target_job_title=target_job_title,
    )


# ---------------------------------------------------------------------------
# Job search — Adzuna, Welcome to the Jungle & SerpApi
# ---------------------------------------------------------------------------


def render_adzuna_auth_help(app_id: str = "") -> None:
    """Help when Adzuna returns 401 AUTH_FAIL."""
    masked_id = f"`{app_id[:4]}…{app_id[-2:]}`" if len(app_id) >= 6 else "(non configuré)"
    st.error("Adzuna refuse vos identifiants (`AUTH_FAIL` = clé invalide ou compte expiré).")
    st.markdown(
        f"""
**Diagnostic :** l'API Adzuna n'accepte que `app_id` + `app_key` en paramètres d'URL.
Votre `app_id` actuel : {masked_id}

**Procédure recommandée :**

1. Ouvrez [developer.adzuna.com/dashboard](https://developer.adzuna.com/dashboard)
2. Si une clé est marquée **supprimée** ou **essai expiré**, créez une **nouvelle application**
   (pas seulement une nouvelle clé sur une app morte)
3. Copiez **les deux valeurs de la même ligne** :
   - Application ID → `ADZUNA_APP_ID`
   - Clé d'application → `ADZUNA_APP_KEY`
4. Collez dans `.streamlit/secrets.toml`, redémarrez Streamlit, puis **Tester connexion Adzuna**

**Test manuel sur le site Adzuna :** onglet *Interactive API* du dashboard — si ça échoue là aussi,
le problème vient du compte Adzuna (contactez support@adzuna.com).

**Alternative immédiate :** [serpapi.com](https://serpapi.com/) → clé gratuite (100 req/mois) →
ajoutez `SERPAPI_API_KEY` dans secrets et choisissez **SerpApi / Google Jobs** dans la sidebar.
        """
    )


def test_adzuna_connection() -> tuple[bool, str]:
    """Verify Adzuna credentials with a minimal search request."""
    app_id = get_secret("ADZUNA_APP_ID")
    app_key = get_secret("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return False, "ADZUNA_APP_ID ou ADZUNA_APP_KEY manquant."

    url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": "developer",
        "results_per_page": 1,
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if response.ok:
            count = response.json().get("count", 0)
            return True, f"OK — {count} offre(s) trouvée(s) en France (app_id `{app_id[:4]}…`)."

        detail = response.text.strip()
        if response.status_code == 401 and "AUTH_FAIL" in detail:
            return (
                False,
                f"AUTH_FAIL — app_id `{app_id[:4]}…`, clé ({len(app_key)} car.) refusée par Adzuna.",
            )
        return False, f"HTTP {response.status_code} — {detail[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def resolve_country_code(country: str) -> str:
    """Map French country name (any casing) to Adzuna ISO code."""
    normalized = country.strip().lower()
    if not normalized:
        return "fr"
    for name, code in ADZUNA_COUNTRY_CODES.items():
        if name.lower() == normalized:
            return code
    aliases = {
        "france": "fr",
        "belgique": "be",
        "suisse": "ch",
        "royaume-uni": "gb",
        "allemagne": "de",
        "espagne": "es",
        "italie": "it",
        "pays-bas": "nl",
        "etats-unis": "us",
        "australie": "au",
    }
    return aliases.get(normalized, "fr")


def search_jobs_with_fallback(
    provider: str,
    query: str,
    location: str,
    country: str,
    metier: str = "",
    contract_type: str = "",
    alternate_queries: list[str] | None = None,
    max_age_days: int = 0,
) -> dict[str, Any]:
    """Search jobs by métier — location-first when a zone is provided."""
    if provider == JOB_PROVIDER_ALL:
        return _search_all_providers_with_fallback(
            query, location, country, metier, contract_type, alternate_queries
        )

    attempts: list[tuple[str, str, str]] = []
    q = query.strip()
    loc = location.strip()
    m = metier.strip()

    if loc:
        if q:
            attempts.append((q, loc, f"Poste visé · {loc}"))
        if m and m.lower() != q.lower():
            attempts.append((m, loc, f"Métier · {loc}"))
        for alt in alternate_queries or []:
            alt_text = alt.strip()
            if not alt_text:
                continue
            if alt_text.lower() in {q.lower(), m.lower()}:
                continue
            attempts.append((alt_text, loc, f"Poste similaire · {loc}"))
        short = " ".join((q or m).split()[:2])
        if short and short.lower() != (q or m).lower():
            attempts.append((short, loc, f"Requête élargie · {loc}"))

    if q:
        attempts.append((q, "", "Recherche nationale (secours)"))
    if m and m.lower() != q.lower():
        attempts.append((m, "", "Métier seul (secours)"))
    short = " ".join((q or m).split()[:2])
    if short and short.lower() != (q or m).lower():
        attempts.append((short, "", "Requête élargie (secours)"))

    seen: set[tuple[str, str]] = set()
    for q_try, loc_try, label in attempts:
        key = (q_try.lower(), loc_try.lower())
        if not q_try or key in seen:
            continue
        seen.add(key)
        jobs = search_jobs(
            provider, q_try, loc_try, country, contract_type, max_age_days=max_age_days
        )
        if jobs:
            return {
                "jobs": jobs,
                "strategy": label,
                "query_used": q_try,
                "location_used": loc_try or f"(tout {country or 'France'})",
                "providers_used": [provider],
            }

    return {
        "jobs": [],
        "strategy": "aucune",
        "query_used": q or m or "(vide)",
        "location_used": loc or f"(tout {country or 'France'})",
        "attempts": len(seen),
        "providers_used": [provider],
    }


def _search_jobs_at_profile_location(
    provider: str,
    query: str,
    loc: str,
    country: str,
    metier: str,
    contract_type: str,
    alternate_queries: list[str] | None,
    max_age_days: int,
) -> dict[str, Any]:
    """Run one provider search for a single profile zone."""
    if provider == JOB_PROVIDER_ALL:
        return _search_all_providers_with_fallback(
            query,
            loc,
            country,
            metier,
            contract_type,
            alternate_queries,
            max_age_days=max_age_days,
        )
    return search_jobs_with_fallback(
        provider,
        query,
        loc,
        country,
        metier,
        contract_type,
        alternate_queries,
        max_age_days=max_age_days,
    )


def _search_jobs_at_country_locations(
    provider: str,
    query: str,
    country: str,
    profile_locations: list[str],
    metier: str,
    contract_type: str,
    alternate_queries: list[str] | None,
    max_age_days: int,
) -> dict[str, Any]:
    """Run provider search for one country across its profile location hints."""
    merged: list[dict[str, Any]] = []
    providers_used: list[str] = []
    strategies: list[str] = []
    query_used = query
    location_iter = profile_locations or [""]
    if provider == JOB_PROVIDER_CAREER_SITES:
        # One Google search covers many companies; do not multiply SerpApi calls per city.
        location_iter = [location_iter[0]]

    worker_count = min(SEARCH_LOCATION_MAX_WORKERS, len(location_iter))
    if worker_count > 1:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    _search_jobs_at_profile_location,
                    provider,
                    query,
                    loc,
                    country,
                    metier,
                    contract_type,
                    alternate_queries,
                    max_age_days,
                )
                for loc in location_iter
            ]
            for future in as_completed(futures):
                result = future.result()
                if result.get("jobs"):
                    merged = merge_job_lists([merged, result["jobs"]])
                    query_used = result.get("query_used") or query_used
                    providers_used.extend(result.get("providers_used") or [])
                    if result.get("strategy"):
                        strategies.append(str(result["strategy"]))
    else:
        for loc in location_iter:
            result = _search_jobs_at_profile_location(
                provider,
                query,
                loc,
                country,
                metier,
                contract_type,
                alternate_queries,
                max_age_days,
            )
            if result.get("jobs"):
                merged = merge_job_lists([merged, result["jobs"]])
                query_used = result.get("query_used") or query_used
                providers_used.extend(result.get("providers_used") or [])
                if result.get("strategy"):
                    strategies.append(str(result["strategy"]))

    return {
        "jobs": merged,
        "strategy": strategies[0] if len(strategies) == 1 else "",
        "query_used": query_used,
        "providers_used": providers_used,
    }


def _with_company_career_sites(
    result: dict[str, Any],
    *,
    query: str,
    metier: str,
    locations: list[str],
    countries: list[str],
    country: str,
    provider: str,
) -> dict[str, Any]:
    """Always mix company career-site openings into an analysis search."""
    secrets = provider_secrets_from_getter(get_secret)
    loc = ", ".join(item for item in (locations or [])[:2] if item)
    return merge_career_site_results(
        result,
        query=query,
        metier=metier,
        location=loc,
        country=(countries[0] if countries else country) or "France",
        provider=provider,
        api_key=secrets.get("serpapi_api_key") or "",
    )


def search_jobs_for_profile(
    provider: str,
    query: str,
    country: str,
    profile: dict[str, Any],
    metier: str = "",
    contract_type: str = "",
    alternate_queries: list[str] | None = None,
) -> dict[str, Any]:
    """Search across all selected countries and profile zones, then merge results."""
    max_age_days = normalize_job_max_age_days(profile.get("job_max_age_days"))
    countries = profile_countries(profile) or [country or "France"]
    geo_map = merge_profile_geo(profile)
    per_country_max = max(3, 24 // max(1, len(countries)))

    merged: list[dict[str, Any]] = []
    providers_used: list[str] = []
    strategies: list[str] = []
    query_used = query
    all_locations: list[str] = []

    for search_country in countries:
        country_locations = build_country_search_locations(
            search_country,
            geo_map.get(search_country, {}),
            max_locations=per_country_max,
        )
        all_locations.extend(country_locations)
        result = _search_jobs_at_country_locations(
            provider,
            query,
            search_country,
            country_locations,
            metier,
            contract_type,
            alternate_queries,
            max_age_days,
        )
        if result.get("jobs"):
            merged = merge_job_lists([merged, result["jobs"]])
            query_used = result.get("query_used") or query_used
            providers_used.extend(result.get("providers_used") or [])
            if result.get("strategy"):
                strategies.append(str(result["strategy"]))

    if merged:
        location_label = ", ".join(all_locations[:4])
        if len(all_locations) > 4:
            location_label += "…"
        countries_label = format_countries_summary(profile)
        strategy = strategies[0] if len(strategies) == 1 else "Zones sélectionnées (profil)"
        if len(countries) > 1:
            strategy = f"{countries_label} — {strategy}"
        return _with_company_career_sites(
            {
                "jobs": merged,
                "strategy": strategy,
                "query_used": query_used,
                "location_used": location_label,
                "providers_used": list(dict.fromkeys(providers_used)),
                "profile_locations": all_locations,
            },
            query=query,
            metier=metier,
            locations=all_locations,
            countries=countries,
            country=country,
            provider=provider,
        )

    fallback_country = profile_primary_country(profile) or country or "France"
    fallback = search_jobs_with_fallback(
        provider,
        query,
        "",
        fallback_country,
        metier,
        contract_type,
        alternate_queries,
        max_age_days=max_age_days,
    )
    fallback["profile_locations"] = all_locations
    return _with_company_career_sites(
        fallback,
        query=query,
        metier=metier,
        locations=all_locations,
        countries=countries,
        country=country,
        provider=provider,
    )


def _search_all_providers_with_fallback(
    query: str,
    location: str,
    country: str,
    metier: str = "",
    contract_type: str = "",
    alternate_queries: list[str] | None = None,
    max_age_days: int = 0,
) -> dict[str, Any]:
    """Query every configured provider and merge unique results."""
    secrets = provider_secrets_from_getter(get_secret)
    providers = configured_providers(secrets=secrets)
    if not providers:
        return {
            "jobs": [],
            "strategy": "aucune",
            "query_used": query or metier or "(vide)",
            "location_used": f"(tout {country or 'France'})",
            "providers_used": [],
        }

    q = query.strip() or metier.strip()
    queries: list[str] = []
    for candidate in [q, metier.strip(), *(alternate_queries or [])]:
        text = candidate.strip()
        if text and text.lower() not in {x.lower() for x in queries}:
            queries.append(text)
    if not queries:
        queries = [""]

    for q_try in queries:
        merged: list[dict[str, Any]] = []
        used: list[str] = []
        loc = location.strip()
        for provider in providers:
            try:
                batch = search_jobs(
                    provider,
                    q_try,
                    loc,
                    country,
                    contract_type,
                    max_age_days=max_age_days,
                )
            except (RuntimeError, requests.HTTPError):
                continue
            if batch:
                used.append(provider)
                merged = merge_job_lists([merged, batch])
        if merged:
            return {
                "jobs": merged,
                "strategy": "Fusion multi-moteurs",
                "query_used": q_try,
                "location_used": loc or f"(tout {country or 'France'})",
                "providers_used": used,
            }

    return {
        "jobs": [],
        "strategy": "aucune",
        "query_used": q or metier or "(vide)",
        "location_used": f"(tout {country or 'France'})",
        "providers_used": providers,
    }


def search_jobs_adzuna(
    query: str,
    location: str,
    country_code: str,
    results_per_page: int = 50,
    max_pages: int = 3,
    max_days_old: int = 0,
) -> list[dict[str, Any]]:
    """Search jobs via Adzuna REST API (multi-page when searching country-wide)."""
    app_id = get_secret("ADZUNA_APP_ID")
    app_key = get_secret("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError(
            "Clés Adzuna manquantes. Configurez ADZUNA_APP_ID et ADZUNA_APP_KEY."
        )

    pages = max_pages if not location.strip() else 1
    jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page in range(1, pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/{page}"
        params: dict[str, Any] = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "what": query,
        }
        if location.strip():
            params["where"] = location.strip()
        if max_days_old and max_days_old > 0:
            params["max_days_old"] = max_days_old

        response = requests.get(
            url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=30,
        )

        if not response.ok:
            detail = response.text.strip() or "(réponse vide — redémarrez Streamlit après changement de secrets)"
            raise requests.HTTPError(
                f"Adzuna {response.status_code}: {detail}",
                response=response,
            )

        data = response.json()
        results = data.get("results", [])
        if not results:
            break

        for item in results:
            job_url = item.get("redirect_url", "")
            if job_url and job_url in seen_urls:
                continue
            if job_url:
                seen_urls.add(job_url)
            jobs.append(
                {
                    "title": item.get("title", "N/A"),
                    "company": item.get("company", {}).get("display_name", "N/A"),
                    "location": item.get("location", {}).get("display_name", "N/A"),
                    "description": item.get("description", ""),
                    "url": job_url,
                    "contract_type": item.get("contract_type", ""),
                    "source": "Adzuna",
                    "published_at": item.get("created", ""),
                }
            )

        if len(results) < results_per_page:
            break

    return jobs


def search_jobs_serpapi(query: str, location: str, country: str = "France") -> list[dict[str, Any]]:
    """Search jobs via SerpApi Google Jobs engine."""
    api_key = get_secret("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Clé SerpApi manquante. Configurez SERPAPI_API_KEY."
        )
    serp_location = f"{location}, {country}" if location else country
    return search_jobs_serpapi_google_jobs(query, serp_location, country, api_key)


def search_jobs(
    provider: str,
    query: str,
    location: str,
    country: str,
    contract_type: str = "",
    max_age_days: int = 0,
) -> list[dict[str, Any]]:
    """Dispatch job search to the selected provider."""
    secrets = provider_secrets_from_getter(get_secret)

    if provider == JOB_PROVIDER_WTTJ:
        return search_jobs_wttj(query, contract_type=contract_type)

    if provider == JOB_PROVIDER_JOOBLE:
        if not secrets["jooble_api_key"]:
            raise RuntimeError(
                "Clé Jooble manquante. Configurez JOOBLE_API_KEY (fr.jooble.org/api/about)."
            )
        return search_jobs_jooble(
            query, location, country, secrets["jooble_api_key"]
        )

    if provider == JOB_PROVIDER_OPTIONCARRIERE:
        if not secrets["careerjet_api_key"]:
            raise RuntimeError(
                "Clé Careerjet manquante. Configurez CAREERJET_API_KEY "
                "(optioncarriere.com/partners/api)."
            )
        return search_jobs_optioncarriere(
            query,
            location,
            country,
            secrets["careerjet_api_key"],
            user_ip=resolve_careerjet_user_ip(
                secrets["careerjet_user_ip"],
                client_ip=resolve_streamlit_client_ip(),
            ),
            referer=resolve_careerjet_referer(secrets["careerjet_referer"]),
            contract_type=contract_type,
        )

    if provider == JOB_PROVIDER_JOBTEASER:
        if not secrets["apify_api_token"]:
            raise RuntimeError(
                "Token Apify manquant. Configurez APIFY_API_TOKEN pour JobTeaser."
            )
        return search_jobs_jobteaser(
            query, location, contract_type, secrets["apify_api_token"]
        )

    serp_key = secrets["serpapi_api_key"]
    apify_token = secrets["apify_api_token"]

    if provider == JOB_PROVIDER_HELLOWORK:
        if not apify_token and not serp_key:
            raise RuntimeError(
                "HelloWork requiert APIFY_API_TOKEN et/ou SERPAPI_API_KEY."
            )
        return search_jobs_hellowork(
            query,
            location,
            contract_type,
            apify_token,
            serpapi_key=serp_key,
        )

    if provider == JOB_PROVIDER_MONSTER:
        if not apify_token and not serp_key:
            raise RuntimeError(
                "Monster requiert APIFY_API_TOKEN et/ou SERPAPI_API_KEY."
            )
        return search_jobs_monster(
            query,
            location,
            country,
            apify_token,
            serpapi_key=serp_key,
            contract_type=contract_type,
        )

    if provider == JOB_PROVIDER_TALENT:
        if not apify_token and not serp_key:
            raise RuntimeError(
                "Talent.com requiert APIFY_API_TOKEN et/ou SERPAPI_API_KEY."
            )
        return search_jobs_talent(
            query,
            location,
            country,
            apify_token,
            serpapi_key=serp_key,
        )

    if provider == JOB_PROVIDER_INDEED:
        if not serp_key:
            raise RuntimeError("SERPAPI_API_KEY requise pour Indeed.")
        return search_jobs_indeed_serpapi(query, location, country, serp_key)

    if provider == JOB_PROVIDER_LINKEDIN:
        if not serp_key:
            raise RuntimeError("SERPAPI_API_KEY requise pour LinkedIn Jobs.")
        return search_jobs_linkedin_serpapi(query, location, country, serp_key)

    if provider == JOB_PROVIDER_GLASSDOOR:
        if not serp_key:
            raise RuntimeError("SERPAPI_API_KEY requise pour Glassdoor.")
        return search_jobs_glassdoor_serpapi(query, location, country, serp_key)

    if provider == JOB_PROVIDER_CAREER_SITES:
        if not serp_key:
            raise RuntimeError(
                "SERPAPI_API_KEY requise pour chercher sur les sites carrière des entreprises."
            )
        return search_jobs_career_sites(query, location, country, serp_key)

    if provider == JOB_PROVIDER_SERPAPI:
        if not serp_key:
            raise RuntimeError("Clé SerpApi manquante. Configurez SERPAPI_API_KEY.")
        serp_location = f"{location}, {country}" if location else country
        return search_jobs_serpapi_google_jobs(
            query, serp_location, country, serp_key
        )

    country_code = resolve_country_code(country)
    return search_jobs_adzuna(query, location, country_code, max_days_old=max_age_days)


def rank_jobs_for_cv(
    jobs: list[dict[str, Any]],
    cv_text: str,
    keywords: list[str],
    top_n: int = TOP_MATCHING_JOBS,
    *,
    target_job_title: str = "",
    cv_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Pre-rank jobs by keyword and title overlap before deep AI matching."""
    cv_lower = cv_text.lower()
    keyword_set = {kw.lower() for kw in keywords if kw and len(kw) > 1}
    if cv_profile:
        for kw in (cv_profile.get("competences_techniques") or [])[:15]:
            if kw:
                keyword_set.add(str(kw).lower())
        for kw in (cv_profile.get("mots_cles") or [])[:10]:
            if kw:
                keyword_set.add(str(kw).lower())

    stopwords = {
        "de", "du", "des", "le", "la", "les", "en", "et", "ou", "un", "une",
        "pour", "par", "sur", "avec", "the", "and", "or",
    }
    target_tokens = {
        t for t in re.findall(r"\w+", target_job_title.lower()) if t not in stopwords and len(t) > 2
    }
    metier = str((cv_profile or {}).get("metier", "")).strip()
    metier_tokens = {
        t for t in re.findall(r"\w+", metier.lower()) if t not in stopwords and len(t) > 2
    }

    def quick_score(job: dict[str, Any]) -> int:
        title = str(job.get("title", "")).lower()
        blob = f"{title} {job.get('description', '')}".lower()
        hits = sum(1 for kw in keyword_set if kw in blob)
        cv_hits = sum(1 for kw in keyword_set if kw in blob and kw in cv_lower)
        title_overlap = sum(1 for token in target_tokens if token in title)
        metier_overlap = sum(1 for token in metier_tokens if token in title)
        return hits * 8 + cv_hits * 5 + title_overlap * 18 + metier_overlap * 12

    return sorted(jobs, key=quick_score, reverse=True)[:top_n]


ProgressReporter = Callable[[int, str], None]


def _report_progress(progress: ProgressReporter | None, percent: int, label: str) -> None:
    if progress:
        progress(max(0, min(100, percent)), label)


def build_matching_results(
    jobs: list[dict[str, Any]],
    cv_text: str,
    keywords: list[str],
    top_n: int = TOP_MATCHING_JOBS,
    *,
    pool_size: int | None = None,
    cv_profile: dict[str, Any] | None = None,
    target_job_title: str = "",
    user_profile: dict[str, Any] | None = None,
    progress: ProgressReporter | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """AI-match candidates from a wide online search and keep only the requested best offers."""
    try:
        from services.llm_usage import bind_current_user_from_streamlit, bind_usage_user_id

        profile_id = (user_profile or {}).get("id")
        if profile_id is not None:
            bind_usage_user_id(int(profile_id))
        bind_current_user_from_streamlit()
    except Exception:  # noqa: BLE001
        pass
    candidate_limit = min(len(jobs), pool_size or MATCHING_CANDIDATE_POOL)
    candidates = rank_jobs_for_cv(
        jobs,
        cv_text,
        keywords,
        top_n=candidate_limit,
        target_job_title=target_job_title,
        cv_profile=cv_profile,
    )

    key_slots = collect_parallel_llm_slots(PARALLEL_MATCH_KEYS_PER_PROVIDER)
    worker_count = min(PARALLEL_MATCH_MAX_WORKERS, max(1, len(key_slots)))
    use_parallel = worker_count > 1 and len(candidates) > 1

    _report_progress(
        progress,
        60,
        f"Matching ATS — analyse de {len(candidates)} offre(s)…",
    )

    results: list[dict[str, Any]] = []
    partial_matches = 0
    match_start = 60
    match_end = 95
    total_candidates = len(candidates)

    def _report_match_progress(done: int) -> None:
        if total_candidates <= 0:
            return
        span = match_end - match_start
        pct = match_start + int(span * done / total_candidates)
        _report_progress(
            progress,
            pct,
            f"Matching IA — {done}/{total_candidates} offre(s) analysée(s)",
        )

    def _match_one(index: int, job: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
        provider, api_key = key_slots[index % len(key_slots)]
        try:
            match = match_cv_to_job(
                cv_text,
                job,
                cv_profile=cv_profile,
                target_job_title=target_job_title,
                user_profile=user_profile,
                llm_provider=provider,
                llm_api_key=api_key,
            )
        except Exception:  # noqa: BLE001 — fallback per offer
            match = fallback_match_result(job)
        return index, job, match

    if use_parallel:
        ordered: list[tuple[int, dict[str, Any], dict[str, Any]] | None] = [None] * len(candidates)
        completed = 0
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_match_one, index, job)
                for index, job in enumerate(candidates)
            ]
            for future in as_completed(futures):
                index, job, match = future.result()
                ordered[index] = (index, job, match)
                completed += 1
                _report_match_progress(completed)
        for item in ordered:
            if item is None:
                continue
            _, job, match = item
            if match.get("_fallback"):
                partial_matches += 1
            results.append({"job": job, "match": match})
    else:
        profile_json = json.dumps(cv_profile or {}, sort_keys=True, ensure_ascii=False)
        provider, api_key = key_slots[0] if key_slots else (None, None)
        for index, job in enumerate(candidates):
            if index > 0:
                time.sleep(GROQ_INTER_CALL_DELAY_SEC)
            if provider and api_key:
                match = match_cv_to_job(
                    cv_text,
                    job,
                    cv_profile=cv_profile,
                    target_job_title=target_job_title,
                    user_profile=user_profile,
                    llm_provider=provider,
                    llm_api_key=api_key,
                )
            else:
                job_json = json.dumps(job, sort_keys=True, ensure_ascii=False)
                match = cached_match_cv_to_job(
                    cv_text,
                    job_json,
                    profile_json,
                    target_job_title,
                )
            if match.get("_fallback"):
                partial_matches += 1
            results.append({"job": job, "match": match})
            _report_match_progress(index + 1)

    _report_progress(progress, match_end, "Classement des meilleures offres…")
    results.sort(
        key=lambda entry: int(entry["match"].get("score_correspondance", 0)),
        reverse=True,
    )
    # Search may find hundreds of offers; display only the N best requested by depth.
    return results[: max(0, int(top_n))], partial_matches


def matching_display_limit(analysis: dict[str, Any] | None) -> int:
    """How many ranked offers the selected depth asked to show."""
    if not analysis:
        return int(TOP_MATCHING_JOBS)
    depth = str(analysis.get("analysis_depth") or "")
    if depth in ANALYSIS_DEPTH_TOP:
        return int(ANALYSIS_DEPTH_TOP[depth])
    try:
        top = int(analysis.get("matching_top") or 0)
    except (TypeError, ValueError):
        top = 0
    if top > 0:
        return top
    return int(TOP_MATCHING_JOBS)


def cap_results_to_requested_best(
    results: list[dict[str, Any]],
    analysis: dict[str, Any] | None = None,
    *,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Keep the N best ATS matches, even if many more were found online."""
    ranked = sorted(
        list(results or []),
        key=lambda item: int((item.get("match") or {}).get("score_correspondance", 0)),
        reverse=True,
    )
    limit = int(top_n) if top_n is not None else matching_display_limit(analysis)
    return ranked[: max(0, limit)]


# ---------------------------------------------------------------------------
# PDF report export
# ---------------------------------------------------------------------------

_PDF_CHAR_REPLACEMENTS = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u2212": "-",  # minus sign
    "\u00b7": "-",  # middle dot
    "\u2022": "-",  # bullet
    "\u2026": "...",  # ellipsis
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
    "\u202f": " ",
    "\u200b": "",
    "\u00ad": "",
    "\u2192": "->",
    "\u2190": "<-",
}


def pdf_safe_text(value: Any, default: str = "-") -> str:
    """Make text safe for fpdf2 core fonts (Helvetica/Times, Latin-1)."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return default
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def sanitize_pdf_html(html_content: str) -> str:
    """Ensure HTML passed to fpdf2 only contains Latin-1 characters."""
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        html_content = html_content.replace(src, dst)
    return html_content.encode("latin-1", errors="replace").decode("latin-1")


def pdf_escape(value: Any, default: str = "-") -> str:
    return html.escape(pdf_safe_text(value, default))


def generate_matching_report_pdf(
    criteria: dict[str, Any],
    results: list[dict[str, Any]],
    extraction_method: str,
) -> bytes:
    """Build a downloadable PDF report from analysis results."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=11)
    pdf.add_page()

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    title = pdf_safe_text(f"Rapport de Matching CV - {APP_NAME}")

    body_html = f"""
    <h1>{pdf_escape(title)}</h1>
    <p><em>Genere le {pdf_escape(generated_at)} - Extraction CV : {pdf_escape(extraction_method)}</em></p>
    <hr>
    <h2>Criteres detectes</h2>
    <ul>
        <li><b>Metier vise :</b> {pdf_escape(criteria.get('metier'))}</li>
        <li><b>Ville :</b> {pdf_escape(criteria.get('ville'))}</li>
        <li><b>Pays :</b> {pdf_escape(criteria.get('pays'))}</li>
        <li><b>Type de contrat :</b> {pdf_escape(criteria.get('type_contrat'))}</li>
        <li><b>Mots-cles :</b> {pdf_escape(', '.join(criteria.get('mots_cles', [])))}</li>
    </ul>
    """

    for idx, entry in enumerate(results, start=1):
        job = entry["job"]
        match = entry["match"]
        score = int(match.get("score_correspondance", 0))
        skills = match.get("analyse_competences") or {}
        exp_analysis = match.get("analyse_experiences") or {}
        missing = ", ".join(match.get("mots_cles_manquants", []))
        presentes = ", ".join(skills.get("presentes", []))
        manquantes = ", ".join(skills.get("manquantes", []))

        body_html += f"""
        <hr>
        <h2>#{idx} - {pdf_escape(job.get('title', 'N/A'))} - Score ATS {score}%</h2>
        <p><b>Synthese :</b> {pdf_escape(match.get('synthese_ats', '-'))}</p>
        <ul>
            <li><b>Entreprise :</b> {pdf_escape(job.get('company', 'N/A'))}</li>
            <li><b>Lieu :</b> {pdf_escape(job.get('location', 'N/A'))}</li>
            <li><b>Contrat :</b> {pdf_escape(job.get('contract_type') or '-')}</li>
            <li><b>Scores :</b> Competences {match.get('score_competences', score)}% |
                Experiences {match.get('score_experiences', score)}% |
                Titre {match.get('score_titre', score)}% |
                Lieu {match.get('score_localisation', score)}%</li>
            <li><b>Titre CV recommande :</b> {pdf_escape(match.get('titre_cv_recommande', 'N/A'))}</li>
            <li><b>Competences presentes :</b> {pdf_escape(presentes or '-')}</li>
            <li><b>Competences manquantes :</b> {pdf_escape(manquantes or missing or '-')}</li>
            <li><b>Niveau offre / CV :</b> {pdf_escape(exp_analysis.get('niveau_offre', '-'))} / {pdf_escape(exp_analysis.get('niveau_cv', '-'))}</li>
            <li><b>Lien :</b> {pdf_escape(job.get('url', '-'))}</li>
        </ul>
        """

    pdf.write_html(sanitize_pdf_html(body_html))
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
    metier = criteria.get("metier", "")

    search_result = cached_search_jobs(
        job_provider,
        query,
        country,
        json.dumps({"country": country}, ensure_ascii=False, sort_keys=True),
        metier,
    )
    jobs = search_result["jobs"]
    results, _partial = build_matching_results(
        jobs,
        cv_text,
        keywords,
        cv_profile=criteria,
    )
    results = cap_results_to_requested_best(results, top_n=TOP_MATCHING_JOBS)

    return {
        "cv_text": cv_text,
        "extraction_method": extraction_method,
        "criteria": criteria,
        "jobs_found": len(jobs),
        "search_strategy": search_result.get("strategy"),
        "search_query_used": search_result.get("query_used"),
        "results": results,
        "job_provider": job_provider,
    }


# ---------------------------------------------------------------------------
# UI — theme & layout
# ---------------------------------------------------------------------------


def _hydrate_analysis_result(
    user_id: int | None,
    result_id: int | None,
    job: dict[str, Any],
    match: dict[str, Any],
    cover_letter_text: str | None,
    adapted_cv_text: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str | None, str | None]:
    """Load full job/match/documents when a collapsed card is opened or applied to."""
    if not user_id or not result_id:
        return job, match, cover_letter_text, adapted_cv_text
    if "description" in job and "analyse_competences" in match:
        return job, match, cover_letter_text, adapted_cv_text
    full = get_analysis_result(int(user_id), int(result_id))
    if not full:
        return job, match, cover_letter_text, adapted_cv_text
    return (
        full.get("job") or job,
        full.get("match") or match,
        full.get("cover_letter_text")
        if full.get("cover_letter_text") is not None
        else cover_letter_text,
        full.get("adapted_cv_text") if full.get("adapted_cv_text") is not None else adapted_cv_text,
    )


def render_page_hero(title: str, subtitle: str, badge: str = "") -> None:
    """Top hero block for each main page."""
    badge_html = f'<span class="app-badge">{html.escape(badge)}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="app-page-hero">
            {badge_html}
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _user_initials(full_name: str) -> str:
    return "".join(word[0].upper() for word in (full_name or "").split()[:2]) or "?"


def render_sidebar_brand(user: dict[str, Any], photo_url: str | None = None) -> None:
    """Sidebar header with circular profile photo and account name."""
    email = user.get("email") or ""
    name = user.get("full_name") or ""
    initials = _user_initials(name)
    if photo_url:
        avatar = f'<img class="sidebar-avatar-img" src="{photo_url}" alt="" />'
    else:
        avatar = f'<div class="sidebar-avatar-fallback">{html.escape(initials)}</div>'
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-avatar-ring">{avatar}</div>
            <p class="sidebar-brand-name"><span>Dowson</span>Bost</p>
            <p class="sidebar-user">{html.escape(name or email)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# UI — components
# ---------------------------------------------------------------------------


def _score_color(score: int) -> str:
    if score >= 75:
        return "#22c55e"
    if score >= 50:
        return "#eab308"
    return "#ef4444"


def _render_skill_tags(label: str, items: list[str]) -> None:
    if not items:
        return
    st.markdown(f"**{label}**")
    st.write(", ".join(f"`{item}`" for item in items[:15]))


def open_job_listing_tab(url: str, clipboard_text: str = "") -> None:
    """Open the job listing in a new tab and copy candidate fields for the form."""
    script = job_listing_open_script(url, clipboard_text)
    if not script:
        return
    import streamlit.components.v1 as components

    components.html(script, height=0)


def _render_candidate_documents(
    *,
    letter_text: str | None,
    adapted_text: str | None,
    job: dict[str, Any],
    match: dict[str, Any],
    user_profile: dict[str, Any] | None,
    original_cv: str,
    widget_key: str,
    profile_text: str = "",
    show_bundle: bool = True,
) -> None:
    """Preview + download profession-templated CV / letter (no modifications appendix)."""
    letter = (letter_text or "").strip()
    adapted = cv_text_for_candidate(adapted_text or "")
    if not letter and not adapted:
        return

    structured = None
    cv_pdf = b""
    letter_pdf = b""
    if adapted:
        structured = prepare_structured_cv(
            adapted,
            job=job,
            match=match,
            user_profile=user_profile or {},
            original_cv=original_cv,
        )
        cv_pdf = render_cv_pdf(structured)
    if letter:
        letter_pdf = render_cover_letter_pdf(
            letter,
            job=job,
            match=match,
            user_profile=user_profile or {},
            family=structured.family if structured else None,
        )

    if show_bundle and (letter or adapted or profile_text):
        bundle_buf = io.BytesIO()
        with zipfile.ZipFile(bundle_buf, "w", zipfile.ZIP_DEFLATED) as archive:
            if profile_text:
                archive.writestr("profil_candidat.txt", profile_text)
            if letter:
                archive.writestr("lettre_motivation.txt", letter)
                if letter_pdf:
                    archive.writestr(letter_pdf_filename(job), letter_pdf)
            if adapted:
                public = public_cv_text(structured) if structured else adapted
                archive.writestr("cv_adapte.txt", public)
                if cv_pdf:
                    family = structured.family if structured else "generic"
                    archive.writestr(cv_pdf_filename(job, family), cv_pdf)
        st.download_button(
            t("job.apply_bundle_download"),
            bundle_buf.getvalue(),
            file_name="dossier_candidature.zip",
            mime="application/zip",
            key=f"dl_bundle_{widget_key}",
            use_container_width=True,
        )

    if letter:
        with st.expander(t("job.cover_expander"), expanded=False):
            st.text_area(t("job.letter_field"), letter, height=220, key=f"view_cover_{widget_key}")
            dl_l1, dl_l2 = st.columns(2)
            with dl_l1:
                if letter_pdf:
                    st.download_button(
                        t("job.download_letter_pdf"),
                        letter_pdf,
                        file_name=letter_pdf_filename(job),
                        mime="application/pdf",
                        key=f"dl_cover_pdf_{widget_key}",
                        use_container_width=True,
                    )
            with dl_l2:
                st.download_button(
                    t("job.download_letter"),
                    letter,
                    file_name="lettre_motivation.txt",
                    key=f"dl_cover_{widget_key}",
                    use_container_width=True,
                )

    if adapted and structured:
        with st.expander(t("job.adapted_expander"), expanded=True):
            st.caption(
                t(
                    "job.cv_template_used",
                    name=template_label(structured.family, get_locale()),
                )
            )
            st.markdown(render_cv_html(structured), unsafe_allow_html=True)
            dl_c1, dl_c2 = st.columns(2)
            with dl_c1:
                st.download_button(
                    t("job.download_adapted_pdf"),
                    cv_pdf,
                    file_name=cv_pdf_filename(job, structured.family),
                    mime="application/pdf",
                    key=f"dl_cv_pdf_{widget_key}",
                    use_container_width=True,
                )
            with dl_c2:
                st.download_button(
                    t("job.download_adapted"),
                    public_cv_text(structured) or adapted,
                    file_name="cv_adapte.txt",
                    key=f"dl_cv_{widget_key}",
                    use_container_width=True,
                )


def render_simple_job_row(
    job: dict[str, Any],
    match: dict[str, Any],
    rank: int,
) -> None:
    """Compact analysis-page row: title, company, location and ATS score."""
    score = int(match.get("score_correspondance", 0))
    score_color = _score_color(score)
    fact_parts = [
        str(job.get("company") or "—"),
        str(job.get("location") or "—"),
    ]
    if job.get("source"):
        fact_parts.append(str(job.get("source")))
    facts_html = "".join(
        f"<span>{html.escape(part)}</span>" for part in fact_parts
    )
    st.markdown(
        (
            '<div class="job-match-card job-match-card-simple">'
            '<div class="job-card-head">'
            "<div>"
            f'<p class="job-card-kicker">#{rank}</p>'
            f'<p class="job-card-title">{html.escape(str(job.get("title") or "—"))}</p>'
            f'<p class="job-card-facts">{facts_html}</p>'
            "</div>"
            f'<div class="job-score-badge" style="background:{score_color}18;'
            f'border:2px solid {score_color};color:{score_color}">'
            f"<strong>{score}%</strong>"
            f"<small>{html.escape(t('results.simple_score'))}</small>"
            "</div></div></div>"
        ),
        unsafe_allow_html=True,
    )


def render_job_card(
    job: dict[str, Any],
    match: dict[str, Any],
    rank: int,
    *,
    result_id: int | None = None,
    application_status: str = "new",
    notes: str = "",
    cover_letter_text: str | None = None,
    adapted_cv_text: str | None = None,
    user_id: int | None = None,
    cv_text: str = "",
    user_profile: dict[str, Any] | None = None,
    enable_tracking: bool = False,
    connected_accounts: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Render a single job match card with ATS deep analysis."""
    score = int(match.get("score_correspondance", 0))
    score_color = _score_color(score)
    skills = match.get("analyse_competences") or {}
    exp_analysis = match.get("analyse_experiences") or {}

    st.markdown('<div class="job-match-card">', unsafe_allow_html=True)
    kicker = f"#{rank}"
    if enable_tracking and result_id:
        kicker += " · " + t(
            "job.tracking", status=application_status_label(application_status)
        )
    contract_label_value = job.get("inferred_contract") or job.get("contract_type") or ""
    fact_parts = [
        f"{t('job.company_label')} {job.get('company') or '—'}",
        f"{t('job.location_label')} {job.get('location') or '—'}",
    ]
    if contract_label_value:
        fact_parts.append(f"{t('job.contract_label')} {contract_label_value}")
    fact_parts.append(f"{t('job.publication_label')} {format_job_published_label(job)}")
    if job.get("source"):
        fact_parts.append(f"{t('job.source_label')} {job.get('source')}")
    recommended = match.get("titre_cv_recommande")
    if recommended:
        fact_parts.append(f"{t('job.recommended_cv_title')} {recommended}")
    facts_html = "".join(
        f"<span>{html.escape(str(part))}</span>" for part in fact_parts
    )
    chip_items = (
        (t("job.skills"), match.get("score_competences", score)),
        (t("job.experiences"), match.get("score_experiences", score)),
        (t("job.title_match"), match.get("score_titre", score)),
        (t("job.location_contract_metric"), match.get("score_localisation", score)),
    )
    chips_html = "".join(
        f'<span class="score-chip">{html.escape(label)} {int(value or 0)}%</span>'
        for label, value in chip_items
    )
    st.markdown(
        (
            '<div class="job-card-head">'
            "<div>"
            f'<p class="job-card-kicker">{html.escape(kicker)}</p>'
            f'<p class="job-card-title">{html.escape(str(job.get("title") or "—"))}</p>'
            f'<p class="job-card-facts">{facts_html}</p>'
            "</div>"
            f'<div class="job-score-badge" style="background:{score_color}18;'
            f'border:2px solid {score_color};color:{score_color}">'
            f"<strong>{score}%</strong>"
            f"<small>{html.escape(t('job.ats_global_score'))}</small>"
            "</div></div>"
            f'<div class="score-chip-row">{chips_html}</div>'
        ),
        unsafe_allow_html=True,
    )
    if match.get("synthese_ats"):
        st.caption(match["synthese_ats"])
    st.caption(t("job.ats_scale"))

    details_key = f"job_open_{result_id or rank}"
    show_details = bool(st.session_state.get(details_key))
    if show_details:
        job, match, cover_letter_text, adapted_cv_text = _hydrate_analysis_result(
            user_id,
            result_id,
            job,
            match,
            cover_letter_text,
            adapted_cv_text,
        )
        score = int(match.get("score_correspondance", score))
        skills = match.get("analyse_competences") or {}
        exp_analysis = match.get("analyse_experiences") or {}
    if st.button(
        t("job.hide_details") if show_details else t("job.toggle_details"),
        key=f"toggle_{details_key}",
        use_container_width=True,
    ):
        st.session_state[details_key] = not show_details
        st.rerun()

    if show_details:
        with st.expander(t("job.skills_expander"), expanded=False):
            c_left, c_right = st.columns(2)
            with c_left:
                st.markdown(f"**{t('job.candidate_cv')}**")
                _render_skill_tags(t("skills.technical"), skills.get("cv_techniques", []))
                _render_skill_tags(t("skills.soft"), skills.get("cv_transversales", []))
                _render_skill_tags(t("skills.tools"), skills.get("cv_outils", []))
                _render_skill_tags(t("skills.languages_prog"), skills.get("cv_langages", []))
                _render_skill_tags(t("skills.certifications"), skills.get("cv_certifications", []))
            with c_right:
                st.markdown(f"**{t('job.offer_requirements')}**")
                _render_skill_tags(t("skills.required"), skills.get("offre_obligatoires", []))
                _render_skill_tags(t("skills.desired"), skills.get("offre_souhaitees", []))
                _render_skill_tags(t("skills.company_tech"), skills.get("offre_technos", []))
            st.markdown("---")
            st.markdown(f"**{t('job.skills_result')}**")
            m1, m2, m3 = st.columns(3)
            with m1:
                _render_skill_tags(t("skills.present"), skills.get("presentes", []))
            with m2:
                _render_skill_tags(t("skills.partial"), skills.get("partielles", []))
            with m3:
                _render_skill_tags(t("skills.missing"), skills.get("manquantes", []))

        with st.expander(t("job.exp_expander"), expanded=False):
            niveau_offre = exp_analysis.get("niveau_offre") or "—"
            niveau_cv = exp_analysis.get("niveau_cv") or "—"
            align = exp_analysis.get("alignement_niveau") or "—"
            st.markdown(
                f"**{t('job.level_offer')} :** {niveau_offre} · "
                f"**{t('job.level_cv')} :** {niveau_cv} · "
                f"**{t('job.alignment')} :** {align}"
            )
            for exp in exp_analysis.get("experiences_pertinentes", []):
                if not isinstance(exp, dict):
                    continue
                poste = exp.get("poste", "")
                if not poste:
                    continue
                line = f"**{poste}**"
                if exp.get("duree"):
                    line += f" ({exp['duree']})"
                if exp.get("secteur"):
                    line += f" — {exp['secteur']}"
                st.markdown(line)
                if exp.get("missions_liees"):
                    st.caption(exp["missions_liees"])
            ecarts = exp_analysis.get("ecarts") or []
            if ecarts:
                st.markdown(f"**{t('job.gaps')}**")
                for gap in ecarts:
                    st.warning(gap)

        missing = match.get("mots_cles_manquants", [])
        if missing:
            st.markdown(f"**{t('job.missing_keywords')}**")
            st.write(", ".join(f"`{kw}`" for kw in missing))

    can_apply = bool(enable_tracking and result_id and user_id and cv_text and user_profile)
    source_key = provider_key_from_job_source(str(job.get("source") or ""))
    source_name = job_board_display_name(source_key) if source_key else ""
    linked_account = None
    if source_key:
        if connected_accounts is not None:
            linked_account = connected_accounts.get(source_key)
        elif user_id:
            linked_account = get_connected_job_account(int(user_id), source_key)
    st.markdown(f"**{t('job.application_section')}**")
    if source_key:
        source_name = job_board_display_name(source_key)
        if linked_account:
            st.caption(
                t(
                    "job.apply_account_linked",
                    name=source_name,
                    email=linked_account.get("account_email") or "",
                )
            )
        else:
            st.caption(t("job.apply_account_missing", name=source_name))
    apply_col1, apply_col2 = st.columns(2)
    with apply_col1:
        if job.get("url"):
            st.link_button(
                t("job.apply_manual"),
                job["url"],
                use_container_width=True,
                help=t("job.apply_manual_help"),
            )
        else:
            st.button(t("job.apply_manual"), disabled=True, use_container_width=True)
    with apply_col2:
        if can_apply:
            if st.button(
                t("job.apply_auto"),
                key=f"apply_auto_{result_id}",
                use_container_width=True,
                help=t("job.apply_auto_help"),
            ):
                job, match, cover_letter_text, adapted_cv_text = _hydrate_analysis_result(
                    user_id,
                    result_id,
                    job,
                    match,
                    cover_letter_text,
                    adapted_cv_text,
                )
                with st.spinner(t("job.apply_auto_running")):
                    current_letter = st.session_state.get(f"cover_{result_id}") or cover_letter_text
                    current_cv = st.session_state.get(f"adapted_{result_id}") or adapted_cv_text
                    auto_result = submit_application_automatically(
                        cv_text,
                        job,
                        match,
                        user_profile,
                        llm_call=call_llm,
                        cover_letter_text=current_letter,
                        adapted_cv_text=current_cv,
                        locale=get_locale(),
                    )
                if auto_result["success"]:
                    save_generated_documents(
                        user_id,
                        result_id,
                        cover_letter_text=auto_result["cover_letter"],
                        adapted_cv_text=auto_result["adapted_cv"],
                    )
                    st.session_state[f"cover_{result_id}"] = auto_result["cover_letter"]
                    st.session_state[f"adapted_{result_id}"] = auto_result["adapted_cv"]
                    st.session_state[f"apply_pack_{result_id}"] = auto_result
                    if auto_result["method"] == "email":
                        record_application(
                            user_id,
                            result_id,
                            "auto_email",
                            status="applied",
                            notes=auto_result["message"],
                        )
                    else:
                        record_application(
                            user_id,
                            result_id,
                            "auto_prepared",
                            status="saved",
                            notes=auto_result["message"],
                        )
                    offer_url = str(job.get("url") or auto_result.get("job_url") or "").strip()
                    autofill_text = format_application_autofill_text(
                        build_application_profile(user_profile or {}),
                        cover_letter=auto_result.get("cover_letter") or "",
                        adapted_cv=auto_result.get("adapted_cv") or "",
                    )
                    if offer_url:
                        st.session_state[f"open_offer_{result_id}"] = offer_url
                        st.session_state[f"autofill_{result_id}"] = autofill_text
                        open_job_listing_tab(offer_url, autofill_text)
                    st.success(auto_result["message"])
                    if linked_account and source_name:
                        st.info(
                            t(
                                "job.apply_auto_opens_site_linked",
                                name=source_name,
                                email=linked_account.get("account_email") or "",
                            )
                        )
                    elif offer_url:
                        st.info(t("job.apply_auto_opens_site"))
                    if autofill_text:
                        st.info(t("job.apply_auto_clipboard"))
                    st.session_state[details_key] = True
                    show_details = True
                else:
                    st.error(auto_result["message"])
        else:
            st.button(t("job.apply_auto"), disabled=True, use_container_width=True)

    if show_details and can_apply:
        pack_col1, pack_col2 = st.columns(2)
        with pack_col1:
            if job.get("url"):
                if st.button(
                    t("job.apply_manual_confirm"),
                    key=f"apply_manual_confirm_{result_id}",
                    use_container_width=True,
                ):
                    record_application(
                        user_id,
                        result_id,
                        "manual",
                        status="applied",
                        notes=t("job.apply_manual_confirmed"),
                    )
                    notified = notify_candidate_application(
                        user_profile or {},
                        job,
                        method="manual",
                        locale=get_locale(),
                    )
                    if notified:
                        st.success(
                            f"{t('job.apply_manual_confirmed')} "
                            f"{t('job.apply_user_confirmation_sent', email=(user_profile or {}).get('email', ''))}"
                        )
                    else:
                        st.success(t("job.apply_manual_confirmed"))
                    st.rerun()
        with pack_col2:
            if st.button(
                t("job.apply_manual_prepare"),
                key=f"apply_manual_prepare_{result_id}",
                use_container_width=True,
                help=t("job.apply_manual_prepare_help"),
            ):
                with st.spinner(t("job.apply_auto_running")):
                    current_letter = st.session_state.get(f"cover_{result_id}") or cover_letter_text
                    current_cv = st.session_state.get(f"adapted_{result_id}") or adapted_cv_text
                    manual_result = prepare_manual_application(
                        cv_text,
                        job,
                        match,
                        user_profile,
                        llm_call=call_llm,
                        cover_letter_text=current_letter,
                        adapted_cv_text=current_cv,
                        generate_documents=True,
                        locale=get_locale(),
                    )
                if manual_result["success"]:
                    save_generated_documents(
                        user_id,
                        result_id,
                        cover_letter_text=manual_result["cover_letter"],
                        adapted_cv_text=manual_result["adapted_cv"],
                    )
                    st.session_state[f"cover_{result_id}"] = manual_result["cover_letter"]
                    st.session_state[f"adapted_{result_id}"] = manual_result["adapted_cv"]
                    st.session_state[f"apply_pack_{result_id}"] = manual_result
                    st.success(manual_result["message"])
                    st.rerun()
                else:
                    st.error(manual_result["message"])

    if show_details and can_apply:
        gen_col1, gen_col2 = st.columns(2)
        with gen_col1:
            if st.button(t("job.cover_letter"), key=f"gen_cover_{result_id}", use_container_width=True):
                with st.spinner(t("job.writing_letter")):
                    letter = generate_cover_letter(
                        cv_text,
                        job,
                        match,
                        user_profile,
                        llm_call=call_llm,
                    )
                    save_generated_documents(
                        user_id,
                        result_id,
                        cover_letter_text=letter,
                    )
                    st.session_state[f"cover_{result_id}"] = letter
                    st.success(t("job.cover_ready"))
        with gen_col2:
            if st.button(
                t("job.adapted_cv"),
                key=f"gen_cv_{result_id}",
                use_container_width=True,
                help=t("job.adapted_cv_help"),
            ):
                with st.spinner(t("job.adapting_cv")):
                    adapted = generate_adapted_cv(
                        cv_text,
                        job,
                        match,
                        user_profile,
                        llm_call=call_llm,
                    )
                    save_generated_documents(
                        user_id,
                        result_id,
                        adapted_cv_text=adapted,
                    )
                    st.session_state[f"adapted_{result_id}"] = adapted
                    st.success(t("job.cv_ready"))

    if not show_details:
        st.markdown("</div>", unsafe_allow_html=True)
        return

    apply_pack = st.session_state.get(f"apply_pack_{result_id}")
    letter_text = st.session_state.get(f"cover_{result_id}") or cover_letter_text
    adapted_text = cv_text_for_candidate(
        st.session_state.get(f"adapted_{result_id}") or adapted_cv_text or ""
    )
    offer_url = str(
        st.session_state.get(f"open_offer_{result_id}")
        or (apply_pack or {}).get("job_url")
        or job.get("url")
        or ""
    ).strip()
    if apply_pack and offer_url:
        st.link_button(
            t(
                "job.apply_continue_on_site",
                name=source_name or t("job.apply_open_offer"),
            ),
            offer_url,
            use_container_width=True,
            type="primary",
        )
    profile_text = ""
    if apply_pack or letter_text or adapted_text:
        profile_text = (apply_pack or {}).get("profile_text") or ""
        if not profile_text and user_profile:
            profile_text = format_application_profile_text(build_application_profile(user_profile))
        if profile_text:
            with st.expander(t("job.apply_profile_expander"), expanded=False):
                st.text_area(
                    t("job.apply_profile_expander"),
                    profile_text,
                    height=140,
                    key=f"apply_profile_{result_id}",
                )
        autofill_text = str(st.session_state.get(f"autofill_{result_id}") or "")
        if not autofill_text and user_profile and (letter_text or adapted_text):
            autofill_text = format_application_autofill_text(
                build_application_profile(user_profile),
                cover_letter=letter_text or "",
                adapted_cv=adapted_text or "",
            )
        if autofill_text:
            with st.expander(t("job.apply_autofill_expander"), expanded=True):
                st.caption(t("job.apply_auto_clipboard"))
                st.text_area(
                    t("job.apply_autofill_expander"),
                    autofill_text,
                    height=220,
                    key=f"apply_autofill_{result_id}",
                )

    _render_candidate_documents(
        letter_text=letter_text,
        adapted_text=adapted_text,
        job=job,
        match=match,
        user_profile=user_profile,
        original_cv=cv_text,
        widget_key=str(result_id or rank),
        profile_text=profile_text,
    )

    if enable_tracking and result_id and user_id:
        st.markdown("---")
        track_col1, track_col2 = st.columns([1, 2])
        with track_col1:
            status_options = list(APPLICATION_STATUSES)
            current_idx = (
                status_options.index(application_status)
                if application_status in status_options
                else 0
            )
            new_status = st.selectbox(
                t("job.tracking_status"),
                status_options,
                index=current_idx,
                format_func=application_status_label,
                key=f"track_status_{result_id}",
            )
        with track_col2:
            note_text = st.text_input(
                t("job.tracking_notes"),
                value=notes,
                key=f"track_notes_{result_id}",
            )
        if st.button(t("job.tracking_save"), key=f"save_track_{result_id}"):
            if new_status in ("applied", "interview", "offer"):
                saved = record_application(
                    user_id,
                    result_id,
                    "manual",
                    status=new_status,
                    notes=note_text,
                )
            else:
                saved = update_application_status(
                    user_id,
                    result_id,
                    new_status,
                    notes=note_text,
                )
            if saved:
                st.success(t("job.tracking_saved"))
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def persist_completed_analysis(
    user: dict[str, Any],
    analysis: dict[str, Any],
    cv_fingerprint: str,
    analysis_depth: str,
) -> dict[str, Any] | None:
    """Save analysis to DB, store active CV, optionally send email alert."""
    analysis["analysis_depth"] = analysis_depth
    analysis["results"] = cap_results_to_requested_best(
        list(analysis.get("results") or []),
        analysis,
    )
    try:
        analysis_id = save_analysis(
            int(user["id"]),
            analysis,
            cv_fingerprint=cv_fingerprint,
            analysis_depth=analysis_depth,
        )
        upsert_active_cv_document(
            int(user["id"]),
            cv_fingerprint,
            analysis.get("cv_text", ""),
            analysis.get("criteria"),
        )
        settings = get_notification_settings(int(user["id"]))
        if settings.get("email_alerts_enabled"):
            offers = [
                {
                    "score": int(entry["match"].get("score_correspondance", 0)),
                    "job": entry["job"],
                }
                for entry in analysis.get("results", [])
            ]
            sent, msg = maybe_send_analysis_alert(
                user.get("email", ""),
                user.get("full_name", ""),
                analysis.get("target_job_title", ""),
                offers,
                settings,
            )
            if sent:
                mark_alert_sent(int(user["id"]))
                st.session_state.analysis_notices.append(
                    {"level": "success", "text": f"Alerte e-mail envoyée — {msg}"}
                )
            elif settings.get("alert_frequency") == "after_search" and not email_configured():
                st.session_state.analysis_notices.append(
                    {
                        "level": "info",
                        "text": t("analysis.email_not_configured"),
                    }
                )
        stored = get_analysis(int(user["id"]), analysis_id)
        if stored:
            session_analysis = analysis_to_session_dict(stored)
            return session_analysis
    except Exception as exc:  # noqa: BLE001
        st.session_state.analysis_notices.append(
            {
                "level": "warning",
                "text": t("analysis.save_failed", error=exc),
            }
        )
    return None


def _job_notices(job: dict[str, Any]) -> list[dict[str, str]]:
    raw = job.get("notices_json") or "[]"
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _cached_user_profile(user: dict[str, Any], *, ttl: float = 20.0) -> dict[str, Any]:
    """Reuse the last profile read so page clicks do not hit Postgres every time."""
    user_id = int(user.get("id") or 0)
    now = time.time()
    cached = st.session_state.get("_profile_cache")
    if (
        isinstance(cached, dict)
        and int(cached.get("id") or 0) == user_id
        and (now - float(st.session_state.get("_profile_cache_at") or 0)) < ttl
    ):
        return cached
    fresh = get_user_by_id(user_id) or user
    st.session_state._profile_cache = fresh
    st.session_state._profile_cache_at = now
    return fresh


def _cached_notification_settings(user_id: int, *, ttl: float = 20.0) -> dict[str, Any]:
    now = time.time()
    if (
        st.session_state.get("_notify_cache_uid") == int(user_id)
        and (now - float(st.session_state.get("_notify_cache_at") or 0)) < ttl
    ):
        return dict(st.session_state.get("_notify_cache") or {})
    settings = get_notification_settings(int(user_id))
    st.session_state._notify_cache_uid = int(user_id)
    st.session_state._notify_cache_at = now
    st.session_state._notify_cache = settings
    return settings


def _clear_profile_page_caches() -> None:
    st.session_state.pop("_profile_cache", None)
    st.session_state.pop("_profile_cache_at", None)
    st.session_state.pop("_notify_cache", None)
    st.session_state.pop("_notify_cache_uid", None)
    st.session_state.pop("_notify_cache_at", None)
    st.session_state.pop("_analyses_rows", None)
    st.session_state.pop("_analyses_at", None)
    st.session_state.pop("_analyses_uid", None)


def _cached_list_analyses(user_id: int, *, ttl: float = 12.0) -> list[dict[str, Any]]:
    now = time.time()
    if (
        st.session_state.get("_analyses_uid") == int(user_id)
        and (now - float(st.session_state.get("_analyses_at") or 0)) < ttl
    ):
        return list(st.session_state.get("_analyses_rows") or [])
    rows = list_analyses(int(user_id))
    st.session_state._analyses_uid = int(user_id)
    st.session_state._analyses_at = now
    st.session_state._analyses_rows = rows
    return rows


def _sync_analysis_job_into_session(
    user_id: int,
    job: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Load a finished analysis into session once, then keep showing those results."""
    job = job if job is not None else get_latest_analysis_job(user_id)
    if not job:
        return None
    job_id = int(job["id"])
    if st.session_state.get("applied_analysis_job_id") == job_id:
        return job
    status = str(job.get("status") or "")
    if status == "completed" and job.get("analysis_id"):
        stored = get_analysis(user_id, int(job["analysis_id"]))
        if stored:
            st.session_state.analysis = analysis_to_session_dict(stored)
            st.session_state.pdf_fingerprint = job.get("cv_fingerprint")
            st.session_state.analysis_notices = _job_notices(job)
            st.session_state.applied_analysis_job_id = job_id
            st.session_state.analysis_job_id = job_id
            st.session_state.dashboard_analysis_select = int(job["analysis_id"])
            st.session_state.pop("_analyses_rows", None)
            st.session_state.pop("_analyses_at", None)
            return job
    if status == "failed":
        notices = _job_notices(job)
        error = str(job.get("error_message") or "").strip()
        if not notices:
            notices = [{"level": "error", "text": t("analysis.queue.failed", error=error or "—")}]
        st.session_state.analysis_notices = notices
        st.session_state.applied_analysis_job_id = job_id
        st.session_state.analysis_job_id = job_id
    return job


def _enqueue_user_analysis_error(code: str) -> str:
    if code == "pdf_too_large":
        return t("analysis.queue.pdf_too_large")
    if code == "missing_cv":
        return t("analysis.missing_cv")
    if code == "already":
        return t("analysis.queue.already")
    return t("analysis.queue.failed", error=code)


def _render_analysis_job_progress(job: dict[str, Any]) -> None:
    """Show a simple progress bar until matching finishes. No ticket number."""
    st.info(t("analysis.progress.working"))

    @st.fragment(run_every=ANALYSIS_JOB_POLL_SECONDS)
    def _poll_analysis_progress() -> None:
        fresh = get_analysis_job(int(job["id"]), int(job["user_id"])) or job
        if str(fresh.get("status") or "") in {"queued", "running"}:
            percent = int(fresh.get("progress_percent") or 0)
            if percent < 3:
                percent = 3
            label = str(fresh.get("progress_label") or t("analysis.progress.working"))
            st.progress(min(1.0, max(0.03, percent / 100.0)), text=label)
            return
        st.rerun()

    _poll_analysis_progress()


def _format_history_datetime(value: str | None) -> str:
    if not value:
        return "—"
    return str(value)[:16].replace("T", " ")


def _render_application_entry(
    entry: dict[str, Any],
    user_id: int,
    *,
    key_prefix: str,
    user_profile: dict[str, Any] | None = None,
) -> None:
    """Render one application with expandable offer and dossier details."""
    job = entry.get("job") or {}
    match = entry.get("match") or {}
    title = job.get("title") or entry.get("target_job_title") or "—"
    company = job.get("company") or "—"
    location = job.get("location") or "—"
    applied_at = _format_history_datetime(entry.get("status_updated_at"))
    method = application_method_label(entry.get("application_method"))
    status = application_status_label(entry.get("application_status", "new"))
    score = int(entry.get("score") or 0)
    result_id = int(entry["result_id"])
    widget_key = f"{key_prefix}_{result_id}"
    analysis_date = _format_history_datetime(entry.get("analysis_created_at"))

    with st.container(border=True):
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(f"### {title}")
            st.markdown(f"**{company}** · {location}")
            st.caption(
                f"{t('history.application_score', score=score)} · "
                f"{t('history.application_date', date=applied_at)}"
            )
            st.caption(t("history.application_method", method=method))
            st.caption(t("history.application_status", status=status))
            if entry.get("notes"):
                st.caption(entry["notes"])
        with header_col2:
            if job.get("url"):
                st.link_button(
                    t("history.application_open"),
                    job["url"],
                    use_container_width=True,
                    key=f"{widget_key}_header_link",
                )

        with st.expander(
            t("applications.view_offer"),
            expanded=False,
            key=f"{widget_key}_expander",
        ):
            st.caption(
                t(
                    "applications.analysis_context",
                    title=entry.get("target_job_title") or "—",
                    date=analysis_date,
                )
            )
            if job.get("contract_type") or job.get("inferred_contract"):
                contract = job.get("inferred_contract") or job.get("contract_type")
                st.markdown(f"**{t('job.contract_label')}** {contract}")
            if job.get("source"):
                st.markdown(f"**{t('job.source_label')}** {job.get('source', '')}")
            st.markdown(f"**{t('job.publication_label')}** {format_job_published_label(job)}")

            if match.get("synthese_ats"):
                st.info(match["synthese_ats"])

            description = str(job.get("description") or "").strip()
            st.markdown(f"**{t('applications.description')}**")
            if description:
                st.markdown(description[:6000])
            else:
                st.caption(t("applications.no_description"))

            letter = (entry.get("cover_letter_text") or "").strip()
            adapted = cv_text_for_candidate(entry.get("adapted_cv_text") or "")
            profile = user_profile or get_user_by_id(user_id) or {}
            if letter or adapted:
                _render_candidate_documents(
                    letter_text=letter,
                    adapted_text=adapted,
                    job=job,
                    match=match,
                    user_profile=profile,
                    original_cv="",
                    widget_key=widget_key,
                    show_bundle=True,
                )
            else:
                if not letter:
                    st.caption(t("applications.no_letter"))
                if not adapted:
                    st.caption(t("applications.no_cv"))

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if job.get("url"):
                    st.link_button(
                        t("history.application_open"),
                        job["url"],
                        use_container_width=True,
                        key=f"{widget_key}_body_link",
                    )
            with action_col2:
                if st.button(
                    t("history.application_view_dashboard"),
                    key=f"{widget_key}_dash",
                    use_container_width=True,
                ):
                    st.session_state.dashboard_analysis_select = int(entry["analysis_id"])
                    _request_navigation("dashboard")


def _render_applications_list(
    entries: list[dict[str, Any]],
    user_id: int,
    *,
    key_prefix: str,
    user_profile: dict[str, Any] | None = None,
) -> None:
    if not entries:
        st.info(t("applications.empty"))
        return
    visible = _paged_items(
        entries,
        key=f"{key_prefix}_page",
        page_size=JOB_CARDS_PER_PAGE,
        filter_signature=key_prefix,
    )
    full_by_id = get_analysis_results_by_ids(
        user_id,
        [int(entry["result_id"]) for entry in visible if entry.get("result_id")],
    )
    for entry in visible:
        payload = full_by_id.get(int(entry["result_id"]))
        if payload:
            entry["job"] = payload.get("job") or entry.get("job")
            entry["match"] = payload.get("match") or entry.get("match")
            entry["cover_letter_text"] = payload.get("cover_letter_text")
            entry["adapted_cv_text"] = payload.get("adapted_cv_text")
        _render_application_entry(
            entry,
            user_id,
            key_prefix=key_prefix,
            user_profile=user_profile,
        )


def render_applications_page(user: dict[str, Any]) -> None:
    """Dedicated page to consult manual and automatic applications."""
    _flush_analysis_notices()
    user_id = int(user["id"])
    applications = list_user_applications(user_id)
    auto_apps = [entry for entry in applications if entry.get("channel") == "automatic"]
    manual_apps = [entry for entry in applications if entry.get("channel") == "manual"]
    user_profile = _cached_user_profile(user)
    channel_map = {
        "all": applications,
        "automatic": auto_apps,
        "manual": manual_apps,
    }
    channel = st.radio(
        t("applications.tab_all", count=len(applications)),
        list(APPLICATION_CHANNEL_KEYS),
        format_func=lambda key: (
            t("applications.tab_all", count=len(applications))
            if key == "all"
            else t("applications.tab_auto", count=len(auto_apps))
            if key == "automatic"
            else t("applications.tab_manual", count=len(manual_apps))
        ),
        horizontal=True,
        key="applications_channel",
        label_visibility="collapsed",
    )
    _render_applications_list(
        channel_map.get(channel, applications),
        user_id,
        key_prefix=f"app_{channel}",
        user_profile=user_profile,
    )


def render_support_page(user: dict[str, Any]) -> None:
    """Private chat with the platform administrator — one or more conversations."""
    _flush_analysis_notices()
    user_id = int(user["id"])
    conversations = user_support_conversations(user_id)
    selected_id = st.session_state.get("support_active_conversation_id")
    conv_ids = [int(item["id"]) for item in conversations if item.get("id") is not None]
    if selected_id not in conv_ids:
        selected_id = conv_ids[0] if conv_ids else None
        if selected_id is not None:
            st.session_state.support_active_conversation_id = selected_id

    if selected_id:
        mark_user_support_read(user_id, conversation_id=int(selected_id))
    else:
        mark_user_support_read(user_id)
    st.session_state._support_unread = user_support_unread(user_id)
    st.session_state._support_unread_uid = user_id
    st.session_state._support_unread_at = time.time()

    messages = (
        user_support_thread(user_id, conversation_id=int(selected_id))
        if selected_id
        else []
    )

    st.markdown(
        (
            f'<p class="msg-title">{html.escape(t("hero.support.title"))}</p>'
            f'<p class="msg-sub">{html.escape(t("hero.support.subtitle"))}</p>'
        ),
        unsafe_allow_html=True,
    )

    list_col, pane_col = st.columns([0.95, 2.05], gap="medium")
    with list_col:
        st.markdown(
            f'<div class="msg-list-head"><strong>{html.escape(t("support.conversations"))}</strong></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            t("support.new"),
            key="support_new",
            use_container_width=True,
            type="primary",
        ):
            created = start_user_support_conversation(user_id)
            if created:
                st.session_state.support_active_conversation_id = int(created["id"])
            st.rerun()
        if conversations:
            by_id = {int(item["id"]): item for item in conversations}

            def _conv_label(cid: int) -> str:
                item = by_id.get(int(cid)) or {}
                preview = str(item.get("last_body") or "").strip().replace("\n", " ")
                if not preview:
                    preview = t("support.new_title")
                elif len(preview) > 72:
                    preview = preview[:69] + "…"
                unread = int(item.get("unread") or 0)
                title = t("support.admin")
                if unread:
                    return f"{title}  ({unread})\n{preview}"
                return f"{title}\n{preview}"

            picked = st.radio(
                t("support.conversations"),
                conv_ids,
                format_func=_conv_label,
                key="support_active_conversation_id",
                label_visibility="collapsed",
            )
            selected_id = int(picked)
            messages = user_support_thread(user_id, conversation_id=selected_id)
        else:
            st.markdown(
                f'<p class="msg-empty-list">{html.escape(t("support.empty_list"))}</p>',
                unsafe_allow_html=True,
            )

    with pane_col:
        if not selected_id:
            st.markdown(
                (
                    '<div class="msg-empty-pane">'
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                    '<path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>'
                    "</svg>"
                    f"<p>{html.escape(t('support.empty_pane'))}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            return
        st.markdown(
            render_support_thread_html(
                messages,
                user_label=t("support.you"),
                admin_label=t("support.admin"),
                empty_text=t("support.empty"),
            ),
            unsafe_allow_html=True,
        )
        with st.form("support_user_form", clear_on_submit=True):
            body = st.text_area(
                t("support.placeholder"),
                height=110,
                max_chars=4000,
                label_visibility="collapsed",
                placeholder=t("support.placeholder"),
            )
            send_col, refresh_col = st.columns([2, 1])
            with send_col:
                submitted = st.form_submit_button(
                    t("support.send"),
                    type="primary",
                    use_container_width=True,
                )
            with refresh_col:
                refresh = st.form_submit_button(t("support.refresh"), use_container_width=True)
        if refresh:
            st.rerun()
        if submitted:
            ok, message, _saved = send_user_support_message(
                user_id,
                body,
                conversation_id=int(selected_id),
            )
            if ok:
                st.success(t("support.sent"))
                st.rerun()
            st.error(
                t("support.empty_error")
                if "vide" in message.lower() or "empty" in message.lower()
                else message
            )


def render_floating_chat_fab(*, unread: int = 0, current_page: str = "") -> None:
    """Teal chat logo pinned to the viewport so page changes never move it."""
    import streamlit.components.v1 as components

    unread_n = int(unread or 0)
    help_label = json.dumps(t("support.fab_help"), ensure_ascii=False)
    primary = THEME["primary"]
    primary_dark = THEME["primary_dark"]
    accent = THEME["accent"]
    nav_script = json.dumps(
        """
(function(){
  function openMessaging(){
    var root = document.querySelector('[class*="st-key-main_navigation"]')
      || document.querySelector('[data-testid="stSidebar"]');
    if (!root) return false;
    var labels = root.querySelectorAll('label');
    for (var i = 0; i < labels.length; i++) {
      var text = labels[i].textContent || '';
      if (text.indexOf('Messagerie') !== -1 || text.indexOf('Inbox') !== -1) {
        var input = labels[i].querySelector('input');
        if (input && input.checked) return true;
        if (labels[i].getAttribute('aria-checked') === 'true') return true;
        if (input) { input.click(); return true; }
        labels[i].click();
        return true;
      }
    }
    var radios = root.querySelectorAll('input[type="radio"]');
    if (radios.length >= 5) { radios[4].click(); return true; }
    return false;
  }
  if (!window.__dbChatFabNav) {
    window.__dbChatFabNav = true;
    document.addEventListener('click', function(ev) {
      var target = ev.target && ev.target.closest && ev.target.closest('#db-chat-fab');
      if (!target) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (target.getAttribute('data-page') === 'support') return;
      openMessaging();
    }, true);
  }
})();
        """.strip()
    )
    components.html(
        f"""
<script>
(function() {{
  const doc = window.parent.document;
  const label = {help_label};
  const unread = {unread_n};
  const svg = '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M18 21h28a5 5 0 0 1 5 5v18a5 5 0 0 1-5 5H29l-9 7v-7h-2a5 5 0 0 1-5-5V26a5 5 0 0 1 5-5z" fill="none" stroke="#ffffff" stroke-width="3.2" stroke-linejoin="round"/></svg>';
  let fab = doc.getElementById("db-chat-fab");
  if (!fab || fab.tagName !== "BUTTON") {{
    if (fab) fab.remove();
    fab = doc.createElement("button");
    fab.id = "db-chat-fab";
    fab.type = "button";
    doc.body.appendChild(fab);
  }}
  fab.innerHTML = svg;
  fab.setAttribute("aria-label", label);
  fab.title = label;
  fab.setAttribute("data-page", {json.dumps(current_page or "")});
  if (!doc.getElementById("db-chat-fab-nav-script")) {{
    const script = doc.createElement("script");
    script.id = "db-chat-fab-nav-script";
    script.textContent = {nav_script};
    doc.documentElement.appendChild(script);
  }}
  let badge = doc.getElementById("db-chat-fab-badge");
  if (unread) {{
    if (!badge) {{
      badge = doc.createElement("span");
      badge.id = "db-chat-fab-badge";
      doc.body.appendChild(badge);
    }}
    badge.textContent = String(unread);
  }} else if (badge) {{
    badge.remove();
  }}
  let style = doc.getElementById("db-chat-fab-style");
  if (!style) {{
    style = doc.createElement("style");
    style.id = "db-chat-fab-style";
    doc.head.appendChild(style);
  }}
  style.textContent = `
    #db-chat-fab {{
      position: fixed !important;
      right: 20px !important;
      bottom: 20px !important;
      z-index: 2147483647 !important;
      width: 64px !important;
      height: 64px !important;
      padding: 14px !important;
      border: 0 !important;
      border-radius: 50% !important;
      cursor: pointer !important;
      display: block !important;
      box-sizing: border-box !important;
      text-decoration: none !important;
      background: linear-gradient(135deg, {primary}, {primary_dark}) !important;
      box-shadow: 0 0 0 3px {accent}, 0 12px 26px rgba(14, 116, 144, 0.42) !important;
      overflow: hidden !important;
      animation: dbChatPulse 2.2s ease-in-out infinite !important;
    }}
    #db-chat-fab svg {{
      width: 100% !important;
      height: 100% !important;
      display: block !important;
      pointer-events: none !important;
    }}
    #db-chat-fab:hover {{
      animation: none !important;
      transform: scale(1.08) !important;
    }}
    #db-chat-fab-badge {{
      position: fixed !important;
      right: 16px !important;
      bottom: 76px !important;
      z-index: 2147483647 !important;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      border-radius: 999px;
      background: {accent};
      color: #0B1220;
      font: 800 11px/20px system-ui, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
    }}
    @keyframes dbChatPulse {{
      0%, 100% {{
        transform: scale(1);
        box-shadow: 0 0 0 3px {accent}, 0 16px 32px rgba(14, 116, 144, 0.42), 0 0 0 0 rgba(14, 116, 144, 0.35);
      }}
      50% {{
        transform: scale(1.07);
        box-shadow: 0 0 0 3px {accent}, 0 16px 32px rgba(14, 116, 144, 0.5), 0 0 0 10px rgba(14, 116, 144, 0);
      }}
    }}
  `;
}})();
</script>
        """,
        height=0,
    )


def render_history_page(user: dict[str, Any]) -> None:
    """List past analyses and reload one into the session."""
    _flush_analysis_notices()
    user_id = int(user["id"])
    application_count = count_user_applications(user_id)
    if application_count:
        info_col1, info_col2 = st.columns([3, 1])
        with info_col1:
            st.info(t("history.applications_banner", count=application_count))
        with info_col2:
            if st.button(t("applications.go_to_applications"), use_container_width=True):
                _request_navigation("applications")

    rows = _cached_list_analyses(user_id)
    st.markdown(
        f'<p class="section-title">{t("history.analyses_title")}</p>',
        unsafe_allow_html=True,
    )
    if not rows:
        st.info(t("history.empty_start"))
        return
    visible_rows = _paged_items(
        rows,
        key="history_page",
        page_size=HISTORY_ROWS_PER_PAGE,
        filter_signature=("history", user_id, len(rows)),
    )
    for row in visible_rows:
        created = row.get("created_at", "")[:16].replace("T", " ")
        label = t(
            "history.row_label",
            created=created,
            title=row.get("target_job_title", "—"),
            count=row.get("jobs_found", 0),
            depth=row.get("analysis_depth", "standard"),
        )
        with st.container(border=True):
            st.markdown(label)
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("history.view"), key=f"load_analysis_{row['id']}"):
                    stored = get_analysis(int(user["id"]), int(row["id"]))
                    if stored:
                        st.session_state.analysis = analysis_to_session_dict(stored)
                        st.session_state.pdf_fingerprint = row.get("cv_fingerprint")
                        st.session_state.dashboard_analysis_select = int(row["id"])
                        st.session_state.analysis_notices = [
                            {
                                "level": "success",
                                "text": t("history.loaded", id=row["id"]),
                            }
                        ]
                        st.rerun()
            with c2:
                st.caption(t("history.engine", engine=row.get("job_provider", "—")))


def _analysis_dashboard_label(row: dict[str, Any]) -> str:
    created = str(row.get("created_at", ""))[:16].replace("T", " ")
    return t(
        "dashboard.analysis_label",
        created=created,
        title=row.get("target_job_title", "—"),
        count=row.get("jobs_found", 0),
        depth=row.get("analysis_depth", "standard"),
    )


def _connected_accounts_map(user_id: int | None) -> dict[str, dict[str, Any]]:
    if not user_id:
        return {}
    return {
        str(row.get("provider") or ""): dict(row)
        for row in list_connected_job_accounts(int(user_id))
        if row.get("provider")
    }


def _status_counts_from_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in APPLICATION_STATUSES}
    for entry in entries:
        status = str(entry.get("application_status") or "new")
        if status in counts:
            counts[status] += 1
    counts["all"] = len(entries)
    return counts


def _filter_dashboard_entries(
    entries: list[dict[str, Any]],
    *,
    status_filter: str,
    min_score: int,
    company_query: str,
    sort_by: str,
) -> list[dict[str, Any]]:
    company_q = (company_query or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        if status_filter and status_filter != "all" and entry.get("application_status") != status_filter:
            continue
        if int(entry.get("score") or 0) < int(min_score or 0):
            continue
        if company_q:
            company = str((entry.get("job") or {}).get("company") or "").lower()
            if company_q not in company:
                continue
        filtered.append(entry)
    if sort_by == "score_asc":
        filtered.sort(key=lambda item: int(item.get("score") or 0))
    elif sort_by == "date_asc":
        filtered.sort(key=lambda item: str(item.get("analysis_created_at") or ""))
    elif sort_by == "date_desc":
        filtered.sort(
            key=lambda item: str(item.get("analysis_created_at") or ""),
            reverse=True,
        )
    else:
        filtered.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return filtered


def _paged_items(
    items: list[Any],
    *,
    key: str,
    page_size: int,
    filter_signature: Any = None,
) -> list[Any]:
    """Show a compact page of items with prev/next controls."""
    sig_key = f"{key}_sig"
    if filter_signature is not None and st.session_state.get(sig_key) != filter_signature:
        st.session_state[key] = 1
        st.session_state[sig_key] = filter_signature
    total = len(items)
    if total <= page_size:
        return items
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get(key, 1) or 1), 1), pages)
    st.session_state[key] = page
    prev_col, mid_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if st.button(
            t("common.previous"),
            disabled=page <= 1,
            key=f"{key}_prev",
            use_container_width=True,
        ):
            st.session_state[key] = page - 1
            st.rerun()
    with mid_col:
        st.caption(t("dashboard.page_status", page=page, pages=pages))
    with next_col:
        if st.button(
            t("common.next"),
            disabled=page >= pages,
            key=f"{key}_next",
            use_container_width=True,
        ):
            st.session_state[key] = page + 1
            st.rerun()
    start = (page - 1) * page_size
    return items[start : start + page_size]


_SCORE_CHART_BUCKETS = (
    (0, 49, "0–49"),
    (50, 64, "50–64"),
    (65, 74, "65–74"),
    (75, 89, "75–89"),
    (90, 100, "90–100"),
)
_STATUS_CHART_COLORS = (
    "#94a3b8",
    "#0E7490",
    "#0F9F6E",
    "#E8B923",
    "#22c55e",
    "#E11D48",
    "#64748b",
)


def dashboard_insight_rows(
    entries: list[dict[str, Any]],
    counts: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build chart rows for status mix and ATS score bands."""
    status_rows = [
        {
            "status": application_status_label(status),
            "count": int(counts.get(status, 0)),
        }
        for status in APPLICATION_STATUSES
        if int(counts.get(status, 0)) > 0
    ]
    bucket_totals = {label: 0 for _low, _high, label in _SCORE_CHART_BUCKETS}
    for entry in entries:
        score = int(entry.get("score") or 0)
        for low, high, label in _SCORE_CHART_BUCKETS:
            if low <= score <= high:
                bucket_totals[label] += 1
                break
    score_rows = [
        {"band": label, "count": bucket_totals[label]}
        for _low, _high, label in _SCORE_CHART_BUCKETS
        if bucket_totals[label]
    ]
    return status_rows, score_rows


def dashboard_quality_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """ATS quality board for the candidate dashboard."""
    total = len(entries)
    scores = [int(entry.get("score") or 0) for entry in entries]
    avg = round(sum(scores) / total, 1) if total else 0.0
    high = sum(1 for score in scores if score >= 75)
    applied = sum(
        1
        for entry in entries
        if str(entry.get("application_status") or "") in ("applied", "interview", "offer")
    )
    bands = (
        ("high", t("dashboard.band_high"), lambda score: score >= 75),
        ("mid", t("dashboard.band_mid"), lambda score: 50 <= score < 75),
        ("low", t("dashboard.band_low"), lambda score: score < 50),
    )
    band_rows = []
    for key, label, matches in bands:
        count = sum(1 for score in scores if matches(score))
        band_rows.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "pct": round((count / total) * 100, 1) if total else 0.0,
            }
        )
    top = sorted(entries, key=lambda item: int(item.get("score") or 0), reverse=True)[:4]
    return {
        "total": total,
        "avg_score": avg,
        "high": high,
        "high_rate": round((high / total) * 100, 1) if total else 0.0,
        "applied": applied,
        "bands": band_rows,
        "top": top,
    }


def _score_tone(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "mid"
    return "low"


def _score_ring_color(score: float) -> str:
    tone = _score_tone(score)
    if tone == "high":
        return "#0F9F6E"
    if tone == "mid":
        return "#E8B923"
    return "#0E7490"


def _render_dashboard_quality_board(entries: list[dict[str, Any]]) -> None:
    """2026-style matching quality board: average ATS, bands and top offers."""
    summary = dashboard_quality_summary(entries)
    avg = float(summary["avg_score"])
    ring_label = f"{avg:g}"
    high_hint = t("dashboard.high_hint", count=int(summary["high"]), rate=f"{summary['high_rate']:g}")
    bands_html = "".join(
        (
            '<div class="dash-band">'
            f"<span>{html.escape(str(band['label']))}</span>"
            f'<span class="meta">{int(band["count"])} · {float(band["pct"]):g}%</span>'
            f'<div class="dash-band-track"><i class="{html.escape(str(band["key"]))}" '
            f'style="width:{float(band["pct"])}%"></i></div>'
            "</div>"
        )
        for band in summary["bands"]
    )
    if summary["top"]:
        matches_html = "".join(
            (
                '<article class="dash-top-match">'
                f'<div class="dash-score-pill {_score_tone(int(item.get("score") or 0))}">'
                f'{int(item.get("score") or 0)}</div>'
                "<div>"
                f'<strong>{html.escape(str((item.get("job") or {}).get("title") or "—"))}</strong>'
                "<small>"
                + html.escape(
                    " · ".join(
                        part
                        for part in (
                            str((item.get("job") or {}).get("company") or "").strip(),
                            str((item.get("job") or {}).get("location") or "").strip(),
                        )
                        if part
                    )
                    or "—"
                )
                + "</small>"
                "</div></article>"
            )
            for item in summary["top"]
        )
    else:
        matches_html = f'<p class="dash-empty-insight">{html.escape(t("dashboard.top_empty"))}</p>'
    st.markdown(
        (
            '<div class="dash-quality">'
            '<div class="dash-quality-kpis">'
            '<article class="stat-card dash-quality-hero">'
            f'<div class="dash-score-ring" style="--p:{max(0.0, min(100.0, avg))};'
            f'--ring:{_score_ring_color(avg)}"><span>{html.escape(ring_label)}</span></div>'
            "<div>"
            f'<p class="stat-card-label">{html.escape(t("dashboard.quality_title"))}</p>'
            f'<p class="stat-card-value dash-quality-title">{html.escape(t("dashboard.metric_avg_score"))}</p>'
            f'<p class="stat-card-hint">{html.escape(high_hint)}</p>'
            "</div></article>"
            '<article class="stat-card">'
            f'<p class="stat-card-label">{html.escape(t("dashboard.metric_scored"))}</p>'
            f'<p class="stat-card-value">{int(summary["total"])}</p>'
            f'<p class="stat-card-hint">{html.escape(t("dashboard.metric_scored_hint"))}</p>'
            "</article>"
            '<article class="stat-card">'
            f'<p class="stat-card-label">{html.escape(t("dashboard.metric_high"))}</p>'
            f'<p class="stat-card-value">{int(summary["high"])}</p>'
            f'<p class="stat-card-hint">{html.escape(t("dashboard.metric_high_hint"))}</p>'
            "</article>"
            '<article class="stat-card">'
            f'<p class="stat-card-label">{html.escape(t("dashboard.metric_pipeline"))}</p>'
            f'<p class="stat-card-value">{int(summary["applied"])}</p>'
            f'<p class="stat-card-hint">{html.escape(t("dashboard.metric_pipeline_hint"))}</p>'
            "</article>"
            "</div>"
            '<div class="dash-quality-split">'
            '<section class="dash-quality-panel">'
            f"<h3>{html.escape(t('dashboard.chart_scores'))}</h3>"
            f'<p>{html.escape(t("dashboard.quality_subtitle"))}</p>'
            f'<div class="dash-band-list">{bands_html}</div>'
            "</section>"
            '<section class="dash-quality-panel">'
            f"<h3>{html.escape(t('dashboard.top_matches'))}</h3>"
            f'<p>{html.escape(t("dashboard.top_matches_hint"))}</p>'
            f'<div class="dash-top-list">{matches_html}</div>'
            "</section>"
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )


def _render_dashboard_insight_charts(
    entries: list[dict[str, Any]],
    counts: dict[str, int],
) -> None:
    """Interactive status and score charts for the candidate dashboard."""
    status_rows, score_rows = dashboard_insight_rows(entries, counts)
    if not status_rows and not score_rows:
        return
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        return

    st.markdown(
        f'<p class="section-title">{html.escape(t("dashboard.insights_title"))}</p>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    tooltip_count = t("dashboard.chart_count")
    if status_rows:
        with left:
            st.markdown('<div class="dash-chart-panel">', unsafe_allow_html=True)
            st.caption(t("dashboard.chart_status"))
            status_chart = (
                alt.Chart(pd.DataFrame(status_rows))
                .mark_arc(innerRadius=48, outerRadius=78, stroke="#fff", strokeWidth=2)
                .encode(
                    theta=alt.Theta("count:Q", stack=True),
                    color=alt.Color(
                        "status:N",
                        legend=alt.Legend(orient="bottom", title=None, columns=2),
                        scale=alt.Scale(
                            domain=[row["status"] for row in status_rows],
                            range=list(_STATUS_CHART_COLORS[: len(status_rows)]),
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("status:N", title=t("dashboard.status")),
                        alt.Tooltip("count:Q", title=tooltip_count),
                    ],
                )
                .properties(height=220)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(status_chart, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    if score_rows:
        with right:
            st.markdown('<div class="dash-chart-panel">', unsafe_allow_html=True)
            st.caption(t("dashboard.chart_scores"))
            score_chart = (
                alt.Chart(pd.DataFrame(score_rows))
                .mark_bar(cornerRadiusEnd=8, color="#0E7490", size=22)
                .encode(
                    x=alt.X("band:N", sort=[row["band"] for row in score_rows], title=None),
                    y=alt.Y("count:Q", title=None),
                    tooltip=[
                        alt.Tooltip("band:N", title=t("dashboard.chart_scores")),
                        alt.Tooltip("count:Q", title=tooltip_count),
                    ],
                )
                .properties(height=220)
                .configure_axis(grid=False, labelColor="#64748b", domainColor="#e2e8f0")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(score_chart, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


def render_dashboard_page(user: dict[str, Any]) -> None:
    """Dashboard scoped to a selected analysis with filters and tracking."""
    _flush_analysis_notices()
    user_id = int(user["id"])
    render_page_hero(
        t("hero.dashboard.title"),
        t("hero.dashboard.subtitle"),
        badge=t("hero.dashboard.badge"),
    )
    analyses = _cached_list_analyses(user_id)
    if not analyses:
        st.markdown(
            (
                '<div class="empty-panel">'
                '<div class="empty-icon">📊</div>'
                f"<h2>{html.escape(t('dashboard.empty_title'))}</h2>"
                f"<p>{html.escape(t('dashboard.empty_text'))}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        if st.button(
            t("dashboard.empty_cta"),
            type="primary",
            use_container_width=True,
            key="dashboard_empty_cta",
        ):
            _request_navigation("analysis")
        return

    analysis_by_id = {int(row["id"]): row for row in analyses}
    analysis_ids = list(analysis_by_id.keys())

    if "dashboard_analysis_select" not in st.session_state:
        session_analysis = st.session_state.get("analysis") or {}
        session_id = session_analysis.get("analysis_id")
        if session_id in analysis_by_id:
            st.session_state.dashboard_analysis_select = int(session_id)
        else:
            st.session_state.dashboard_analysis_select = analysis_ids[0]
    elif st.session_state.dashboard_analysis_select not in analysis_by_id:
        st.session_state.dashboard_analysis_select = analysis_ids[0]

    selected_id = st.selectbox(
        t("dashboard.analysis_select"),
        options=analysis_ids,
        format_func=lambda aid: _analysis_dashboard_label(analysis_by_id[aid]),
        key="dashboard_analysis_select",
    )
    selected_meta = analysis_by_id[selected_id]
    created = str(selected_meta.get("created_at", ""))[:16].replace("T", " ")
    pills = [
        f"#{selected_id}",
        created,
        str(selected_meta.get("job_provider") or "—"),
        f"{selected_meta.get('jobs_raw', 0)} → {selected_meta.get('jobs_found', 0)}",
    ]
    pills_html = "".join(
        f'<span class="dash-meta-pill">{html.escape(str(item))}</span>' for item in pills if item
    )
    st.markdown(f'<div class="dash-meta-pills">{pills_html}</div>', unsafe_allow_html=True)

    display_limit = matching_display_limit(selected_meta)
    all_entries = list_dashboard_results(
        user_id,
        analysis_id=selected_id,
        limit=display_limit,
    )
    counts = _status_counts_from_entries(all_entries)
    stat_items = (
        (t("dashboard.metric_total"), counts.get("all", 0)),
        (t("dashboard.metric_saved"), counts.get("saved", 0)),
        (t("dashboard.metric_applied"), counts.get("applied", 0)),
        (t("dashboard.metric_interview"), counts.get("interview", 0)),
    )
    stats_html = "".join(
        (
            '<div class="stat-card">'
            f'<p class="stat-card-label">{html.escape(str(label))}</p>'
            f'<p class="stat-card-value">{int(value)}</p>'
            "</div>"
        )
        for label, value in stat_items
    )
    st.markdown(f'<div class="stat-card-grid">{stats_html}</div>', unsafe_allow_html=True)

    _render_dashboard_quality_board(all_entries)
    _render_dashboard_insight_charts(all_entries, counts)

    st.markdown(
        f'<p class="filter-bar-title">{html.escape(t("dashboard.filters_title"))}</p>',
        unsafe_allow_html=True,
    )
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status_filter = st.selectbox(
            t("dashboard.status"),
            ["all", *APPLICATION_STATUSES],
            format_func=lambda value: t("dashboard.all")
            if value == "all"
            else application_status_label(value),
            key="dash_status_filter",
        )
    with f2:
        sort_by = st.selectbox(
            t("common.sort"),
            ["score_desc", "score_asc", "date_desc", "date_asc"],
            format_func=sort_label,
            key="dash_sort",
        )
    with f3:
        min_score = st.slider(t("dashboard.min_score"), 0, 100, 0, key="dash_min_score")
    with f4:
        company_query = st.text_input(t("common.company"), key="dash_company")

    entries = _filter_dashboard_entries(
        all_entries,
        status_filter=status_filter,
        min_score=min_score,
        company_query=company_query,
        sort_by=sort_by,
    )
    if not entries:
        st.info(t("dashboard.no_results"))
        return

    st.markdown(
        f'<p class="dash-results-line">{html.escape(t("dashboard.results_count", count=len(entries), id=selected_id))}</p>',
        unsafe_allow_html=True,
    )
    visible_entries = _paged_items(
        entries,
        key="dash_page",
        page_size=JOB_CARDS_PER_PAGE,
        filter_signature=(selected_id, status_filter, sort_by, min_score, company_query),
    )
    user_profile = _cached_user_profile(user)
    apply_context = get_analysis_apply_context(user_id, selected_id) or {}
    cv_text = apply_context.get("cv_text", "")
    profile_snapshot = apply_context.get("user_profile") or user_profile
    connected_accounts = _connected_accounts_map(user_id)
    page_offset = 0
    if st.session_state.get("dash_page"):
        page_offset = (int(st.session_state.get("dash_page") or 1) - 1) * JOB_CARDS_PER_PAGE
    for idx, entry in enumerate(visible_entries, start=page_offset + 1):
        render_job_card(
            entry["job"],
            entry["match"],
            idx,
            result_id=entry["result_id"],
            application_status=entry.get("application_status", "new"),
            notes=entry.get("notes", ""),
            cover_letter_text=entry.get("cover_letter_text"),
            adapted_cv_text=entry.get("adapted_cv_text"),
            user_id=user_id,
            cv_text=cv_text,
            user_profile=profile_snapshot,
            enable_tracking=True,
            connected_accounts=connected_accounts,
        )


def render_notification_settings(user: dict[str, Any], job_provider: str) -> None:
    """Alert email and scheduled search preferences."""
    settings = get_notification_settings(int(user["id"]))
    st.markdown(
        f'<p class="section-title">{t("notify.title")}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="profile-section-hint">{t("notify.hint")}</p>',
        unsafe_allow_html=True,
    )
    if not email_configured():
        st.caption(t("notify.email_config_hint"))
    with st.form(f"notification_settings_{user['id']}"):
        email_alerts = st.checkbox(
            t("notify.email_checkbox"),
            value=bool(settings.get("email_alerts_enabled")),
        )
        alert_min_score = st.slider(
            t("notify.min_score"),
            50,
            95,
            int(settings.get("alert_min_score", 70)),
        )
        auto_search = st.checkbox(
            t("notify.auto_search"),
            value=bool(settings.get("auto_search_enabled")),
            help=t("notify.auto_search_need_cv"),
        )
        sched_col1, sched_col2, sched_col3 = st.columns(3)
        with sched_col1:
            weekday = st.selectbox(
                t("notify.weekday"),
                AUTO_SEARCH_WEEKDAYS,
                index=AUTO_SEARCH_WEEKDAYS.index(settings.get("auto_search_weekday", "daily"))
                if settings.get("auto_search_weekday") in AUTO_SEARCH_WEEKDAYS
                else 0,
                format_func=weekday_label,
            )
        with sched_col2:
            hour = st.selectbox(
                t("notify.time"),
                list(range(24)),
                index=int(settings.get("auto_search_hour", 8)),
            )
        with sched_col3:
            auto_depth = st.selectbox(
                t("notify.depth"),
                ANALYSIS_DEPTH_OPTIONS,
                index=ANALYSIS_DEPTH_OPTIONS.index(settings.get("auto_search_depth", "standard"))
                if settings.get("auto_search_depth") in ANALYSIS_DEPTH_OPTIONS
                else 1,
                format_func=analysis_depth_label,
            )
        if st.form_submit_button(t("notify.save"), use_container_width=True):
            save_notification_settings(
                int(user["id"]),
                {
                    "email_alerts_enabled": email_alerts,
                    "alert_min_score": alert_min_score,
                    "alert_frequency": "after_search",
                    "auto_search_enabled": auto_search,
                    "auto_search_weekday": weekday,
                    "auto_search_hour": hour,
                    "auto_search_provider": job_provider,
                    "auto_search_depth": auto_depth,
                },
            )
            st.success(t("notify.saved"))
            st.rerun()


def run_auto_search_for_user(user: dict[str, Any], job_provider: str) -> None:
    """Queue a scheduled search using the last active CV (same matching as a manual run)."""
    user_id = int(user["id"])
    settings = get_notification_settings(user_id)
    cv_doc = get_active_cv_document(user_id)
    if not cv_doc:
        st.error(t("auto_search.no_cv"))
        return

    user_profile = get_user_by_id(user_id) or user
    depth_key = settings.get("auto_search_depth", "standard")
    if depth_key not in ANALYSIS_DEPTH_POOL:
        depth_key = "standard"
    provider = settings.get("auto_search_provider") or job_provider
    job_id, err = enqueue_analysis_job(
        user_id,
        user_profile,
        job_provider=provider,
        analysis_depth=depth_key,
        cv_fingerprint=str(cv_doc.get("fingerprint") or ""),
        cv_text=str(cv_doc.get("extracted_text") or ""),
        extraction_method="native",
        trigger_source="auto",
    )
    if err and err != "already":
        st.error(_enqueue_user_analysis_error(err))
        return
    kick_embedded_analysis_worker()
    log_scheduled_run(user_id, "running", trigger_source="app")
    st.session_state.analysis_job_id = job_id
    st.session_state.applied_analysis_job_id = None
    st.session_state.analysis = None
    st.rerun()



def render_cv_profile_summary(criteria: dict[str, Any], user_profile: dict[str, Any]) -> None:
    """Display enriched CV profile and user matching preferences."""
    st.markdown(
        f'<p class="section-title">{t("cvprofile.title")}</p>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("cvprofile.target_role"), user_profile.get("target_job_title") or criteria.get("metier", "—"))
        cv_metier = criteria.get("metier", "")
        if cv_metier and cv_metier != user_profile.get("target_job_title"):
            c1.caption(t("cvprofile.detected_cv", value=cv_metier))
        cv_level = criteria.get("niveau_experience", "—")
        profile_level = user_profile.get("experience_level", "confirme")
        c2.metric(
            t("cvprofile.level"),
            experience_label(profile_level)
            if profile_level != "tous"
            else t("cvprofile.cv_level", level=cv_level),
        )
        c3.metric(t("cvprofile.contract"), user_profile.get("contract_type", "—"))
        region_text, dept_text, city_text = format_profile_geo_summary(user_profile)
        zone_label = region_text
        if city_text != "—":
            zone_label = city_text if len(profile_countries(user_profile)) > 1 else (
                city_text if city_text != "—" else dept_text
            )
        c4.metric(t("cvprofile.zone"), zone_label if zone_label != "—" else dept_text)

        profile_sectors = user_profile.get("target_sectors") or []
        cv_sectors = criteria.get("secteurs") or []
        active_sectors = profile_sectors or cv_sectors
        if active_sectors:
            st.caption(f"**{t('cvprofile.sectors')} :** " + ", ".join(active_sectors))

        geo_mode = user_profile.get("geo_filter_mode", "departement")
        geo_labels = {
            "ville": geo_mode_label("ville"),
            "departement": geo_mode_label("departement", register=True),
            "rayon": t(
                "cvprofile.geo_rayon",
                radius=user_profile.get("search_radius_km", 20),
            ),
        }
        countries_label = format_countries_summary(user_profile)
        st.caption(
            t(
                "cvprofile.geo_filter_line",
                mode=geo_labels.get(geo_mode, "—"),
                countries=countries_label,
                regions=region_text,
                depts=dept_text,
                cities=city_text,
            )
        )

        tech = criteria.get("competences_techniques") or criteria.get("mots_cles") or []
        soft = criteria.get("soft_skills") or []
        if tech:
            st.markdown(f"**{t('cvprofile.tech_skills')} :** " + " · ".join(f"`{kw}`" for kw in tech))
        if soft:
            st.markdown(f"**{t('cvprofile.soft_skills')} :** " + " · ".join(f"`{kw}`" for kw in soft))
        outils = criteria.get("outils") or []
        langages = criteria.get("langages") or []
        if outils:
            st.markdown(f"**{t('cvprofile.tools')} :** " + " · ".join(f"`{o}`" for o in outils))
        if langages:
            st.markdown(f"**{t('cvprofile.languages')} :** " + " · ".join(f"`{l}`" for l in langages))

        col_a, col_b = st.columns(2)
        with col_a:
            diplomes = criteria.get("diplomes_certifications") or []
            if diplomes:
                st.markdown(f"**{t('cvprofile.degrees')}**")
                for item in diplomes:
                    st.write(f"- {item}")
            secteurs = criteria.get("secteurs") or []
            if secteurs:
                st.markdown(f"**{t('cvprofile.sectors')} :** " + ", ".join(secteurs))
        with col_b:
            experiences = criteria.get("experiences") or []
            if experiences:
                st.markdown(f"**{t('cvprofile.experiences')}**")
                for exp in experiences[:4]:
                    if isinstance(exp, dict):
                        line = (
                            f"- {exp.get('poste', '—')} · {exp.get('entreprise', '—')} "
                            f"({exp.get('duree', '—')})"
                        )
                        if exp.get("missions"):
                            line += f" — {exp['missions'][:120]}"
                        st.write(line)
            if criteria.get("mobilite_geographique"):
                st.markdown(f"**{t('cvprofile.mobility')} :** {criteria['mobilite_geographique']}")
            if criteria.get("disponibilites"):
                st.markdown(f"**{t('cvprofile.availability')} :** {criteria['disponibilites']}")


def render_analysis_results(analysis: dict[str, Any]) -> None:
    """Show the N best ranked offers requested by the selected depth."""
    results = cap_results_to_requested_best(list(analysis.get("results") or []), analysis)
    analysis_id = analysis.get("analysis_id")
    if analysis_id:
        st.session_state.dashboard_analysis_select = int(analysis_id)

    st.success(
        t(
            "results.simple_summary",
            jobs=analysis.get("jobs_found", len(results)),
            top=len(results),
        )
    )
    st.caption(t("results.simple_hint"))

    dash_col, pdf_col = st.columns([2, 1])
    with dash_col:
        if st.button(
            t("results.open_dashboard"),
            type="primary",
            use_container_width=True,
            key="analysis_open_dashboard",
        ):
            if analysis_id:
                st.session_state.dashboard_analysis_select = int(analysis_id)
            _request_navigation("dashboard")
    with pdf_col:
        extraction_method = analysis.get("extraction_method") or "native"
        method_label = (
            t("results.extraction_native")
            if extraction_method == "native"
            else t("results.extraction_ocr")
        )
        try:
            if not analysis.get("report_pdf"):
                analysis["report_pdf"] = generate_matching_report_pdf(
                    analysis.get("criteria") or {},
                    results,
                    method_label,
                )
            st.download_button(
                label=t("results.download_pdf"),
                data=analysis["report_pdf"],
                file_name="rapport_matching_dowsonbost.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="download_matching_report",
            )
        except Exception as exc:  # noqa: BLE001
            st.error(t("results.pdf_error", error=exc))

    st.markdown(
        f'<p class="section-title">{t("results.simple_title", count=len(results))}</p>',
        unsafe_allow_html=True,
    )
    for idx, entry in enumerate(results, start=1):
        render_simple_job_row(entry.get("job") or {}, entry.get("match") or {}, idx)


# ---------------------------------------------------------------------------
# Authentication UI
# ---------------------------------------------------------------------------


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "pdf_fingerprint" not in st.session_state:
        st.session_state.pdf_fingerprint = None
    if "active_llm_provider" not in st.session_state:
        st.session_state.active_llm_provider = "—"
    if "gemini_fallback_warned" not in st.session_state:
        st.session_state.gemini_fallback_warned = False
    if "analysis_notices" not in st.session_state:
        st.session_state.analysis_notices = []
    if "analysis_job_id" not in st.session_state:
        st.session_state.analysis_job_id = None
    if "applied_analysis_job_id" not in st.session_state:
        st.session_state.applied_analysis_job_id = None
    if "auth_view" not in st.session_state:
        st.session_state.auth_view = "login"
    if "groq_quota_exhausted" not in st.session_state:
        st.session_state.groq_quota_exhausted = False
    if "llm_backend_active" not in st.session_state:
        st.session_state.llm_backend_active = None
    init_locale()
    if st.session_state.get("main_navigation") not in NAV_PAGE_KEYS:
        st.session_state.main_navigation = NAV_PAGE_KEYS[0]


def _apply_pending_navigation() -> None:
    """Apply programmatic navigation before the sidebar radio is rendered."""
    pending = st.session_state.pop("_pending_navigation", None)
    try:
        nav_q = st.query_params.get("nav")
    except Exception:
        nav_q = None
    if isinstance(nav_q, list):
        nav_q = nav_q[0] if nav_q else None
    if nav_q in NAV_PAGE_KEYS:
        st.session_state.main_navigation = nav_q
        try:
            del st.query_params["nav"]
        except Exception:
            pass
        return
    if pending in NAV_PAGE_KEYS:
        st.session_state.main_navigation = pending


def _request_navigation(page: str) -> None:
    """Navigate to another main page on the next rerun."""
    if page in NAV_PAGE_KEYS:
        st.session_state["_pending_navigation"] = page
        st.rerun()


def render_language_selector(
    *,
    key_prefix: str = "locale",
    persist_user: bool = False,
    label_visibility: str = "visible",
) -> None:
    """Language picker — visible on login page and in the sidebar."""
    current = get_locale()
    try:
        current_index = SUPPORTED_LOCALES.index(current)
    except ValueError:
        current_index = 0
    selected = st.selectbox(
        t("language.label"),
        SUPPORTED_LOCALES,
        index=current_index,
        format_func=lambda code: LOCALE_LABELS.get(code, code),
        key=f"{key_prefix}_select",
        label_visibility=label_visibility,
    )
    if selected != st.session_state.get("locale"):
        set_locale(selected)
        if persist_user and st.session_state.get("authenticated") and st.session_state.get("user"):
            user = st.session_state.user
            ok, _, updated = update_user_preferred_language(int(user["id"]), selected)
            if ok and updated:
                st.session_state.user = updated
        st.rerun()


def _flush_analysis_notices() -> None:
    """Display one-shot analysis notices without leaving stale DOM nodes."""
    for notice in st.session_state.get("analysis_notices", []):
        level = notice.get("level", "info")
        text = notice.get("text", "")
        if not text:
            continue
        if level == "warning":
            st.warning(text)
        elif level == "error":
            st.error(text)
        elif level == "success":
            st.success(text)
        else:
            st.info(text)
    st.session_state.analysis_notices = []


def run_cv_analysis_pipeline(
    pdf_bytes: bytes | None,
    job_provider: str,
    user_profile: dict[str, Any],
    *,
    matching_pool: int | None = None,
    matching_top: int | None = None,
    cv_text_override: str | None = None,
    extraction_method_override: str = "native",
    search_refresh_key: str = "",
    progress: ProgressReporter | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Run the CV analysis pipeline without mutating the Streamlit DOM."""
    notices: list[dict[str, str]] = []
    pool_size = matching_pool or MATCHING_CANDIDATE_POOL
    top_n = matching_top or TOP_MATCHING_JOBS

    _report_progress(progress, 2, t("analysis.progress.init"))

    target_title = str(user_profile.get("target_job_title", "")).strip()
    if not target_title:
        notices.append(
            {
                "level": "warning",
                "text": "Poste visé manquant — renseignez-le dans **Mon profil** avant l'analyse.",
            }
        )
        return None, notices

    if not cv_text_override and not pdf_bytes:
        notices.append(
            {
                "level": "warning",
                "text": "CV manquant — déposez un PDF ou enregistrez un CV actif pour la recherche automatique.",
            }
        )
        return None, notices

    _report_progress(progress, 8, t("analysis.progress.extract"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        plan_future = executor.submit(cached_build_job_search_plan, target_title)
        if cv_text_override:
            search_plan = plan_future.result()
            cv_text, method = cv_text_override, extraction_method_override
        else:
            cv_future = executor.submit(extract_cv_text, pdf_bytes or b"")
            search_plan = plan_future.result()
            cv_text, method = cv_future.result()

    _report_progress(progress, 22, t("analysis.progress.search"))

    query = search_plan.get("query_recherche") or target_title
    metier = search_plan.get("metier") or target_title
    alternate_queries = tuple(search_plan.get("variantes") or ())
    country = user_profile.get("country", "France")
    contract_type = user_profile.get("contract_type", "CDI")
    profile_json = json.dumps(user_profile, ensure_ascii=False, sort_keys=True)

    notices.append(
        {
            "level": "info",
            "text": (
                f"Poste visé : **{target_title}** — l'IA recherche des offres "
                f"correspondantes ou proches (`{query}`)."
            ),
        }
    )
    notices.append(
        {
            "level": "info",
            "text": (
                f"Filtre publication : **{job_max_age_label(user_profile.get('job_max_age_days', 7))}**."
            ),
        }
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        search_future = executor.submit(
            cached_search_jobs,
            job_provider,
            query,
            country,
            profile_json,
            metier,
            contract_type=contract_type,
            alternate_queries=alternate_queries,
            refresh_key=search_refresh_key,
        )
        criteria_future = executor.submit(cached_extract_criteria, cv_text)
        search_result = search_future.result()
        criteria = criteria_future.result()

    _report_progress(progress, 48, t("analysis.progress.filter"))

    raw_jobs = search_result["jobs"]
    if method == "ocr":
        notices.append({"level": "warning", "text": t("pipeline.ocr_detected")})

    if criteria.get("_heuristic"):
        notices.append({"level": "warning", "text": t("pipeline.heuristic")})

    keywords = criteria.get("mots_cles") or criteria.get("competences_techniques") or []
    jobs, filter_stats = apply_strict_job_filters(
        raw_jobs,
        user_profile,
        cv_profile=criteria,
        min_keep=top_n,
    )
    _report_progress(
        progress,
        58,
        t("pipeline.filter_done", kept=len(jobs), total=len(raw_jobs)),
    )

    providers_used = search_result.get("providers_used") or [job_provider]
    if len(providers_used) > 1:
        sources = ", ".join(job_provider_label(p) for p in providers_used)
        source_text = t("pipeline.engines_multi", names=sources)
    else:
        source_text = t(
            "pipeline.engine_single",
            name=job_provider_label(providers_used[0]),
        )

    profile_locations = search_result.get("profile_locations") or build_profile_search_locations(
        user_profile
    )
    zone_preview = ", ".join(profile_locations[:3])
    if len(profile_locations) > 3:
        zone_preview += "…"

    notices.append(
        {
            "level": "info",
            "text": t(
                "pipeline.search_targeted",
                country=country,
                zones=zone_preview,
                source=source_text,
            ),
        }
    )

    if not raw_jobs:
        notices.append({"level": "warning", "text": t("pipeline.no_raw_jobs")})
        notices.append(
            {
                "level": "info",
                "text": t(
                    "pipeline.query_tested",
                    query=search_result.get("query_used", query),
                    location=search_result.get("location_used", f"tout {country}"),
                ),
            }
        )
        return None, notices

    if not jobs:
        level_label = experience_label(
            resolve_experience_level(user_profile, criteria)
        )
        hint = format_filter_rejection_hint(filter_stats, user_profile)
        notices.append(
            {
                "level": "warning",
                "text": t(
                    "pipeline.no_filtered",
                    contract=user_profile.get("contract_type"),
                    level=level_label,
                    mode=user_profile.get("geo_filter_mode"),
                ),
            }
        )
        notices.append({"level": "info", "text": t("pipeline.main_block", hint=hint)})
        notices.append(
            {
                "level": "info",
                "text": t(
                    "pipeline.rejection_stats",
                    total=filter_stats.get("total", 0),
                    contract=filter_stats.get("rejected_contract", 0),
                    geo=filter_stats.get("rejected_geo", 0),
                    experience=filter_stats.get("rejected_experience", 0),
                    sector=filter_stats.get("rejected_sector", 0),
                    age=filter_stats.get("rejected_publication_age", 0),
                ),
            }
        )
        return None, notices

    if search_result.get("strategy") not in (None, "Recherche précise"):
        notices.append(
            {
                "level": "info",
                "text": t(
                    "pipeline.expanded_search",
                    strategy=search_result["strategy"],
                    query=search_result.get("query_used"),
                    raw=len(raw_jobs),
                    filtered=len(jobs),
                ),
            }
        )

    backfilled = int(filter_stats.get("backfilled_older") or 0)
    kept_strict = int(filter_stats.get("kept_strict") or 0)
    if backfilled:
        notices.append(
            {
                "level": "info",
                "text": t(
                    "pipeline.filter_backfill",
                    age=job_max_age_label(user_profile.get("job_max_age_days", 7)),
                    strict=kept_strict,
                    added=backfilled,
                    target=top_n,
                ),
            }
        )
    elif len(jobs) < top_n:
        notices.append(
            {
                "level": "info",
                "text": t(
                    "pipeline.filter_shortfall",
                    kept=len(jobs),
                    total=len(raw_jobs),
                    target=top_n,
                ),
            }
        )

    results, partial_matches = build_matching_results(
        jobs,
        cv_text,
        keywords,
        top_n=top_n,
        pool_size=pool_size,
        cv_profile=criteria,
        target_job_title=target_title,
        user_profile=user_profile,
        progress=progress,
    )
    results = cap_results_to_requested_best(results, top_n=top_n)

    _report_progress(progress, 98, t("analysis.progress.match"))

    if partial_matches:
        notices.append(
            {
                "level": "warning",
                "text": t("pipeline.degraded", count=partial_matches),
            }
        )

    notices.append(
        {
            "level": "info",
            "text": t(
                "pipeline.parallel_match",
                keys=parallel_match_summary(),
                pool=min(len(jobs), pool_size),
                results=len(results),
            ),
        }
    )

    analysis = {
        "cv_text": cv_text,
        "extraction_method": method,
        "criteria": criteria,
        "user_profile": user_profile,
        "target_job_title": target_title,
        "search_plan": search_plan,
        "filter_stats": filter_stats,
        "jobs_found": len(jobs),
        "jobs_raw": len(raw_jobs),
        "search_strategy": search_result.get("strategy"),
        "search_query_used": search_result.get("query_used"),
        "results": results,
        "job_provider": job_provider,
        "matching_top": top_n,
        "matching_pool": pool_size,
    }
    _report_progress(progress, 100, t("analysis.progress.done"))
    return analysis, notices


def format_profile_geo_summary(profile: dict[str, Any]) -> tuple[str, str, str]:
    """Return human-readable (regions/countries, subdivisions, cities) labels."""
    countries = profile_countries(profile)
    if len(countries) == 1 and countries[0] == "France":
        regions, departments = resolve_multi_geo_from_profile(profile)
        cities = resolve_selected_cities(profile)
        region_text = ", ".join(regions) if regions else "—"
        if departments:
            dept_text = ", ".join(
                format_department_label(d.get("code", ""), d.get("name", ""))
                if d.get("name")
                else str(d.get("code", ""))
                for d in departments
            )
        else:
            dept_text = "—"
        city_text = (
            "Toutes les villes (départements sélectionnés)"
            if profile_all_cities(profile)
            else (", ".join(cities) if cities else "—")
        )
        return region_text, dept_text, city_text

    region_text = format_countries_summary(profile)
    subdivision_parts: list[str] = []
    city_parts: list[str] = []
    for country in countries:
        geo = get_country_geo(profile, country)
        if country == "France":
            fr_regions, fr_departments = resolve_multi_geo_from_profile(profile)
            if fr_regions:
                subdivision_parts.append(
                    f"France: {', '.join(fr_regions[:3])}"
                    + ("…" if len(fr_regions) > 3 else "")
                )
            if fr_departments:
                dept_labels = [
                    format_department_label(d.get("code", ""), d.get("name", ""))
                    for d in fr_departments[:3]
                ]
                subdivision_parts.append(f"France (dép.): {', '.join(dept_labels)}")
            if profile_all_cities(profile):
                city_parts.append("France: toutes les villes")
            else:
                fr_cities = resolve_selected_cities(profile)
                if fr_cities:
                    city_parts.append(f"France: {', '.join(fr_cities[:4])}")
            continue

        if country_geo_all_cities(geo):
            zones = (geo.get("level1") or []) + (geo.get("level2") or [])
            if zones:
                city_parts.append(f"{country}: toutes les villes ({', '.join(zones[:3])})")
            else:
                city_parts.append(f"{country}: toutes les villes")
            continue

        level1 = geo.get("level1") or []
        level2 = geo.get("level2") or []
        cities = geo.get("cities") or []
        schema = country_geo_schema(country)
        if level1:
            label = (schema or {}).get("level1_label", "Zone")
            subdivision_parts.append(
                f"{country} ({label.lower()}): {', '.join(level1[:3])}"
                + ("…" if len(level1) > 3 else "")
            )
        if level2:
            subdivision_parts.append(f"{country} (niv. 2): {', '.join(level2[:3])}")
        if cities:
            city_parts.append(f"{country}: {', '.join(cities[:4])}")

    dept_text = " · ".join(subdivision_parts) if subdivision_parts else "—"
    city_text = " · ".join(city_parts) if city_parts else "—"
    return region_text, dept_text, city_text


def render_countries_multiselect(
    profile: dict[str, Any],
    key_prefix: str,
) -> list[str]:
    """ISO 3166-1 multi-select for job search countries."""
    initial = profile_countries(profile)
    countries_key = f"{key_prefix}_selected_countries"
    if countries_key not in st.session_state:
        st.session_state[countries_key] = initial

    selected = st.multiselect(
        t("profile.countries"),
        list(COUNTRY_OPTIONS),
        key=countries_key,
        help=t("profile.countries_help"),
    )
    return selected if selected else ["France"]


def render_international_city_selector(
    country: str,
    profile: dict[str, Any],
    key_prefix: str,
    level1: list[str],
    level2: list[str],
    geo: dict[str, Any],
) -> tuple[list[str], bool]:
    """Multiselect of cities for international countries (same UX as France)."""
    cities_key = f"{key_prefix}_intl_cities_{country}"
    all_cities_key = f"{key_prefix}_intl_all_cities_{country}"
    zones_key = f"{key_prefix}_intl_zones_sig_{country}"
    schema = country_geo_schema(country)

    if all_cities_key not in st.session_state:
        st.session_state[all_cities_key] = country_geo_all_cities(geo)

    requires_zone = bool(schema)
    has_zone = bool(level1 or level2)

    if requires_zone and not has_zone:
        st.checkbox(
            "Toutes les villes des zones sélectionnées",
            value=False,
            disabled=True,
            key=all_cities_key,
        )
        st.multiselect(
            "Villes ciblées pour les offres",
            [],
            disabled=True,
            help=(
                f"Sélectionnez d'abord au moins un(e) "
                f"{(schema or {}).get('level1_label', 'zone').lower()}."
            ),
        )
        return [], False

    zone_sig = (tuple(sorted(level1)), tuple(sorted(level2)))
    initial_cities = country_geo_cities(geo)

    with st.spinner("Chargement des villes…"):
        available = city_options_for_country_zone(country, level1, level2)

    if cities_key not in st.session_state:
        st.session_state[cities_key] = labels_for_selected_intl_cities(
            initial_cities, level1, level2, available
        )

    if st.session_state.get(zones_key) != zone_sig:
        previous = st.session_state.get(cities_key, [])
        st.session_state[cities_key] = [label for label in previous if label in available]
        st.session_state[zones_key] = zone_sig

    zone_label = (schema or {}).get("level2_label") or (schema or {}).get("level1_label") or "zones"
    all_cities = st.checkbox(
        f"Toutes les villes des {zone_label.lower()} sélectionnées"
        if requires_zone and has_zone
        else "Toutes les villes du pays",
        key=all_cities_key,
        help=(
            "Accepte toute offre située dans vos zones sélectionnées, "
            "sans filtrer par nom de ville."
        ),
    )

    if not available:
        st.warning(t("geo.cities_unavailable"))
        return initial_cities, all_cities

    if all_cities:
        st.caption(f"**{len(available)}** ville(s) couverte(s) dans la zone sélectionnée.")
        st.multiselect(
            "Villes ciblées pour les offres",
            available,
            default=[],
            disabled=True,
            help="Décochez « Toutes les villes » pour choisir des villes précises.",
        )
        return [], True

    selected_labels = st.multiselect(
        "Villes ciblées pour les offres",
        available,
        key=cities_key,
        help=(
            f"{len(available)} ville(s) disponible(s). "
            "Choisissez une ou plusieurs villes, ou cochez « Toutes les villes »."
        ),
    )
    return [parse_intl_city_option(label) for label in selected_labels], False


def render_international_geo_selectors(
    country: str,
    profile: dict[str, Any],
    key_prefix: str,
) -> dict[str, Any]:
    """Adaptive region/state/city selectors for non-France countries."""
    geo = get_country_geo(profile, country)
    schema = country_geo_schema(country)
    result: dict[str, Any] = {
        "level1": [],
        "level2": [],
        "cities": [],
        "all_cities": False,
    }

    if not schema:
        cities, all_cities = render_international_city_selector(
            country,
            profile,
            key_prefix,
            [],
            [],
            geo,
        )
        result["cities"] = cities
        result["all_cities"] = all_cities
        return result

    level1_options = schema.get("level1_options") or []
    if level1_options:
        level1_key = f"{key_prefix}_l1_{country}"
        if level1_key not in st.session_state:
            st.session_state[level1_key] = [
                item for item in (geo.get("level1") or []) if item in level1_options
            ]
        result["level1"] = st.multiselect(
            schema.get("level1_label", "Région"),
            level1_options,
            key=level1_key,
            help=f"Sélectionnez une ou plusieurs {schema.get('level1_label', 'zones').lower()}.",
        )

    if schema.get("level2_label"):
        level2_label = schema["level2_label"]
        level2_key = f"{key_prefix}_l2_{country}"
        level2_options = schema.get("level2_options") or []
        if level2_options:
            if level2_key not in st.session_state:
                st.session_state[level2_key] = [
                    item for item in (geo.get("level2") or []) if item in level2_options
                ]
            result["level2"] = st.multiselect(
                level2_label,
                level2_options,
                key=level2_key,
                help=f"Sélectionnez un ou plusieurs {level2_label.lower()}.",
            )
        else:
            level2_raw = st.text_input(
                level2_label,
                value=", ".join(geo.get("level2") or []),
                key=level2_key,
                help=f"Saisie libre — {level2_label.lower()}, séparés par des virgules.",
            )
            result["level2"] = [
                item.strip() for item in level2_raw.split(",") if item.strip()
            ]

    cities, all_cities = render_international_city_selector(
        country,
        profile,
        key_prefix,
        result["level1"],
        result["level2"],
        geo,
    )
    result["cities"] = cities
    result["all_cities"] = all_cities
    return result


def render_region_department_selectors(
    profile: dict[str, Any],
    key_prefix: str,
) -> tuple[list[str], list[dict[str, str]]]:
    """Multi-select region and department selectors."""
    regions_all = get_region_names()
    initial_regions, initial_depts = resolve_multi_geo_from_profile(profile)
    initial_regions = [r for r in initial_regions if r in regions_all]

    regions_key = f"{key_prefix}_admin_regions"
    depts_key = f"{key_prefix}_department_labels"
    last_regions_key = f"{key_prefix}_last_admin_regions"

    if regions_key not in st.session_state:
        st.session_state[regions_key] = initial_regions

    selected_regions = st.multiselect(
        "Régions",
        regions_all,
        key=regions_key,
        help="Sélectionnez une ou plusieurs régions.",
    )

    available_labels = department_labels_for_regions(selected_regions)

    if st.session_state.get(last_regions_key) != tuple(selected_regions):
        previous = st.session_state.get(depts_key, [])
        st.session_state[depts_key] = [label for label in previous if label in available_labels]
        st.session_state[last_regions_key] = tuple(selected_regions)

    if depts_key not in st.session_state:
        seed_regions = selected_regions or initial_regions
        initial_labels = labels_for_selected_departments(initial_depts, seed_regions)
        st.session_state[depts_key] = [
            label for label in initial_labels if label in available_labels
        ]

    selected_labels = st.multiselect(
        "Départements",
        available_labels,
        key=depts_key,
        disabled=not available_labels,
        help="Sélectionnez un ou plusieurs départements parmi les régions choisies.",
    )

    departments = [
        department_from_multiselect_label(label) for label in selected_labels
    ]
    return selected_regions, departments


def render_city_selector(
    profile: dict[str, Any],
    key_prefix: str,
    selected_departments: list[dict[str, str]],
    country: str = "France",
) -> tuple[list[str], bool]:
    """Multiselect of communes filtered by selected departments."""
    cities_key = f"{key_prefix}_selected_cities"
    last_depts_key = f"{key_prefix}_last_departments_for_cities"
    all_cities_key = f"{key_prefix}_all_cities"

    if all_cities_key not in st.session_state:
        st.session_state[all_cities_key] = profile_all_cities(profile)

    if not communes_supported_for_country(country):
        st.multiselect(
            "Villes ciblées pour les offres",
            resolve_selected_cities(profile),
            disabled=True,
            help="La liste déroulante des communes est disponible pour la France.",
        )
        return resolve_selected_cities(profile), False

    if not selected_departments:
        st.checkbox(
            "Toutes les villes des départements sélectionnés",
            value=False,
            disabled=True,
            key=all_cities_key,
        )
        st.multiselect(
            "Villes ciblées pour les offres",
            [],
            disabled=True,
            help="Sélectionnez d'abord au moins un département.",
        )
        return [], False

    with st.spinner("Chargement des communes…"):
        available = city_options_for_departments(selected_departments)

    dept_sig = tuple(sorted(str(d.get("code", "")).strip().upper() for d in selected_departments))
    initial_cities = resolve_selected_cities(profile)

    if cities_key not in st.session_state:
        st.session_state[cities_key] = labels_for_selected_cities(
            initial_cities, selected_departments, available
        )

    if st.session_state.get(last_depts_key) != dept_sig:
        previous = st.session_state.get(cities_key, [])
        st.session_state[cities_key] = [label for label in previous if label in available]
        st.session_state[last_depts_key] = dept_sig

    all_cities = st.checkbox(
        "Toutes les villes des départements sélectionnés",
        key=all_cities_key,
        help=(
            "Accepte toute offre située dans vos départements/régions, "
            "sans filtrer par nom de ville."
        ),
    )

    if not available:
        st.warning("Impossible de charger les communes pour ce(s) département(s).")
        return initial_cities, all_cities

    if all_cities:
        st.caption(
            f"**{len(available)}** commune(s) couvertes dans les départements sélectionnés."
        )
        st.multiselect(
            "Villes ciblées pour les offres",
            available,
            default=[],
            disabled=True,
            help="Décochez « Toutes les villes » pour choisir des communes précises.",
        )
        return [], True

    selected_labels = st.multiselect(
        "Villes ciblées pour les offres",
        available,
        key=cities_key,
        help=(
            f"{len(available)} commune(s) disponible(s). "
            "Choisissez une ou plusieurs villes, ou cochez « Toutes les villes »."
        ),
    )
    return [parse_city_option(label) for label in selected_labels], False


def _auth_time_greeting() -> tuple[str, str]:
    """Return headline and sub-greeting for the auth panel."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return t("auth.greeting.morning"), t("auth.greeting.morning_sub")
    if 12 <= hour < 18:
        return t("auth.greeting.morning"), t("auth.greeting.afternoon_sub")
    if 18 <= hour < 23:
        return t("auth.greeting.evening"), t("auth.greeting.evening_sub")
    return t("auth.greeting.evening"), t("auth.greeting.night_sub")


def _auth_illustration_svg() -> str:
    """Dusk city illustration for the left auth panel."""
    return """
<svg class="auth-illustration" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <rect width="320" height="220" fill="#155E75"/>
  <circle cx="248" cy="52" r="34" fill="#E8B923"/>
  <ellipse cx="210" cy="58" rx="38" ry="18" fill="#0E7490"/>
  <ellipse cx="255" cy="62" rx="30" ry="14" fill="#0E7490"/>
  <path d="M0 150 Q80 120 160 145 T320 138 L320 220 L0 220 Z" fill="#0B4A5C"/>
  <path d="M0 170 Q90 145 180 168 T320 158 L320 220 L0 220 Z" fill="#0E7490"/>
  <path d="M0 188 Q100 165 200 185 T320 176 L320 220 L0 220 Z" fill="#124E5E"/>
  <line x1="40" y1="28" x2="58" y2="8" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <line x1="120" y1="18" x2="128" y2="2" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <line x1="180" y1="36" x2="198" y2="16" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <circle cx="90" cy="40" r="2" fill="#F4F1EA"/>
  <circle cx="150" cy="24" r="2" fill="#F4F1EA"/>
  <circle cx="200" cy="30" r="2" fill="#F4F1EA"/>
</svg>
"""


def _auth_left_panel_html() -> str:
    """Decorative left column for the auth card."""
    return f"""
<div class="auth-left-panel">
  <div class="auth-illustration-wrap">
    {_auth_illustration_svg()}
  </div>
  <p class="auth-left-title">
    {html.escape(t("auth.left.title", app_name=APP_NAME))}
  </p>
  <p class="auth-left-tip">
    {html.escape(t("auth.left.tip"))}
  </p>
</div>
"""


def _render_auth_language_bar() -> None:
    """Quiet language control, top-right of the login card."""
    st.markdown('<div class="auth-lang-bar-marker"></div>', unsafe_allow_html=True)
    render_language_selector(
        key_prefix="auth_top_locale",
        label_visibility="collapsed",
    )


def _render_account_deleted_notice() -> None:
    if st.session_state.get("account_deleted_notice"):
        st.success(t("auth.account.deleted"))


def _render_auth_login_form() -> None:
    """Login form stacked like a 2026 sign-in card."""
    _render_account_deleted_notice()
    headline, sub = _auth_time_greeting()
    st.markdown(
        f'<p class="auth-greeting-main">{html.escape(headline)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="auth-greeting-sub">{html.escape(sub)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="auth-form-title">{html.escape(t("auth.login.title"))}</p>',
        unsafe_allow_html=True,
    )
    st.text_input(t("common.email"), placeholder=t("placeholder.email"), key="login_email")
    st.text_input(
        t("common.password"),
        type="password",
        placeholder=t("placeholder.password"),
        key="login_password",
    )
    st.markdown('<div class="auth-forgot-row-marker"></div>', unsafe_allow_html=True)
    if st.button(t("auth.login.forgot"), key="auth_go_reset"):
        _clear_auth_reset_flow()
        st.session_state.auth_view = "reset"
        st.rerun()
    if st.button(
        t("auth.login.submit"),
        type="primary",
        use_container_width=True,
        key="auth_login_submit",
    ):
        ok, message, user = authenticate_user(
            st.session_state.get("login_email", ""),
            st.session_state.get("login_password", ""),
        )
        if ok and user:
            login_locale = get_locale()
            ok_lang, _, updated = update_user_preferred_language(
                int(user["id"]), login_locale
            )
            st.session_state.authenticated = True
            st.session_state.user = (
                updated
                if ok_lang and updated
                else {**user, "preferred_language": login_locale}
            )
            set_locale(login_locale)
            st.session_state.auth_view = "login"
            st.session_state.pop("account_deleted_notice", None)
            st.session_state.pop("prefill_register_email", None)
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.markdown('<div class="auth-signup-row-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="auth-no-account">{html.escape(t("auth.footer.no_account"))}</p>',
        unsafe_allow_html=True,
    )
    if st.button(t("auth.footer.create"), key="auth_go_register"):
        st.session_state.auth_view = "register"
        _reset_register_wizard()
        st.rerun()


def _clear_auth_reset_flow(*, keep_identity: bool = False) -> None:
    for key in (
        "reset_step",
        "reset_verified_user_id",
        "reset_code_expires_at",
        "reset_code",
        "reset_password_1",
        "reset_password_2",
    ):
        st.session_state.pop(key, None)
    if not keep_identity:
        for key in (
            "reset_email",
            "reset_full_name",
            "reset_identity_email",
            "reset_identity_name",
        ):
            st.session_state.pop(key, None)


def _store_reset_identity() -> None:
    """Keep e-mail/name after Streamlit drops the identify widgets on the next step."""
    email = str(
        st.session_state.get("reset_email")
        or st.session_state.get("reset_identity_email")
        or ""
    )
    name = str(
        st.session_state.get("reset_full_name")
        or st.session_state.get("reset_identity_name")
        or ""
    )
    st.session_state.reset_identity_email = email
    st.session_state.reset_identity_name = name


def _reset_identity_email() -> str:
    return str(st.session_state.get("reset_identity_email") or st.session_state.get("reset_email") or "")


def _reset_identity_name() -> str:
    return str(st.session_state.get("reset_identity_name") or st.session_state.get("reset_full_name") or "")


def _render_auth_reset_form() -> None:
    """Password reset: identity → e-mailed 8-character code → new password."""
    step = str(st.session_state.get("reset_step") or "identify")
    verified_user_id = int(st.session_state.get("reset_verified_user_id") or 0)
    if step not in {"identify", "code", "password"}:
        step = "identify"
        st.session_state.reset_step = "identify"
    if step == "password" and verified_user_id <= 0:
        step = "code"
        st.session_state.reset_step = "code"

    st.markdown(f'<p class="auth-greeting-main">{html.escape(t("auth.reset.title"))}</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="auth-greeting-sub">{html.escape(t("auth.reset.subtitle"))}</p>',
        unsafe_allow_html=True,
    )
    if step == "identify":
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.reset.form_title"))}</p>',
            unsafe_allow_html=True,
        )
        st.text_input(t("common.email"), placeholder=t("placeholder.email"), key="reset_email")
        st.text_input(t("common.full_name"), placeholder=t("placeholder.name"), key="reset_full_name")
        if st.button(
            t("auth.reset.send_code"),
            type="primary",
            use_container_width=True,
            key="reset_send_code",
        ):
            ok, message, expires_at = request_password_reset_code(
                st.session_state.get("reset_email", ""),
                st.session_state.get("reset_full_name", ""),
            )
            if ok:
                _store_reset_identity()
                st.session_state.reset_step = "code"
                st.session_state.reset_code_expires_at = expires_at
                st.session_state.pop("reset_code", None)
                st.session_state.pop("reset_verified_user_id", None)
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        return

    if step == "code":
        remaining = reset_code_seconds_remaining(
            str(st.session_state.get("reset_code_expires_at") or "")
        )
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.reset.code_title"))}</p>',
            unsafe_allow_html=True,
        )
        if remaining <= 0:
            st.warning(t("auth.reset.code_expired_hint"))
        else:
            st.caption(t("auth.reset.code_ttl", seconds=remaining))
        st.text_input(
            t("auth.reset.code"),
            placeholder=t("auth.reset.code_ph"),
            max_chars=12,
            key="reset_code",
        )
        if st.button(
            t("auth.reset.verify_code"),
            type="primary",
            use_container_width=True,
            key="reset_verify_code",
        ):
            ok, message, user_id = verify_password_reset_code(
                _reset_identity_email(),
                st.session_state.get("reset_code", ""),
            )
            if ok and user_id:
                st.session_state.reset_verified_user_id = int(user_id)
                st.session_state.reset_step = "password"
                st.session_state.pop("reset_code", None)
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        if st.button(
            t("auth.reset.resend_code"),
            use_container_width=True,
            key="reset_resend_code",
        ):
            ok, message, expires_at = request_password_reset_code(
                _reset_identity_email(),
                _reset_identity_name(),
            )
            if ok:
                st.session_state.reset_code_expires_at = expires_at
                st.session_state.pop("reset_code", None)
                st.session_state.pop("reset_verified_user_id", None)
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        return

    st.markdown(
        f'<p class="auth-form-title">{html.escape(t("auth.reset.password_title"))}</p>',
        unsafe_allow_html=True,
    )
    st.text_input(
        t("auth.reset.new_password"),
        type="password",
        placeholder=t("placeholder.password_min"),
        key="reset_password_1",
    )
    st.text_input(
        t("auth.reset.confirm"),
        type="password",
        key="reset_password_2",
    )
    if st.button(
        t("auth.reset.submit"),
        type="primary",
        use_container_width=True,
        key="reset_submit_password",
    ):
        password_1 = str(st.session_state.get("reset_password_1") or "")
        password_2 = str(st.session_state.get("reset_password_2") or "")
        if password_1 != password_2:
            st.error(t("auth.register.password_mismatch"))
        else:
            ok, message = complete_verified_password_reset(verified_user_id, password_1)
            if ok:
                _clear_auth_reset_flow()
                st.session_state.auth_view = "login"
                st.success(message)
                st.rerun()
            else:
                st.error(message)


REGISTER_WIZARD_STEPS = (
    "auth.register.wizard.language",
    "auth.register.wizard.countries",
    "auth.register.wizard.identity",
    "auth.register.wizard.job",
    "auth.register.wizard.location",
    "auth.register.wizard.preferences",
)


def _reset_register_wizard() -> None:
    st.session_state.register_wizard_step = 0
    st.session_state.pop("register_draft", None)
    st.session_state.pop("register_geo_snapshot", None)


def _render_register_wizard_progress(step: int) -> None:
    parts = []
    for index, label_key in enumerate(REGISTER_WIZARD_STEPS):
        state = "done" if index < step else ("active" if index == step else "")
        parts.append(
            f'<div class="reg-wizard-step {state}">'
            f'<span class="reg-wizard-dot">{index + 1}</span>'
            f'<span class="reg-wizard-label">{html.escape(t(label_key))}</span>'
            f"</div>"
        )
    st.markdown(
        f'<div class="reg-wizard-track">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def _validate_register_wizard_step(step: int) -> tuple[bool, str]:
    if step == 1:
        countries = st.session_state.get("register_selected_countries") or []
        if not countries:
            return False, t("auth.register.countries_required")
    elif step == 2:
        first = (st.session_state.get("register_wiz_first_name") or "").strip()
        last = (st.session_state.get("register_wiz_last_name") or "").strip()
        email = (st.session_state.get("register_wiz_email") or "").strip().lower()
        password = st.session_state.get("register_wiz_password") or ""
        password2 = st.session_state.get("register_wiz_password2") or ""
        if len(first) < 2:
            return False, t("auth.register.first_name_required")
        if len(last) < 2:
            return False, t("auth.register.last_name_required")
        if not EMAIL_PATTERN.match(email):
            return False, t("auth.email.invalid")
        if password != password2:
            return False, t("auth.register.password_mismatch")
        if len(password.strip()) < 8:
            return False, t("placeholder.password_min")
    elif step == 3:
        job = (st.session_state.get("register_wiz_target_job") or "").strip()
        if len(job) < 2:
            return False, t("auth.register.job_required")
    return True, ""


def _persist_register_wizard_step(step: int, draft: dict[str, Any]) -> None:
    if step == 0:
        locale = st.session_state.get("register_wiz_locale") or get_locale()
        draft["locale"] = locale
        set_locale(locale)
    elif step == 1:
        draft["countries"] = list(
            st.session_state.get("register_selected_countries") or ["France"]
        )
    elif step == 2:
        draft["first_name"] = (st.session_state.get("register_wiz_first_name") or "").strip()
        draft["last_name"] = (st.session_state.get("register_wiz_last_name") or "").strip()
        draft["email"] = (st.session_state.get("register_wiz_email") or "").strip().lower()
        draft["phone"] = (st.session_state.get("register_wiz_phone") or "").strip()
        draft["password"] = st.session_state.get("register_wiz_password") or ""
    elif step == 3:
        draft["target_job"] = (st.session_state.get("register_wiz_target_job") or "").strip()


def _render_register_location_step(countries: list[str]) -> dict[str, Any]:
    admin_regions: list[str] = []
    departments: list[dict[str, str]] = []
    cities: list[str] = []
    all_cities = False
    geo_by_country: dict[str, dict[str, Any]] = {}

    if "France" in countries:
        with st.expander("France — régions, départements & villes", expanded=True):
            admin_regions, departments = render_region_department_selectors(
                {},
                key_prefix="register",
            )
            cities, all_cities = render_city_selector(
                {},
                key_prefix="register",
                selected_departments=departments,
                country="France",
            )

    for country in countries:
        if country == "France":
            continue
        with st.expander(
            f"{country} — {country_geo_schema(country).get('level1_label', 'zones') if country_has_subdivisions(country) else 'villes'}",
            expanded=len(countries) <= 2,
        ):
            geo_by_country[country] = render_international_geo_selectors(
                country,
                {},
                key_prefix="register",
            )

    return {
        "admin_regions": admin_regions,
        "departments": departments,
        "cities": cities,
        "all_cities": all_cities,
        "geo_by_country": geo_by_country,
    }


def _submit_register_wizard(draft: dict[str, Any]) -> None:
    geo = st.session_state.get("register_geo_snapshot") or {}
    countries = draft.get("countries") or ["France"]
    geo_mode = st.session_state.get("register_wiz_geo_mode", GEO_FILTER_MODES[1])
    full_name = f"{draft.get('first_name', '')} {draft.get('last_name', '')}".strip()

    ok, message = register_user(
        full_name,
        draft.get("email", ""),
        draft.get("password", ""),
        admin_regions=geo.get("admin_regions", []),
        selected_departments=geo.get("departments", []),
        selected_cities=geo.get("cities", []),
        all_cities=bool(geo.get("all_cities")),
        country=countries[0],
        contract_type=st.session_state.get("register_wiz_contract", CONTRACT_TYPES[0]),
        geo_filter_mode=geo_mode,
        search_radius_km=int(st.session_state.get("register_wiz_radius", 20)),
        experience_level=st.session_state.get("register_wiz_experience", EXPERIENCE_LEVELS[1]),
        target_sectors=st.session_state.get("register_target_sectors", ["Informatique"]),
        target_job_title=draft.get("target_job", ""),
        job_max_age_days=st.session_state.get("register_wiz_publication_age", 7),
        selected_countries=countries,
        geo_by_country=geo.get("geo_by_country", {}),
        preferred_language=draft.get("locale", get_locale()),
        phone=draft.get("phone", ""),
    )
    if ok:
        st.success(message)
        st.session_state.auth_view = "login"
        st.session_state.pop("account_deleted_notice", None)
        st.session_state.pop("prefill_register_email", None)
        _reset_register_wizard()
    else:
        st.error(message)


def _render_auth_register_form() -> None:
    """Multi-step registration wizard."""
    step = int(st.session_state.get("register_wizard_step", 0))
    total = len(REGISTER_WIZARD_STEPS)
    draft = st.session_state.setdefault("register_draft", {})
    pending_geo: dict[str, Any] | None = None

    st.markdown(
        f'<p class="auth-greeting-main">{html.escape(t("auth.register.welcome"))}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="auth-greeting-sub">{html.escape(t("auth.register.subtitle"))}</p>',
        unsafe_allow_html=True,
    )
    _render_account_deleted_notice()
    prefill_email = str(st.session_state.get("prefill_register_email") or "").strip()
    if prefill_email and "register_wiz_email" not in st.session_state:
        st.session_state.register_wiz_email = prefill_email
    _render_register_wizard_progress(step)

    if step == 0:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.wizard.language"))}</p>',
            unsafe_allow_html=True,
        )
        current = draft.get("locale") or get_locale()
        try:
            locale_index = SUPPORTED_LOCALES.index(current)
        except ValueError:
            locale_index = 0
        st.selectbox(
            t("language.label"),
            SUPPORTED_LOCALES,
            index=locale_index,
            format_func=lambda code: LOCALE_LABELS.get(code, code),
            key="register_wiz_locale",
        )
    elif step == 1:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.wizard.countries"))}</p>',
            unsafe_allow_html=True,
        )
        render_countries_multiselect({}, key_prefix="register")
    elif step == 2:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.wizard.identity"))}</p>',
            unsafe_allow_html=True,
        )
        st.caption(t("auth.register.wizard.identity_hint"))
        name_col1, name_col2 = st.columns(2)
        with name_col1:
            st.text_input(
                t("common.first_name"),
                key="register_wiz_first_name",
                placeholder="Jean",
            )
        with name_col2:
            st.text_input(
                t("common.last_name"),
                key="register_wiz_last_name",
                placeholder="Dupont",
            )
        st.text_input(
            t("common.email"),
            key="register_wiz_email",
            placeholder=t("placeholder.email"),
        )
        st.text_input(
            t("common.phone"),
            key="register_wiz_phone",
            placeholder="+33 6 12 34 56 78",
        )
        st.text_input(
            t("common.password"),
            type="password",
            key="register_wiz_password",
            placeholder=t("placeholder.password_min"),
        )
        st.text_input(
            t("auth.register.password_confirm"),
            type="password",
            key="register_wiz_password2",
        )
    elif step == 3:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.step1"))}</p>',
            unsafe_allow_html=True,
        )
        st.text_input(
            t("auth.register.job_title"),
            key="register_wiz_target_job",
            placeholder=t("auth.register.job_title_ph"),
            help=t("auth.register.job_title_help"),
        )
    elif step == 4:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.step2"))}</p>',
            unsafe_allow_html=True,
        )
        countries = draft.get("countries") or st.session_state.get("register_selected_countries") or ["France"]
        st.markdown(
            f"**{html.escape(t('auth.register.location'))}** — {html.escape(', '.join(countries))}"
        )
        pending_geo = _render_register_location_step(countries)
    elif step == 5:
        st.markdown(
            f'<p class="auth-form-title">{html.escape(t("auth.register.prefs"))}</p>',
            unsafe_allow_html=True,
        )
        st.selectbox(
            t("auth.register.contract"),
            CONTRACT_TYPES,
            index=0,
            key="register_wiz_contract",
        )
        st.selectbox(
            t("auth.register.experience"),
            EXPERIENCE_LEVELS,
            index=1,
            format_func=experience_label,
            key="register_wiz_experience",
        )
        geo_mode = st.selectbox(
            t("auth.register.geo_mode"),
            GEO_FILTER_MODES,
            index=1,
            format_func=lambda value: geo_mode_label(value, register=True),
            key="register_wiz_geo_mode",
        )
        st.slider(
            t("auth.register.radius"),
            5,
            100,
            20,
            disabled=(geo_mode != "rayon"),
            key="register_wiz_radius",
        )
        st.multiselect(
            t("auth.register.sectors"),
            SECTOR_OPTIONS,
            default=["Informatique"],
            key="register_target_sectors",
        )
        st.radio(
            t("auth.register.publication"),
            JOB_MAX_AGE_DAYS_OPTIONS,
            index=JOB_MAX_AGE_DAYS_OPTIONS.index(7),
            format_func=job_age_label,
            help=t("auth.register.publication_help"),
            key="register_wiz_publication_age",
            horizontal=True,
        )

    st.markdown('<div class="reg-wizard-nav">', unsafe_allow_html=True)
    _nav_sp_l, nav_back, nav_next, _nav_sp_r = st.columns([1.25, 1.05, 1.05, 1.25])
    with nav_back:
        if step > 0:
            if st.button(
                t("auth.register.back"),
                use_container_width=True,
                key="register_wizard_back",
            ):
                st.session_state.register_wizard_step = step - 1
                st.rerun()
        elif st.button(
            t("auth.footer.back_login"),
            use_container_width=True,
            key="auth_register_back_login",
        ):
            st.session_state.auth_view = "login"
            _reset_register_wizard()
            st.rerun()
    with nav_next:
        if step < total - 1:
            if st.button(
                t("auth.register.next"),
                type="primary",
                use_container_width=True,
                key="register_wizard_next",
            ):
                valid, error = _validate_register_wizard_step(step)
                if not valid:
                    st.error(error)
                else:
                    _persist_register_wizard_step(step, draft)
                    if step == 4 and pending_geo is not None:
                        st.session_state.register_geo_snapshot = pending_geo
                    st.session_state.register_wizard_step = step + 1
                    st.rerun()
        elif st.button(
            t("auth.register.submit"),
            type="primary",
            use_container_width=True,
            key="register_wizard_submit",
        ):
            _submit_register_wizard(draft)
    st.markdown("</div>", unsafe_allow_html=True)


def render_auth_page() -> None:
    """Split-screen login / reset, or a full-page registration wizard."""
    render_auth_styles()
    view = st.session_state.get("auth_view", "login")

    if view == "register":
        st.markdown('<div id="auth-fullpage"></div>', unsafe_allow_html=True)
        _render_auth_register_form()
        return

    _spacer_left, card_col, _spacer_right = st.columns([0.12, 1.76, 0.12])
    with card_col:
        st.markdown('<div id="auth-split-screen"></div>', unsafe_allow_html=True)
        panel_left, panel_right = st.columns([0.94, 1.06], gap="large")

        with panel_left:
            st.markdown(_auth_left_panel_html(), unsafe_allow_html=True)

        with panel_right:
            st.markdown('<div class="auth-panel-right-inner">', unsafe_allow_html=True)
            _render_auth_language_bar()
            if view == "login":
                _render_auth_login_form()
            else:
                _render_auth_reset_form()
                st.markdown('<div class="auth-back-link-marker"></div>', unsafe_allow_html=True)
                if st.button(t("auth.footer.back_login"), key="auth_go_login"):
                    st.session_state.auth_view = "login"
                    _reset_register_wizard()
                    _clear_auth_reset_flow()
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


def _reset_session_after_account_deletion(*, recreate_email: str = "") -> None:
    """Wipe in-browser session data after a successful account purge."""
    st.session_state.clear()
    st.session_state.account_deleted_notice = True
    if recreate_email:
        st.session_state.prefill_register_email = recreate_email
    init_session_state()
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.auth_view = "login"


def render_delete_account_section(user: dict[str, Any]) -> None:
    """Danger zone — delete account with confirmation."""
    user_id = int(user["id"])
    confirm_key = f"delete_account_confirm_{user_id}"

    st.markdown(
        (
            '<div class="danger-zone delete-account-zone">'
            f'<p class="danger-zone-kicker">{html.escape(t("profile.delete_kicker"))}</p>'
            '<div class="danger-zone-row">'
            '<span class="danger-zone-icon" aria-hidden="true">!</span>'
            "<div>"
            f'<p class="danger-zone-title delete-account-title">{html.escape(t("profile.delete_title"))}</p>'
            f'<p class="danger-zone-text delete-account-text">{html.escape(t("profile.delete_text"))}</p>'
            "</div></div></div>"
        ),
        unsafe_allow_html=True,
    )

    if not st.session_state.get(confirm_key):
        if st.button(
            t("profile.delete_button"),
            key=f"delete_account_btn_{user_id}",
            use_container_width=True,
        ):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        st.markdown(
            f'<p class="danger-zone-confirm">{html.escape(t("profile.delete_confirm"))}</p>',
            unsafe_allow_html=True,
        )
        yes_col, no_col = st.columns(2)
        with yes_col:
            if st.button(
                t("profile.delete_yes"),
                key=f"delete_account_yes_{user_id}",
                use_container_width=True,
            ):
                ok, message = delete_user_account(user_id)
                if ok:
                    _reset_session_after_account_deletion(
                        recreate_email=str(user.get("email") or "")
                    )
                    st.rerun()
                st.error(message)
        with no_col:
            if st.button(
                t("profile.delete_no"),
                key=f"delete_account_no_{user_id}",
                use_container_width=True,
            ):
                st.session_state.pop(confirm_key, None)
                st.rerun()


def render_connected_accounts_section(user: dict[str, Any]) -> None:
    """Let the candidate link existing job-board accounts to DowsonBost."""
    user_id = int(user["id"])
    linked = {
        row["provider"]: row for row in list_connected_job_accounts(user_id)
    }
    default_email = str(user.get("email") or "").strip()
    total_sites = len(CONNECTABLE_JOB_PROVIDERS)

    st.markdown('<div class="profile-section-card">', unsafe_allow_html=True)
    st.markdown(
        f'<p class="section-title">{html.escape(t("accounts.title"))}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="profile-section-hint">{html.escape(t("accounts.hint"))}</p>',
        unsafe_allow_html=True,
    )
    st.caption(t("accounts.summary", linked=len(linked), total=total_sites))
    if default_email:
        st.caption(t("accounts.candidate_email", email=default_email))

    for provider in CONNECTABLE_JOB_PROVIDERS:
        account = linked.get(provider)
        name = job_board_display_name(provider)
        header = (
            t("accounts.row_connected", name=name)
            if account
            else t("accounts.row_disconnected", name=name)
        )
        with st.expander(header, expanded=False):
            if account:
                st.success(
                    t(
                        "accounts.linked_as",
                        name=name,
                        email=account.get("account_email") or "—",
                    )
                )
                profile_url = str(account.get("profile_url") or "").strip()
                if profile_url:
                    st.caption(t("accounts.linked_profile", url=profile_url))
                if st.button(
                    t("accounts.disconnect"),
                    key=f"disconnect_{provider}_{user_id}",
                    use_container_width=True,
                ):
                    _ok, message = disconnect_job_account(user_id, provider)
                    st.success(message)
                    st.rerun()
            else:
                st.markdown(f"**{t('accounts.login_title', name=name)}**")
                with st.form(f"connect_form_{provider}_{user_id}", clear_on_submit=False):
                    st.text_input(
                        t("accounts.login_id", name=name),
                        value=default_email,
                        key=f"connect_email_{provider}_{user_id}",
                        help=t("accounts.login_id_help", name=name),
                    )
                    st.text_input(
                        t("accounts.login_password", name=name),
                        type="password",
                        key=f"connect_password_{provider}_{user_id}",
                        help=t("accounts.login_password_help", name=name),
                    )
                    st.text_input(
                        t("accounts.login_password_confirm", name=name),
                        type="password",
                        key=f"connect_password_confirm_{provider}_{user_id}",
                        help=t("accounts.login_password_confirm_help", name=name),
                    )
                    st.text_input(
                        t("accounts.profile_url", name=name),
                        key=f"connect_profile_url_{provider}_{user_id}",
                        help=t("accounts.profile_url_help", name=name),
                    )
                    confirmed = st.checkbox(
                        t("accounts.confirm_existing", name=name),
                        key=f"confirm_existing_{provider}_{user_id}",
                    )
                    submitted = st.form_submit_button(
                        t("accounts.connect"),
                        use_container_width=True,
                    )
                signup_url = job_board_signup_url(provider)
                if signup_url:
                    st.link_button(
                        t("accounts.create_on_site", name=name),
                        signup_url,
                        use_container_width=True,
                    )
                if st.button(
                    t("accounts.no_account"),
                    key=f"no_account_{provider}_{user_id}",
                    use_container_width=True,
                ):
                    st.error(t("accounts.not_created", name=name))
                if submitted:
                    email_value = str(
                        st.session_state.get(f"connect_email_{provider}_{user_id}")
                        or ""
                    )
                    password_value = str(
                        st.session_state.get(f"connect_password_{provider}_{user_id}")
                        or ""
                    )
                    password_confirm = str(
                        st.session_state.get(
                            f"connect_password_confirm_{provider}_{user_id}"
                        )
                        or ""
                    )
                    profile_value = str(
                        st.session_state.get(f"connect_profile_url_{provider}_{user_id}")
                        or ""
                    )
                    ok, message = connect_job_account(
                        user_id,
                        provider,
                        email_value,
                        has_existing_account=confirmed,
                        site_password=password_value,
                        site_password_confirm=password_confirm,
                        profile_url=profile_value,
                    )
                    if ok:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    st.markdown("</div>", unsafe_allow_html=True)


def _profile_header_chips(profile: dict[str, Any]) -> str:
    """Compact identity chips for the profile header."""
    chips: list[str] = []
    job_title = str(profile.get("target_job_title") or "").strip()
    if job_title:
        chips.append(job_title)
    contract = profile.get("contract_type")
    if contract:
        chips.append(contract_label(str(contract)))
    level = profile.get("experience_level")
    if level:
        chips.append(experience_label(str(level)))
    countries = format_countries_summary(profile)
    if countries:
        chips.append(countries)
    return "".join(
        f'<span class="profile-chip">{html.escape(chip)}</span>' for chip in chips if chip
    )


def _render_profile_photo_editor(user_id: int, *, has_photo: bool) -> None:
    """Let the candidate add, replace, or remove their profile photo."""
    st.markdown(f'<p class="filter-bar-title">{html.escape(t("profile.photo.title"))}</p>', unsafe_allow_html=True)
    st.caption(t("profile.photo.hint"))
    uploaded = st.file_uploader(
        t("profile.photo.upload"),
        type=["jpg", "jpeg", "png", "webp"],
        key="profile_photo_upload",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        raw = uploaded.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        if st.session_state.get("_profile_photo_digest") != digest:
            ok, reason = save_profile_photo(user_id, raw, uploaded.type or "")
            st.session_state._profile_photo_digest = digest
            clear_profile_photo_cache(st.session_state)
            if ok:
                st.success(t("profile.photo.saved"))
                st.rerun()
            if reason == "too_large":
                st.error(t("profile.photo.too_large"))
            elif reason == "empty":
                st.error(t("profile.photo.empty"))
            else:
                st.error(t("profile.photo.invalid"))
    if has_photo:
        if st.button(t("profile.photo.remove"), key="profile_photo_remove"):
            remove_profile_photo(user_id)
            st.session_state.pop("_profile_photo_digest", None)
            clear_profile_photo_cache(st.session_state)
            st.success(t("profile.photo.removed"))
            st.rerun()


def render_profile_page(user: dict[str, Any], job_provider: str) -> None:
    """Profile settings — identity, search prefs, security, alerts, delete account."""
    _flush_analysis_notices()
    profile = _cached_user_profile(user)
    current_age = normalize_job_max_age_days(profile.get("job_max_age_days"))
    member_since = profile.get("created_at", "")
    full_name = profile.get("full_name", "Utilisateur")
    profile_first, profile_last = split_full_name(full_name)
    profile_phone = profile.get("phone", "") or ""
    initials = _user_initials(full_name)
    photo_url = cached_profile_photo_data_url(int(user["id"]), st.session_state)

    phone_line = (
        f"<p>{html.escape(profile_phone)}</p>" if profile_phone else ""
    )
    member_label = html.escape(
        t(
            "profile.member_since",
            date=format_member_since(member_since) if member_since else "—",
        )
    )
    avatar_html = (
        f'<div class="profile-avatar"><img src="{photo_url}" alt="" /></div>'
        if photo_url
        else f'<div class="profile-avatar">{html.escape(initials)}</div>'
    )
    st.markdown(
        (
            '<div class="profile-header-card">'
            f"{avatar_html}"
            '<div class="profile-header-text">'
            f"<h2>{html.escape(full_name)}</h2>"
            f"<p>{html.escape(profile.get('email', '—'))}</p>"
            f"{phone_line}"
            f'<span class="profile-badge">{member_label}</span>'
            f'<div class="profile-chip-row">{_profile_header_chips(profile)}</div>'
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )
    _render_profile_photo_editor(int(user["id"]), has_photo=bool(photo_url))

    profile_section = st.radio(
        t("profile.tab_search"),
        list(PROFILE_SECTION_KEYS),
        format_func=lambda key: t(f"profile.tab_{key}"),
        horizontal=True,
        key="profile_section",
        label_visibility="collapsed",
    )

    if profile_section == "search":
        st.markdown(
            f'<p class="section-title">{html.escape(t("profile.search_section"))}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="profile-section-hint">{html.escape(t("profile.search_hint"))}</p>',
            unsafe_allow_html=True,
        )

        profile_key_prefix = f"profile_{user['id']}"
        selected_countries = render_countries_multiselect(profile, key_prefix=profile_key_prefix)

        st.markdown(
            f'<p class="filter-bar-title">{html.escape(t("profile.geo_section"))}</p>',
            unsafe_allow_html=True,
        )
        admin_regions: list[str] = []
        selected_departments: list[dict[str, str]] = []
        profile_cities: list[str] = []
        profile_all_cities = False
        geo_by_country: dict[str, dict[str, Any]] = {}

        if "France" in selected_countries:
            france_expanded = len(selected_countries) == 1
            with st.expander("France — régions, départements & villes", expanded=france_expanded):
                admin_regions, selected_departments = render_region_department_selectors(
                    profile,
                    key_prefix=profile_key_prefix,
                )
                profile_cities, profile_all_cities = render_city_selector(
                    profile,
                    key_prefix=profile_key_prefix,
                    selected_departments=selected_departments,
                    country="France",
                )

        for country in selected_countries:
            if country == "France":
                continue
            with st.expander(
                f"{country} — {country_geo_schema(country).get('level1_label', 'zones') if country_has_subdivisions(country) else 'villes'}",
                expanded=len(selected_countries) <= 2,
            ):
                geo_by_country[country] = render_international_geo_selectors(
                    country,
                    profile,
                    key_prefix=profile_key_prefix,
                )

        with st.form("profile_form"):
            st.markdown(f"**{t('profile.identity_section')}**")
            st.caption(t("profile.identity_hint"))
            name_col1, name_col2 = st.columns(2)
            with name_col1:
                profile_first_name = st.text_input(
                    t("common.first_name"),
                    value=profile_first,
                    key=f"profile_first_name_{user['id']}",
                )
            with name_col2:
                profile_last_name = st.text_input(
                    t("common.last_name"),
                    value=profile_last,
                    key=f"profile_last_name_{user['id']}",
                )
            contact_col1, contact_col2 = st.columns(2)
            with contact_col1:
                profile_phone_input = st.text_input(
                    t("common.phone"),
                    value=profile_phone,
                    placeholder="+33 6 12 34 56 78",
                    key=f"profile_phone_{user['id']}",
                )
            with contact_col2:
                st.text_input(
                    t("common.email"),
                    value=profile.get("email", ""),
                    disabled=True,
                    help=t("profile.email_readonly"),
                    key=f"profile_email_{user['id']}",
                )

            st.markdown(f"**{t('profile.search_section')}**")
            id_col1, id_col2 = st.columns(2)
            with id_col1:
                target_job_title = st.text_input(
                    t("profile.target_job"),
                    value=profile.get("target_job_title", ""),
                    help=t("profile.target_job_help"),
                )
            with id_col2:
                contract_type = st.selectbox(
                    t("profile.contract"),
                    CONTRACT_TYPES,
                    index=CONTRACT_TYPES.index(profile.get("contract_type", "CDI"))
                    if profile.get("contract_type") in CONTRACT_TYPES
                    else 0,
                    format_func=contract_label,
                )

            pref_col1, pref_col2 = st.columns(2)
            with pref_col1:
                exp_index = (
                    EXPERIENCE_LEVELS.index(profile.get("experience_level", "confirme"))
                    if profile.get("experience_level") in EXPERIENCE_LEVELS
                    else 1
                )
                experience_level = st.selectbox(
                    t("profile.experience"),
                    EXPERIENCE_LEVELS,
                    index=exp_index,
                    format_func=experience_label,
                )
                geo_mode = st.selectbox(
                    t("profile.geo_mode"),
                    GEO_FILTER_MODES,
                    index=GEO_FILTER_MODES.index(profile.get("geo_filter_mode", "departement"))
                    if profile.get("geo_filter_mode") in GEO_FILTER_MODES
                    else 1,
                    format_func=lambda mode: geo_mode_label(mode),
                )
            with pref_col2:
                current_sectors = profile.get("target_sectors") or []
                sectors_key = f"profile_sectors_{user['id']}"
                if sectors_key not in st.session_state:
                    st.session_state[sectors_key] = [
                        s for s in current_sectors if s in SECTOR_OPTIONS
                    ]
                target_sectors = st.multiselect(
                    t("profile.sectors"),
                    SECTOR_OPTIONS,
                    help=t("profile.sectors_help"),
                    key=sectors_key,
                    format_func=sector_label,
                )
                search_radius = st.slider(
                    t("profile.radius"),
                    5,
                    100,
                    int(profile.get("search_radius_km") or 20),
                    disabled=(geo_mode != "rayon"),
                )

            st.markdown(f"**{t('profile.published_since')}**")
            profile_age_index = (
                JOB_MAX_AGE_DAYS_OPTIONS.index(current_age)
                if current_age in JOB_MAX_AGE_DAYS_OPTIONS
                else JOB_MAX_AGE_DAYS_OPTIONS.index(7)
            )
            job_max_age_days = st.radio(
                t("profile.publication"),
                JOB_MAX_AGE_DAYS_OPTIONS,
                index=profile_age_index,
                format_func=job_age_label,
                horizontal=True,
                label_visibility="collapsed",
            )

            if st.form_submit_button(
                t("profile.save"),
                use_container_width=True,
                type="primary",
            ):
                first_name = profile_first_name.strip()
                last_name = profile_last_name.strip()
                if len(first_name) < 2:
                    st.error(t("auth.register.first_name_required"))
                elif len(last_name) < 2:
                    st.error(t("auth.register.last_name_required"))
                else:
                    new_name = join_full_name(first_name, last_name)
                    ok, message, updated = update_user_profile(
                        user["id"],
                        new_name,
                        profile.get("home_city", ""),
                        profile.get("postal_code", ""),
                        admin_regions,
                        selected_departments,
                        profile_cities,
                        profile_all_cities,
                        selected_countries[0],
                        contract_type,
                        geo_mode,
                        search_radius,
                        experience_level,
                        target_sectors,
                        target_job_title,
                        job_max_age_days,
                        selected_countries=selected_countries,
                        geo_by_country=geo_by_country,
                        phone=profile_phone_input.strip(),
                    )
                    if ok and updated:
                        st.session_state.user = updated
                        _clear_profile_page_caches()
                        st.session_state.pop(sectors_key, None)
                        prefix = f"profile_{user['id']}"
                        for suffix in (
                            "admin_regions",
                            "department_labels",
                            "last_admin_regions",
                            "selected_cities",
                            "last_departments_for_cities",
                            "all_cities",
                        ):
                            st.session_state.pop(f"{prefix}_{suffix}", None)
                        st.session_state.analysis_notices = [
                            {"level": "success", "text": message}
                        ]
                        st.rerun()
                    st.error(message)

    elif profile_section == "accounts":
        render_connected_accounts_section(profile)

    elif profile_section == "alerts":
        render_notification_settings(user, job_provider)

    elif profile_section == "security":
        st.markdown(
            f'<p class="section-title">{html.escape(t("profile.password_section"))}</p>',
            unsafe_allow_html=True,
        )
        with st.form("password_form"):
            current_pw = st.text_input(
                t("profile.current_password"),
                type="password",
                key=f"profile_current_password_{user['id']}",
            )
            new_pw = st.text_input(
                t("profile.new_password"),
                type="password",
                key=f"profile_new_password_{user['id']}",
            )
            new_pw2 = st.text_input(
                t("profile.confirm_password"),
                type="password",
                key=f"profile_confirm_password_{user['id']}",
            )
            if st.form_submit_button(
                t("profile.change_password"),
                use_container_width=True,
            ):
                if new_pw != new_pw2:
                    st.error(t("profile.password_mismatch"))
                else:
                    ok, message = change_password(user["id"], current_pw, new_pw)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)

        st.markdown('<hr class="profile-divider">', unsafe_allow_html=True)
        render_delete_account_section(user)


def render_cv_analysis(
    job_provider: str,
    user: dict[str, Any],
    *,
    analysis_depth: str = "standard",
) -> None:
    """CV upload and matching workflow."""
    user_profile = _cached_user_profile(user)
    latest_job = get_latest_analysis_job(int(user["id"]))
    _sync_analysis_job_into_session(int(user["id"]), latest_job)
    active_job = (
        latest_job
        if latest_job and str(latest_job.get("status") or "") in {"queued", "running"}
        else None
    )
    ready, _ = ai_setup_status()
    if not ready and not active_job:
        render_ai_setup_help()
        return

    profile_ok, profile_msg = profile_ready_for_matching(user_profile)
    if not profile_ok:
        st.warning(profile_msg)
        st.info(t("matching.profile_incomplete"))
        return

    if active_job:
        _render_analysis_job_progress(active_job)
        return

    target_title = user_profile.get("target_job_title", "—")
    active_level = resolve_experience_level(user_profile, {})
    active_sectors = resolve_target_sectors(user_profile, {})
    region_text, dept_text, city_text = format_profile_geo_summary(user_profile)
    publication_filter = normalize_job_max_age_days(user_profile.get("job_max_age_days"))
    depth_key = analysis_depth if analysis_depth in ANALYSIS_DEPTH_POOL else "standard"

    notify_settings = _cached_notification_settings(int(user["id"]))
    if is_auto_search_due(notify_settings) and notify_settings.get("auto_search_enabled"):
        st.info(t("analysis.auto_search_due"))
        if st.button(t("analysis.auto_search_run"), key="run_auto_search_now"):
            run_auto_search_for_user(user, job_provider)
            return

    with st.container(border=True):
        st.markdown(
            f'<p class="section-title">{t("analysis.upload_title")}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{t('analysis.target_job', title=target_title)}**")
        st.caption(t("analysis.upload_hint"))
        countries_label = format_countries_summary(user_profile)
        st.caption(
            t(
                "analysis.filters_active",
                age=job_max_age_label(publication_filter),
                contract=user_profile.get("contract_type"),
                countries=countries_label,
                level=experience_label(active_level),
                sectors=", ".join(active_sectors) if active_sectors else t("analysis.sectors_cv"),
                regions=region_text,
                depts=dept_text,
                cities=city_text,
                depth=analysis_depth_label(depth_key),
            )
            + f" {t('analysis.filters_editable')}"
        )

        uploaded_file = st.file_uploader(
            t("analysis.file_upload"),
            type=["pdf"],
            help=t("analysis.upload_help"),
            key="cv_pdf_uploader",
        )

        current_fp = None
        pdf_bytes = None
        if uploaded_file is not None:
            pdf_bytes = uploaded_file.read()
            current_fp = pdf_fingerprint(pdf_bytes)

        fp_matches = bool(
            st.session_state.analysis
            and current_fp
            and st.session_state.pdf_fingerprint == current_fp
        )

        if not uploaded_file:
            if st.session_state.analysis:
                pass
            else:
                st.info(
                    "Uploadez votre CV (PDF) — l'IA recherche les offres pour votre poste visé, "
                    "puis analyse la correspondance avec votre profil."
                )
        else:
            if fp_matches:
                st.info("Résultats en cache pour ce CV — relancez pour forcer une nouvelle analyse.")
            if st.button(
                t("analysis.run"),
                type="primary",
                use_container_width=True,
                key="run_full_analysis",
            ):
                job_id, err = enqueue_analysis_job(
                    int(user["id"]),
                    user_profile,
                    job_provider=job_provider,
                    analysis_depth=depth_key,
                    cv_fingerprint=current_fp or "",
                    pdf_bytes=pdf_bytes,
                    trigger_source="ui",
                )
                if err and err != "already":
                    st.session_state.analysis_notices = [
                        {"level": "error", "text": _enqueue_user_analysis_error(err)}
                    ]
                else:
                    kick_embedded_analysis_worker()
                    st.session_state.analysis_job_id = job_id
                    st.session_state.applied_analysis_job_id = None
                    st.session_state.analysis = None
                    st.session_state.pdf_fingerprint = current_fp
                st.rerun()

    if not uploaded_file:
        if st.session_state.analysis:
            _flush_analysis_notices()
            render_analysis_results(st.session_state.analysis)
        return

    if st.session_state.pop("adzuna_error_body", None):
        render_adzuna_auth_help(get_secret("ADZUNA_APP_ID"))

    _flush_analysis_notices()

    if fp_matches and st.session_state.analysis:
        render_analysis_results(st.session_state.analysis)


def render_config_tests_panel(*, show_clear_cache: bool = True, expanded: bool = False) -> None:
    """API diagnostics — shown only on the admin dashboard."""
    provider_secrets = provider_secrets_from_getter(get_secret)
    with st.expander(t("app.config_tests"), expanded=expanded):
        st.caption(f"{t('app.version')} : `{APP_VERSION}`")

        db_backend, db_message = database_status()
        if db_backend == "postgres":
            st.success(db_message)
        else:
            st.warning(db_message)

        adzuna_id = get_secret("ADZUNA_APP_ID")
        adzuna_key = get_secret("ADZUNA_APP_KEY")
        serp_configured = bool(provider_secrets["serpapi_api_key"])
        jooble_configured = bool(provider_secrets["jooble_api_key"])
        careerjet_configured = bool(provider_secrets["careerjet_api_key"])
        apify_configured = bool(provider_secrets["apify_api_token"])
        has_adzuna = bool(adzuna_id and adzuna_key)

        openai_configured = bool(get_secret("OPENAI_API_KEY"))
        groq_configured = bool(get_secret("GROQ_API_KEY"))
        gemini_configured = bool(get_secret("GEMINI_API_KEY"))
        ai_ready, ai_status = ai_setup_status()
        chain = get_llm_provider_chain()
        active = st.session_state.get(
            "active_llm_provider",
            resolve_llm_provider(),
        )

        st.markdown("**Mode IA :** sélection automatique")
        if chain:
            st.caption(
                "Ordre de bascule : "
                + " → ".join({"groq": "Groq", "gemini": "Gemini", "openai": "OpenAI"}[p] for p in chain)
            )
        st.markdown(f"**Moteur en cours :** `{active}`")

        if ai_ready:
            st.success(ai_status)
        else:
            st.error(ai_status)

        parallel_keys = collect_parallel_llm_slots(PARALLEL_MATCH_KEYS_PER_PROVIDER)
        counts = count_parallel_keys_by_provider()
        if counts["total"] > 1:
            st.success(
                f"Matching parallèle : **{counts['groq']} Groq** + "
                f"**{counts['gemini']} Gemini** "
                f"(**{min(PARALLEL_MATCH_MAX_WORKERS, counts['total'])}** offres simultanées max)."
            )
        else:
            st.caption(
                "Matching parallèle : configurez **3 clés Groq** + **3 clés Gemini** "
                "via `GROQ_API_KEY` + `GROQ_API_KEYS` et `GEMINI_API_KEY` + `GEMINI_API_KEYS`."
            )

        if groq_configured:
            fmt_ok, fmt_msg = validate_groq_api_key()
            if fmt_ok:
                st.success(f"Groq : clé présente ({fmt_msg})")
            else:
                st.error(f"Groq : {fmt_msg}")
        else:
            st.warning("Groq : clé absente — [créer ici](https://console.groq.com/keys)")

        if openai_configured:
            st.info("OpenAI : clé présente *(secours, crédits requis)*")

        if gemini_configured:
            g_status, g_msg = gemini_key_status()
            if g_status == "ok":
                st.info(f"Gemini : clé présente ({g_msg}) — secours auto")
            else:
                st.warning(f"Gemini : {g_msg}")

        if has_adzuna:
            st.caption(f"Adzuna : app_id `{adzuna_id[:4]}…`, clé {len(adzuna_key)} caractères")
        else:
            st.warning("Adzuna : identifiants incomplets")

        st.success("Welcome to the Jungle : actif *(gratuit, sans clé API)*")

        if jooble_configured:
            st.success("Jooble : clé présente")
        else:
            st.caption("Jooble : [clé gratuite](https://fr.jooble.org/api/about)")

        if careerjet_configured:
            st.success("OptionCarriere / Careerjet : clé présente")
            referer_preview = resolve_careerjet_referer(
                provider_secrets["careerjet_referer"]
            )
            ip_preview = resolve_careerjet_user_ip(
                provider_secrets["careerjet_user_ip"],
                client_ip=resolve_streamlit_client_ip(),
            )
            st.caption(
                f"Careerjet — referer `{referer_preview}` · IP `{ip_preview}`. "
                "Le referer doit être l'URL exacte enregistrée sur le portail partenaire."
            )
        else:
            st.caption(
                "OptionCarriere : [clé gratuite](https://www.optioncarriere.com/partners/api)"
            )

        if apify_configured:
            st.success(
                "Apify : token présent "
                "*(JobTeaser, HelloWork, Monster, Talent.com)*"
            )
        else:
            st.caption(
                "Apify : token requis pour JobTeaser, HelloWork, Monster, Talent.com "
                "— [apify.com](https://apify.com/)"
            )

        if serp_configured:
            st.success(
                "SerpApi : clé présente "
                "*(Indeed, LinkedIn, Glassdoor, HelloWork, Monster, Talent.com, Google Jobs)*"
            )
        else:
            st.caption("SerpApi : non configuré — [serpapi.com](https://serpapi.com/)")

        if st.button(
            "Tester Welcome to the Jungle",
            use_container_width=True,
            key="admin_test_wttj",
        ):
            ok, message = test_wttj_connection()
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Jooble", use_container_width=True, key="admin_test_jooble"):
            ok, message = test_jooble_connection(provider_secrets["jooble_api_key"])
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button(
            "Tester OptionCarriere",
            use_container_width=True,
            key="admin_test_optioncarriere",
        ):
            ok, message = test_optioncarriere_connection(
                provider_secrets["careerjet_api_key"],
                user_ip=provider_secrets["careerjet_user_ip"],
                referer=resolve_careerjet_referer(provider_secrets["careerjet_referer"]),
                client_ip=resolve_streamlit_client_ip(),
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester JobTeaser", use_container_width=True, key="admin_test_jobteaser"):
            ok, message = test_jobteaser_connection(provider_secrets["apify_api_token"])
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester HelloWork", use_container_width=True, key="admin_test_hellowork"):
            ok, message = test_hellowork_connection(
                provider_secrets["apify_api_token"],
                serpapi_key=provider_secrets["serpapi_api_key"],
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Monster", use_container_width=True, key="admin_test_monster"):
            ok, message = test_monster_connection(
                provider_secrets["apify_api_token"],
                serpapi_key=provider_secrets["serpapi_api_key"],
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Talent.com", use_container_width=True, key="admin_test_talent"):
            ok, message = test_talent_connection(
                provider_secrets["apify_api_token"],
                serpapi_key=provider_secrets["serpapi_api_key"],
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Indeed (SerpApi)", use_container_width=True, key="admin_test_indeed"):
            ok, message = test_serpapi_platform_connection(
                provider_secrets["serpapi_api_key"], "indeed"
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button(
            "Tester LinkedIn (SerpApi)",
            use_container_width=True,
            key="admin_test_linkedin",
        ):
            ok, message = test_serpapi_platform_connection(
                provider_secrets["serpapi_api_key"], "linkedin"
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button(
            "Tester Glassdoor (SerpApi)",
            use_container_width=True,
            key="admin_test_glassdoor",
        ):
            ok, message = test_serpapi_platform_connection(
                provider_secrets["serpapi_api_key"], "glassdoor"
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester connexion Adzuna", use_container_width=True, key="admin_test_adzuna"):
            ok, message = test_adzuna_connection()
            if ok:
                st.success(message)
            else:
                st.error(message)
                render_adzuna_auth_help(adzuna_id)

        if st.button("Tester connexion IA", use_container_width=True, key="admin_test_ai"):
            ok, message, provider = test_ai_connection()
            if ok:
                st.success(f"{provider} — {message}")
            else:
                st.error(f"{provider} — {message}")
                if groq_configured and (
                    "401" in message
                    or "Invalid API Key" in message
                    or "refusée" in message
                ):
                    render_groq_key_help()
                elif groq_configured:
                    fp = hashlib.sha256(get_secret("GROQ_API_KEY").encode()).hexdigest()[:16]
                    models, live = fetch_groq_model_ids(fp)
                    if live and models:
                        st.caption(
                            "Modèles Groq (API live) : "
                            + ", ".join(f"`{m}`" for m in models[:6])
                        )
                    elif models:
                        st.caption(
                            "Liste modèles par défaut (API Groq non joignable) — "
                            "vérifiez votre clé."
                        )

        if show_clear_cache and st.button(
            t("app.clear_cache"), use_container_width=True, key="admin_clear_cache"
        ):
            st.cache_data.clear()
            st.session_state.analysis = None
            st.session_state.pdf_fingerprint = None
            st.session_state.analysis_notices = []
            st.session_state.groq_quota_exhausted = False
            st.session_state.llm_backend_active = None
            st.success(t("app.cache_cleared"))
            st.rerun()


def _cached_support_unread(user_id: int) -> int:
    now = time.time()
    if (
        st.session_state.get("_support_unread_uid") == int(user_id)
        and (now - float(st.session_state.get("_support_unread_at") or 0)) < 15
    ):
        return int(st.session_state.get("_support_unread") or 0)
    count = user_support_unread(int(user_id))
    st.session_state._support_unread_uid = int(user_id)
    st.session_state._support_unread_at = now
    st.session_state._support_unread = count
    return count


def _sidebar_job_provider() -> str:
    stored = st.session_state.get("job_provider")
    if stored in JOB_PROVIDER_SIDEBAR_ORDER:
        return str(stored)
    provider = default_job_provider(secrets=provider_secrets_from_getter(get_secret))
    st.session_state.job_provider = provider
    return provider


def render_app() -> None:
    """Main application shell with navigation."""
    render_app_styles()
    _apply_pending_navigation()
    user = st.session_state.user or {}
    user_name = user.get("full_name") or t("common.user")
    job_provider = _sidebar_job_provider()
    analysis_depth = st.session_state.get("analysis_depth", "standard")

    with st.sidebar:
        photo_url = None
        if user.get("id"):
            photo_url = cached_sidebar_photo_data_url(int(user["id"]), st.session_state)
        render_sidebar_brand(user, photo_url)

        st.markdown('<p class="sidebar-nav-label">Menu</p>', unsafe_allow_html=True)
        support_unread = 0
        if user.get("id"):
            support_unread = _cached_support_unread(int(user["id"]))

        def _sidebar_nav_label(key: str) -> str:
            label = nav_label_with_icon(key, nav_label(key))
            if key == "support" and support_unread:
                return f"{label}  ({support_unread})"
            return label

        page = st.radio(
            "Navigation",
            list(NAV_PAGE_KEYS),
            format_func=_sidebar_nav_label,
            label_visibility="collapsed",
            key="main_navigation",
        )

        if page == "analysis":
            st.markdown("---")
            options = JOB_PROVIDER_SIDEBAR_ORDER
            current = job_provider if job_provider in options else options[0]
            job_provider = st.selectbox(
                t("app.job_provider"),
                options,
                index=options.index(current),
                format_func=job_provider_label,
                help=t("app.job_provider_help"),
                key="sidebar_job_provider",
            )
            st.session_state.job_provider = job_provider

            current_depth = st.session_state.get("analysis_depth", "standard")
            if current_depth not in ANALYSIS_DEPTH_OPTIONS:
                current_depth = "standard"
            analysis_depth = st.selectbox(
                t("app.analysis_depth"),
                ANALYSIS_DEPTH_OPTIONS,
                index=ANALYSIS_DEPTH_OPTIONS.index(current_depth),
                format_func=analysis_depth_label,
                help=t("app.analysis_depth_help"),
                key="analysis_depth_select",
            )
            st.session_state.analysis_depth = analysis_depth

        render_language_selector(key_prefix="sidebar_locale", persist_user=True)
        st.markdown('<div class="sidebar-flex-spacer" aria-hidden="true"></div>', unsafe_allow_html=True)

        if st.button(t("app.logout"), use_container_width=True, key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.analysis = None
            st.session_state.pdf_fingerprint = None
            st.rerun()

    render_floating_chat_fab(unread=support_unread, current_page=page)

    if page == "profile":
        render_profile_page(user, job_provider)
        return

    if page == "support":
        render_support_page(user)
        return

    if page == "applications":
        render_page_hero(
            t("hero.applications.title"),
            t("hero.applications.subtitle"),
            badge=t("hero.applications.badge"),
        )
        render_applications_page(user)
        return

    if page == "history":
        render_page_hero(
            t("hero.history.title"),
            t("hero.history.subtitle"),
            badge=t("hero.history.badge"),
        )
        render_history_page(user)
        return

    if page == "dashboard":
        render_dashboard_page(user)
        return

    render_page_hero(
        t("hero.analysis.title"),
        t("hero.analysis.subtitle", name=user_name),
        badge=t("hero.analysis.badge"),
    )
    render_cv_analysis(job_provider, user, analysis_depth=analysis_depth)


def main() -> None:
    """Application entry point — auth gate then main tool."""
    export_streamlit_secrets_to_environ()
    try:
        configure_database(
            get_secret("DATABASE_URL"),
            password=get_secret("DATABASE_PASSWORD"),
        )
        init_db()
    except DatabaseConfigError as exc:
        st.error("**Configuration base de données incorrecte.**")
        st.code(str(exc))
        st.markdown(
            "**Corrigez vos secrets Streamlit ainsi :**\n\n"
            "```toml\n"
            'DATABASE_URL = "postgresql://postgres.ongzgribavyjprbrawzd@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"\n'
            'DATABASE_PASSWORD = "votre_mot_de_passe"\n'
            "```\n\n"
            "Ne mettez **jamais** le mot de passe dans DATABASE_URL si il contient `@`, `#`, `!`, etc."
        )
        return
    except Exception as exc:  # noqa: BLE001
        st.error("**Impossible de se connecter à la base de données.**")
        st.code(format_database_exception(exc))
        if get_secret("DATABASE_URL"):
            st.info(database_connection_hint(exc))
            st.markdown(
                "**Format recommandé (Streamlit Secrets) :**\n\n"
                "```toml\n"
                'DATABASE_URL = "postgresql://postgres.ongzgribavyjprbrawzd@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"\n'
                'DATABASE_PASSWORD = "votre_mot_de_passe_supabase"\n'
                "```\n\n"
                "Copiez l'URL depuis Supabase → **Connect** → **Transaction pooler** (port 6543), "
                "sans le mot de passe dans l'URL."
            )
        else:
            st.warning(
                "DATABASE_URL absent — l'app utilise SQLite local (comptes non conservés en production). "
                "Ajoutez l'URL PostgreSQL Supabase dans les secrets."
            )
        return

    init_session_state()
    ensure_embedded_analysis_worker()

    # One Postgres checkout for the whole Streamlit rerun (avoids 5–8 SSL handshakes).
    with connect():
        if not st.session_state.authenticated:
            render_auth_page()
            return
        render_app()


if __name__ == "__main__":
    main()
