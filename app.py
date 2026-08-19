"""
DowsonBost — Job Finder & CV Matcher
Upload CV (PDF) → AI extraction → Job search → CV matching report
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import os
import re
import unicodedata
from datetime import datetime
from typing import Any

import fitz  # pymupdf
import pdfplumber
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
    EXPERIENCE_LABELS,
    EXPERIENCE_LEVELS,
    GEO_FILTER_MODES,
    SECTOR_OPTIONS,
    apply_strict_job_filters,
    enrich_query_for_contract,
    format_filter_rejection_hint,
    profile_ready_for_matching,
    resolve_experience_level,
    resolve_target_sectors,
)

APP_NAME = "DowsonBost"

from job_providers import (
    JOB_PROVIDER_ADZUNA,
    JOB_PROVIDER_ALL,
    JOB_PROVIDER_GLASSDOOR,
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_JOBTEASER,
    JOB_PROVIDER_JOOBLE,
    JOB_PROVIDER_LABELS,
    JOB_PROVIDER_LINKEDIN,
    JOB_PROVIDER_OPTIONCARRIERE,
    JOB_PROVIDER_SERPAPI,
    JOB_PROVIDER_SIDEBAR_ORDER,
    JOB_PROVIDER_WTTJ,
    configured_providers,
    default_job_provider,
    merge_job_lists,
    provider_secrets_from_getter,
    search_jobs_glassdoor_serpapi,
    search_jobs_indeed_serpapi,
    search_jobs_jobteaser,
    search_jobs_jooble,
    search_jobs_linkedin_serpapi,
    search_jobs_optioncarriere,
    search_jobs_serpapi_google_jobs,
    search_jobs_wttj,
    test_jobteaser_connection,
    test_jooble_connection,
    test_optioncarriere_connection,
    test_serpapi_platform_connection,
    test_wttj_connection,
)
MIN_CV_TEXT_LENGTH = 50
MAX_OCR_PAGES = 5
CACHE_TTL_SECONDS = 86_400  # 24 h

APP_VERSION = "3.0.0-multi-engines"

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


GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_FALLBACK_MODELS = ("gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_MODEL = "gpt-4o-mini"
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_FALLBACK_MODELS = (
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "groq/compound-mini",
)
from auth import (
    authenticate_user,
    change_password,
    format_member_since,
    get_user_by_id,
    init_db,
    register_user,
    reset_password,
    update_user_profile,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

GEMINI_KEY_PLACEHOLDERS = {
    "",
    "votre_cle_gemini",
    "your_api_key",
    "your_gemini_api_key",
    "aiza...",
    "aizasy...",
}


def normalize_secret(value: Any) -> str:
    """Strip whitespace and surrounding quotes from secret values."""
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'").strip()


def get_secret(key: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then environment variables."""
    raw = default
    try:
        raw = st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        raw = os.getenv(key, default)
    return normalize_secret(raw)


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
    """Detect new Google auth keys (AQ.) — currently broken on many accounts."""
    value = key.strip() if key else get_secret("GEMINI_API_KEY")
    return value.startswith("AQ.")


def should_use_gemini() -> bool:
    """Whether to attempt Gemini calls."""
    gemini_key = get_secret("GEMINI_API_KEY")
    if not gemini_key:
        return False

    pref = get_ai_provider_preference()
    if pref == "openai":
        return False
    if pref == "gemini":
        return True
    # auto: skip AQ. keys (Google bug — 401 ACCESS_TOKEN_TYPE_UNSUPPORTED)
    return not gemini_key.startswith("AQ.")


def get_ai_provider_preference() -> str:
    """Return 'groq', 'openai', 'gemini', or 'auto' from secrets."""
    pref = get_secret("AI_PROVIDER", "groq").lower().strip()
    if pref in {"groq", "gemini", "openai", "auto"}:
        return pref
    return "groq"


def resolve_llm_provider() -> str:
    """Pick the active LLM backend based on secrets and preference."""
    pref = get_ai_provider_preference()
    groq_key = get_secret("GROQ_API_KEY")
    openai_key = get_secret("OPENAI_API_KEY")

    if pref == "groq" and groq_key:
        return "groq"
    if pref == "openai" and openai_key:
        return "openai"
    if pref == "gemini" and should_use_gemini():
        return "gemini"

    if pref == "auto" or pref == "groq":
        if groq_key:
            return "groq"
        if openai_key:
            return "openai"
        if should_use_gemini():
            return "gemini"
    elif pref == "openai" and not openai_key and groq_key:
        return "groq"

    return "none"


def ai_setup_status() -> tuple[bool, str]:
    """Return (ready, message) for AI configuration."""
    provider = resolve_llm_provider()
    groq_key = get_secret("GROQ_API_KEY")
    openai_key = get_secret("OPENAI_API_KEY")
    gemini_key = get_secret("GEMINI_API_KEY")

    if provider == "groq":
        return True, "Groq configuré (gratuit) — prêt."
    if provider == "openai":
        return True, "OpenAI configuré — vérifiez vos crédits."
    if provider == "gemini":
        return True, "Gemini configuré (clé AIza)."

    if openai_key and not groq_key:
        return False, (
            "OpenAI sans crédits (erreur 429). Ajoutez **Groq gratuit** : "
            "`GROQ_API_KEY` sur [console.groq.com/keys](https://console.groq.com/keys) "
            "et `AI_PROVIDER = \"groq\"`"
        )

    if gemini_key and gemini_key.startswith("AQ."):
        return False, (
            "Clé Gemini `AQ.` incompatible. Utilisez **Groq gratuit** : "
            "`GROQ_API_KEY` + `AI_PROVIDER = \"groq\"`"
        )

    return False, (
        "Aucune clé IA. Ajoutez `GROQ_API_KEY` (gratuit) dans `.streamlit/secrets.toml`."
    )


def render_ai_setup_help() -> None:
    """Blocking help when AI is not configured."""
    st.error("Configuration IA requise")
    _, message = ai_setup_status()
    st.markdown(message)
    st.markdown(
        """
### Option gratuite recommandée — Groq

1. Créez une clé sur [console.groq.com/keys](https://console.groq.com/keys) *(gratuit)*
2. Éditez `.streamlit/secrets.toml` :
   ```toml
   GROQ_API_KEY = "gsk_votre_cle"
   AI_PROVIDER = "groq"
   ```
3. Redémarrez : `Ctrl+C` puis `streamlit run app.py`

### Option payante — OpenAI

Ajoutez des crédits sur [platform.openai.com/settings/billing](https://platform.openai.com/settings/organization/billing)
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
                "console.groq.com/keys → GROQ_API_KEY + AI_PROVIDER=groq"
            ) from exc
        raise

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Le modèle IA n'a renvoyé aucun texte.")
    return content


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_groq_model_ids(api_key_fingerprint: str) -> list[str]:
    """Fetch live model list from Groq API."""
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        return list(GROQ_FALLBACK_MODELS)

    try:
        response = requests.get(
            f"{GROQ_API_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        if not response.ok:
            return list(GROQ_FALLBACK_MODELS)

        skip_tokens = ("whisper", "embed", "guard", "distil-whisper")
        model_ids = [
            item["id"]
            for item in response.json().get("data", [])
            if not any(token in item["id"].lower() for token in skip_tokens)
        ]
        return model_ids or list(GROQ_FALLBACK_MODELS)
    except Exception:  # noqa: BLE001
        return list(GROQ_FALLBACK_MODELS)


def _groq_chat_raw(
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Direct HTTP call to Groq chat completions (no json_mode — better compatibility)."""
    api_key = get_secret("GROQ_API_KEY")
    json_instruction = (
        "\n\nIMPORTANT : réponds UNIQUEMENT avec un objet JSON valide, sans markdown."
    )
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = requests.post(
        f"{GROQ_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
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
    return content.strip()


def call_groq_text(system_prompt: str, user_prompt: str) -> str:
    """Call Groq — uses live model list from your account."""
    groq_key = get_secret("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY manquante.")

    fp = hashlib.sha256(groq_key.encode()).hexdigest()[:16]
    live_models = fetch_groq_model_ids(fp)
    custom_model = get_secret("GROQ_MODEL")

    if custom_model:
        models = [custom_model] + [m for m in live_models if m != custom_model]
    else:
        # Prefer live models, then static fallbacks
        models = live_models + [m for m in GROQ_FALLBACK_MODELS if m not in live_models]

    seen: set[str] = set()
    unique_models = [m for m in models if m and not (m in seen or seen.add(m))]

    errors: list[str] = []
    for model in unique_models[:8]:
        try:
            result = _groq_chat_raw(model, system_prompt, user_prompt)
            st.session_state.active_llm_provider = f"Groq ({model})"
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{model}: {str(exc)[:100]}")
            continue

    raise RuntimeError(
        "Aucun modèle Groq disponible sur votre compte.\n"
        + "\n".join(errors[:5])
        + "\n\nVérifiez votre clé sur console.groq.com/keys ou recréez-en une."
    )


def call_openai_text(system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI chat completions."""
    openai_key = get_secret("OPENAI_API_KEY")
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


def _gemini_via_sdk(
    parts: list[dict[str, Any]],
    system_prompt: str | None,
    model: str,
) -> str | None:
    """Try Gemini via google-genai SDK. Returns None if SDK unavailable or fails."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

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

    config = types.GenerateContentConfig(temperature=0.2)
    if system_prompt:
        config.system_instruction = system_prompt

    for api_version in ("v1beta", "v1alpha", "v1"):
        try:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(api_version=api_version),
            )
            response = client.models.generate_content(
                model=model,
                contents=sdk_parts,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception:  # noqa: BLE001 — try next API version/model
            continue
    return None


def _gemini_via_rest(
    parts: list[dict[str, Any]],
    system_prompt: str | None,
    model: str,
) -> str | None:
    """Try Gemini via REST. Returns None on failure."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return None

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2},
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    headers = {"Content-Type": "application/json"}
    for request_kwargs in (
        {"headers": {**headers, "x-goog-api-key": api_key}},
        {"params": {"key": api_key}, "headers": headers},
    ):
        response = requests.post(url, json=payload, timeout=90, **request_kwargs)
        if response.ok:
            return _extract_gemini_text(response.json())
    return None


def _gemini_generate_content(
    parts: list[dict[str, Any]],
    system_prompt: str | None = None,
) -> str:
    """Call Gemini with SDK + REST fallbacks across several models."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY manquante.")

    errors: list[str] = []
    for model in GEMINI_FALLBACK_MODELS:
        sdk_text = _gemini_via_sdk(parts, system_prompt, model)
        if sdk_text:
            st.session_state.active_llm_provider = f"Gemini ({model}, SDK)"
            return sdk_text
        errors.append(f"{model}/SDK: échec")

        rest_text = _gemini_via_rest(parts, system_prompt, model)
        if rest_text:
            st.session_state.active_llm_provider = f"Gemini ({model}, REST)"
            return rest_text
        errors.append(f"{model}/REST: échec")

    raise RuntimeError(
        "Connexion Gemini impossible (clé AQ. non reconnue par Google).\n"
        "Solutions :\n"
        "1. Ajoutez OPENAI_API_KEY dans secrets.toml (recommandé)\n"
        "2. Ou créez une clé AIza depuis Google Cloud Console → Credentials\n"
        "3. Ou définissez AI_PROVIDER = \"openai\" dans secrets.toml"
    )


def test_groq_connection() -> tuple[bool, str]:
    try:
        reply = call_groq_text('Réponds en JSON.', '{"status":"OK"}')
        return True, f"Connexion OK — {reply[:40]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


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
    """Test configured AI provider(s). Returns (ok, message, provider)."""
    ready, status_msg = ai_setup_status()
    provider = resolve_llm_provider()

    if not ready:
        return False, status_msg, "—"

    if provider == "groq":
        ok, msg = test_groq_connection()
        return ok, msg, "Groq"
    if provider == "openai":
        ok, msg = test_openai_connection()
        return ok, msg, "OpenAI"
    if provider == "gemini":
        try:
            reply = _gemini_generate_content([{"text": "Réponds uniquement: OK"}])
            return True, f"Gemini OK — {reply[:30]}", "Gemini"
        except Exception as exc:
            return False, str(exc)[:300], "Gemini"

    return False, status_msg, "—"


def call_gemini_text(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini via native REST API."""
    return _gemini_generate_content(
        parts=[{"text": user_prompt}],
        system_prompt=system_prompt,
    )


def extract_text_ocr(pdf_bytes: bytes) -> str:
    """OCR fallback using Gemini vision, or OpenAI vision if Gemini fails."""
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
        if should_use_gemini() and not gemini_failed:
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


def _normalize_match_result(
    data: dict[str, Any],
    job: dict[str, Any] | None = None,
    *,
    fallback: bool = False,
) -> dict[str, Any]:
    """Ensure a job-match payload has the expected shape."""
    score_raw = data.get("score_correspondance", 50)
    try:
        score = max(0, min(100, int(score_raw)))
    except (TypeError, ValueError):
        score = 50

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
    conseils = conseils[:3]

    mots_raw = data.get("mots_cles_manquants", [])
    if isinstance(mots_raw, str):
        mots = [mots_raw]
    elif isinstance(mots_raw, list):
        mots = [str(m).strip() for m in mots_raw if str(m).strip()]
    else:
        mots = []
    mots = mots[:8]

    default_title = job.get("title", "Profil candidat") if job else "Profil candidat"
    titre = str(data.get("titre_cv_recommande") or default_title).strip()

    result = {
        "score_correspondance": score,
        "titre_cv_recommande": titre,
        "mots_cles_manquants": mots,
        "conseils": conseils,
    }
    if fallback:
        result["_fallback"] = True
    return result


def fallback_match_result(job: dict[str, Any]) -> dict[str, Any]:
    """Minimal match report when the LLM response cannot be parsed."""
    return _normalize_match_result(
        {
            "score_correspondance": 50,
            "titre_cv_recommande": job.get("title", "Profil candidat"),
            "mots_cles_manquants": [],
            "conseils": [
                "Analyse partielle — relancez l'analyse pour des conseils détaillés.",
                "Alignez le titre de votre CV sur l'intitulé exact de l'offre.",
                "Reprenez les compétences techniques listées dans la description.",
            ],
        },
        job,
        fallback=True,
    )


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call Groq, OpenAI, or Gemini with automatic fallback."""
    provider = resolve_llm_provider()

    if provider == "groq":
        st.session_state.active_llm_provider = "Groq (gratuit)"
        return call_groq_text(system_prompt, user_prompt)

    if provider == "openai":
        st.session_state.active_llm_provider = "OpenAI"
        return call_openai_text(system_prompt, user_prompt)

    if provider == "gemini":
        st.session_state.active_llm_provider = "Gemini"
        return call_gemini_text(system_prompt, user_prompt)

    raise RuntimeError(
        "Aucune clé IA utilisable. Ajoutez GROQ_API_KEY (gratuit) sur "
        "console.groq.com/keys ou des crédits OpenAI."
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
- competences_techniques : tableau de compétences techniques
- soft_skills : tableau de compétences comportementales
- experiences : tableau d'objets {poste, entreprise, duree}
- diplomes_certifications : tableau de diplômes/certifications
- secteurs : tableau de secteurs d'activité
- niveau_experience : junior, confirme ou senior
- mots_cles : tableau de 5 à 10 mots-clés dominants
- mobilite_geographique : texte libre (si mentionné dans le CV, sinon "")
- disponibilites : texte libre (si mentionné, sinon "")

Exemple valide :
{"metier":"Technicien Systèmes et Réseau","query_recherche":"Technicien systèmes réseau Linux","competences_techniques":["Linux","Windows Server","VMware"],"soft_skills":["Rigueur","Travail en équipe"],"experiences":[{"poste":"Technicien support","entreprise":"ACME","duree":"2020-2024"}],"diplomes_certifications":["BTS SIO"],"secteurs":["Informatique","Télécoms"],"niveau_experience":"confirme","mots_cles":["Linux","Réseau","Active Directory"],"mobilite_geographique":"Île-de-France","disponibilites":"Immédiate"}"""

CRITERIA_RETRY_PROMPT = CRITERIA_SYSTEM_PROMPT + """

RAPPEL CRITIQUE : ta réponse précédente a recopié le modèle au lieu du CV.
Relis le CV ligne par ligne. Remplis metier, ville et mots_cles avec des termes EXACTS du document.
Réponds UNIQUEMENT en JSON, sans markdown."""


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


def match_cv_to_job(cv_text: str, job: dict[str, Any]) -> dict[str, Any]:
    """Compare CV against a single job offer and return optimization advice."""
    system_prompt = """Tu es un coach carrière expert en ATS et recrutement.
Compare le CV du candidat à l'offre d'emploi et produis un rapport d'optimisation.
Réponds UNIQUEMENT en JSON valide, sans markdown ni texte autour :
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

    desc_limit = 3500
    job_summary = (
        f"Titre : {job.get('title', '')}\n"
        f"Entreprise : {job.get('company', '')}\n"
        f"Lieu : {job.get('location', '')}\n"
        f"Contrat : {job.get('contract_type', '')}\n"
        f"Description :\n{job.get('description', '')[:desc_limit]}"
    )
    user_prompt = f"CV candidat :\n{cv_text[:6000]}\n\nOffre :\n{job_summary}"

    for attempt in range(2):
        try:
            prompt = system_prompt
            if attempt == 1:
                prompt += (
                    "\n\nRAPPEL CRITIQUE : retourne UNIQUEMENT l'objet JSON, "
                    "rien avant ni après. Pas de commentaire."
                )
            raw = call_llm(prompt, user_prompt)
            return _normalize_match_result(_parse_json_response(raw), job)
        except (json.JSONDecodeError, TypeError, ValueError):
            if attempt == 0:
                continue

    return fallback_match_result(job)


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
    metier: str = "",
    contract_type: str = "",
) -> dict[str, Any]:
    boosted_query = enrich_query_for_contract(query, contract_type)
    boosted_metier = enrich_query_for_contract(metier, contract_type)
    return search_jobs_with_fallback(
        provider,
        boosted_query,
        location,
        country,
        boosted_metier,
        contract_type,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_match_cv_to_job(cv_text: str, job_json: str) -> dict[str, Any]:
    return match_cv_to_job(cv_text, json.loads(job_json))


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
) -> dict[str, Any]:
    """Search jobs nationally by métier; optional location is a last-resort hint only."""
    if provider == JOB_PROVIDER_ALL:
        return _search_all_providers_with_fallback(
            query, location, country, metier, contract_type
        )

    attempts: list[tuple[str, str, str]] = []
    q = query.strip()
    loc = location.strip()
    m = metier.strip()

    if q:
        attempts.append((q, "", "Recherche nationale (métier)"))
    if m and m.lower() != q.lower():
        attempts.append((m, "", "Intitulé métier seul"))
    short = " ".join((q or m).split()[:2])
    if short and short.lower() != (q or m).lower():
        attempts.append((short, "", "Requête élargie"))
    if q and loc:
        attempts.append((q, loc, "Recherche avec zone indicative"))

    seen: set[tuple[str, str]] = set()
    for q_try, loc_try, label in attempts:
        key = (q_try.lower(), loc_try.lower())
        if not q_try or key in seen:
            continue
        seen.add(key)
        jobs = search_jobs(provider, q_try, loc_try, country, contract_type)
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


def _search_all_providers_with_fallback(
    query: str,
    location: str,
    country: str,
    metier: str = "",
    contract_type: str = "",
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
    queries = [q] if q else []
    if metier.strip() and metier.strip().lower() != q.lower():
        queries.append(metier.strip())
    if not queries:
        queries = [""]

    for q_try in queries:
        merged: list[dict[str, Any]] = []
        used: list[str] = []
        for provider in providers:
            try:
                batch = search_jobs(provider, q_try, "", country, contract_type)
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
                "location_used": f"(tout {country or 'France'})",
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
            user_ip=secrets["careerjet_user_ip"],
            referer=secrets["careerjet_referer"],
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

    if provider == JOB_PROVIDER_SERPAPI:
        if not serp_key:
            raise RuntimeError("Clé SerpApi manquante. Configurez SERPAPI_API_KEY.")
        serp_location = f"{location}, {country}" if location else country
        return search_jobs_serpapi_google_jobs(
            query, serp_location, country, serp_key
        )

    country_code = resolve_country_code(country)
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

_PDF_CHAR_REPLACEMENTS = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u00b7": "-",  # middle dot
    "\u2022": "-",  # bullet
    "\u2026": "...",  # ellipsis
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
}


def pdf_safe_text(value: Any, default: str = "-") -> str:
    """Make text safe for fpdf2 core fonts (Helvetica/Times, Latin-1)."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return default
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("latin-1", errors="replace").decode("latin-1")


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
        missing = ", ".join(match.get("mots_cles_manquants", []))
        tips_html = "".join(
            f"<li>{pdf_escape(tip)}</li>"
            for tip in match.get("conseils", [])[:3]
        )

        body_html += f"""
        <hr>
        <h2>#{idx} - {pdf_escape(job.get('title', 'N/A'))} ({score}%)</h2>
        <ul>
            <li><b>Entreprise :</b> {pdf_escape(job.get('company', 'N/A'))}</li>
            <li><b>Lieu :</b> {pdf_escape(job.get('location', 'N/A'))}</li>
            <li><b>Contrat :</b> {pdf_escape(job.get('contract_type') or '-')}</li>
            <li><b>Source :</b> {pdf_escape(job.get('source', ''))}</li>
            <li><b>Lien :</b> {pdf_escape(job.get('url', '-'))}</li>
            <li><b>Titre CV recommande :</b> {pdf_escape(match.get('titre_cv_recommande', 'N/A'))}</li>
            <li><b>Mots-cles manquants :</b> {pdf_escape(missing or '-')}</li>
        </ul>
        <h3>Conseils d'optimisation</h3>
        <ol>{tips_html}</ol>
        """

    pdf.write_html(body_html)
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
        job_provider, query, location, country, metier
    )
    jobs = search_result["jobs"]
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
        "search_strategy": search_result.get("strategy"),
        "search_query_used": search_result.get("query_used"),
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
        if job.get("contract_type") or job.get("inferred_contract"):
            contract_label = job.get("inferred_contract") or job.get("contract_type")
            st.markdown(f"**Contrat :** {contract_label}")
        if job.get("inferred_experience"):
            st.markdown(f"**Niveau :** {EXPERIENCE_LABELS.get(job['inferred_experience'], job['inferred_experience'])}")
        if job.get("inferred_sector"):
            st.markdown(f"**Secteur :** {job['inferred_sector']}")
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


def render_cv_profile_summary(criteria: dict[str, Any], user_profile: dict[str, Any]) -> None:
    """Display enriched CV profile and user matching preferences."""
    st.subheader("Profil candidat & critères de recherche")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Métier visé", criteria.get("metier", "—"))
    cv_level = criteria.get("niveau_experience", "—")
    profile_level = user_profile.get("experience_level", "confirme")
    c2.metric(
        "Niveau",
        EXPERIENCE_LABELS.get(profile_level, profile_level)
        if profile_level != "tous"
        else f"CV: {cv_level}",
    )
    c3.metric("Contrat recherché", user_profile.get("contract_type", "—"))
    c4.metric("Zone", user_profile.get("home_city", "—"))

    profile_sectors = user_profile.get("target_sectors") or []
    cv_sectors = criteria.get("secteurs") or []
    active_sectors = profile_sectors or cv_sectors
    if active_sectors:
        st.caption("**Secteurs ciblés :** " + ", ".join(active_sectors))

    geo_labels = {
        "ville": "Même ville",
        "departement": "Même département",
        "rayon": f"Rayon {user_profile.get('search_radius_km', 20)} km",
    }
    region_text, dept_text, city_text = format_profile_geo_summary(user_profile)
    st.caption(
        f"Filtrage géographique : **{geo_labels.get(user_profile.get('geo_filter_mode', 'departement'), '—')}** · "
        f"{user_profile.get('country', 'France')} · "
        f"Régions : **{region_text}** · "
        f"Départements : **{dept_text}** · "
        f"Villes : **{city_text}**"
    )

    tech = criteria.get("competences_techniques") or criteria.get("mots_cles") or []
    soft = criteria.get("soft_skills") or []
    if tech:
        st.markdown("**Compétences techniques :** " + " · ".join(f"`{kw}`" for kw in tech))
    if soft:
        st.markdown("**Soft skills :** " + " · ".join(f"`{kw}`" for kw in soft))

    col_a, col_b = st.columns(2)
    with col_a:
        diplomes = criteria.get("diplomes_certifications") or []
        if diplomes:
            st.markdown("**Diplômes / certifications**")
            for item in diplomes:
                st.write(f"- {item}")
        secteurs = criteria.get("secteurs") or []
        if secteurs:
            st.markdown("**Secteurs :** " + ", ".join(secteurs))
    with col_b:
        experiences = criteria.get("experiences") or []
        if experiences:
            st.markdown("**Expériences clés**")
            for exp in experiences[:4]:
                if isinstance(exp, dict):
                    st.write(
                        f"- {exp.get('poste', '—')} · {exp.get('entreprise', '—')} "
                        f"({exp.get('duree', '—')})"
                    )
        if criteria.get("mobilite_geographique"):
            st.markdown(f"**Mobilité (CV) :** {criteria['mobilite_geographique']}")
        if criteria.get("disponibilites"):
            st.markdown(f"**Disponibilités (CV) :** {criteria['disponibilites']}")


def render_analysis_results(analysis: dict[str, Any]) -> None:
    """Display stored analysis results and export button."""
    criteria = analysis["criteria"]
    user_profile = analysis.get("user_profile", {})
    extraction_method = analysis["extraction_method"]
    filter_stats = analysis.get("filter_stats", {})

    method_label = "Texte natif PDF" if extraction_method == "native" else "OCR Gemini Vision"
    st.caption(f"Extraction CV : **{method_label}**")

    with st.expander("Texte extrait du CV", expanded=False):
        cv_preview = analysis["cv_text"]
        st.text(cv_preview[:3000] + ("…" if len(cv_preview) > 3000 else ""))

    render_cv_profile_summary(criteria, user_profile)

    if filter_stats:
        st.info(
            f"**Filtrage strict** : {filter_stats.get('kept', 0)} offre(s) retenue(s) sur "
            f"{filter_stats.get('total', 0)} — "
            f"{filter_stats.get('rejected_contract', 0)} contrat · "
            f"{filter_stats.get('rejected_geo', 0)} zone · "
            f"{filter_stats.get('rejected_experience', 0)} niveau · "
            f"{filter_stats.get('rejected_sector', 0)} secteur."
        )

    st.success(
        f"{analysis['jobs_found']} offre(s) éligible(s) après filtrage. "
        f"Top {len(analysis['results'])} analysé(s)."
    )

    col_export, col_info = st.columns([1, 2])
    with col_export:
        try:
            if not analysis.get("report_pdf"):
                analysis["report_pdf"] = generate_matching_report_pdf(
                    criteria,
                    analysis["results"],
                    method_label,
                )
            st.download_button(
                label="Télécharger le rapport (PDF)",
                data=analysis["report_pdf"],
                file_name="rapport_matching_dowsonbost.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="download_matching_report",
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Export PDF indisponible : {exc}")
    with col_info:
        st.caption(
            "Le rapport PDF inclut les 5 offres, scores, mots-clés manquants "
            "et conseils d'optimisation."
        )

    st.subheader("Top 5 — Rapport de matching & optimisation CV")
    for idx, entry in enumerate(analysis["results"], start=1):
        render_job_card(entry["job"], entry["match"], idx)


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
    pdf_bytes: bytes,
    job_provider: str,
    user_profile: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Run the CV analysis pipeline without mutating the Streamlit DOM."""
    notices: list[dict[str, str]] = []

    cv_text, method = extract_cv_text(pdf_bytes)
    if method == "ocr":
        notices.append(
            {
                "level": "warning",
                "text": "PDF scanné détecté — extraction via OCR Gemini Vision.",
            }
        )

    criteria = cached_extract_criteria(cv_text)
    if criteria.get("_heuristic"):
        notices.append(
            {
                "level": "warning",
                "text": "Extraction IA partielle — profil déduit automatiquement du texte du CV.",
            }
        )

    query = criteria.get("query_recherche") or criteria.get("metier", "")
    country = user_profile.get("country", "France")
    contract_type = user_profile.get("contract_type", "CDI")
    keywords = criteria.get("mots_cles") or criteria.get("competences_techniques") or []
    metier = criteria.get("metier", "")

    # National API search (métier + contrat) — geographic profile applied after fetch.
    search_result = cached_search_jobs(
        job_provider,
        query,
        "",
        country,
        metier,
        contract_type=contract_type,
    )
    raw_jobs = search_result["jobs"]
    jobs, filter_stats = apply_strict_job_filters(
        raw_jobs, user_profile, cv_profile=criteria
    )

    providers_used = search_result.get("providers_used") or [job_provider]
    if len(providers_used) > 1:
        sources = ", ".join(JOB_PROVIDER_LABELS.get(p, p) for p in providers_used)
        source_text = f"moteurs : {sources}"
    else:
        source_text = f"moteur : {JOB_PROVIDER_LABELS.get(providers_used[0], providers_used[0])}"

    notices.append(
        {
            "level": "info",
            "text": (
                f"Recherche **nationale** ({country}) via {source_text} — "
                f"filtrage ensuite selon votre profil (pays, régions, départements, villes)."
            ),
        }
    )

    if not raw_jobs:
        notices.append(
            {
                "level": "warning",
                "text": (
                    "Aucune offre trouvée par les moteurs pour cette requête. "
                    "Essayez « Tous les moteurs » ou élargissez le métier."
                ),
            }
        )
        notices.append(
            {
                "level": "info",
                "text": (
                    f"Requête testée : `{search_result.get('query_used', query)}` · "
                    f"Périmètre : `{search_result.get('location_used', f'tout {country}')}`"
                ),
            }
        )
        return None, notices

    if not jobs:
        level_label = EXPERIENCE_LABELS.get(
            resolve_experience_level(user_profile, criteria), "—"
        )
        hint = format_filter_rejection_hint(filter_stats, user_profile)
        notices.append(
            {
                "level": "warning",
                "text": (
                    f"Aucune offre ne correspond à vos filtres stricts "
                    f"({user_profile.get('contract_type')} · {level_label} · "
                    f"{user_profile.get('geo_filter_mode')})."
                ),
            }
        )
        notices.append({"level": "info", "text": f"Principal blocage : {hint}."})
        notices.append(
            {
                "level": "info",
                "text": (
                    f"{filter_stats.get('total', 0)} offre(s) brutes · "
                    f"{filter_stats.get('rejected_contract', 0)} rejetées contrat · "
                    f"{filter_stats.get('rejected_geo', 0)} rejetées zone · "
                    f"{filter_stats.get('rejected_experience', 0)} rejetées niveau · "
                    f"{filter_stats.get('rejected_sector', 0)} rejetées secteur."
                ),
            }
        )
        return None, notices

    if search_result.get("strategy") not in (None, "Recherche précise"):
        notices.append(
            {
                "level": "info",
                "text": (
                    f"Recherche élargie ({search_result['strategy']}) — "
                    f"`{search_result.get('query_used')}` · "
                    f"{len(raw_jobs)} offre(s) brutes, {len(jobs)} après filtrage."
                ),
            }
        )

    ranked_jobs = rank_jobs_for_cv(jobs, cv_text, keywords)
    results: list[dict[str, Any]] = []
    partial_matches = 0
    for job in ranked_jobs:
        job_json = json.dumps(job, sort_keys=True, ensure_ascii=False)
        match = cached_match_cv_to_job(cv_text, job_json)
        if match.get("_fallback"):
            partial_matches += 1
        results.append({"job": job, "match": match})

    if partial_matches:
        notices.append(
            {
                "level": "warning",
                "text": (
                    f"{partial_matches} offre(s) analysée(s) en mode dégradé "
                    "(réponse IA partielle). Relancez après **Vider le cache** pour réessayer."
                ),
            }
        )

    analysis = {
        "cv_text": cv_text,
        "extraction_method": method,
        "criteria": criteria,
        "user_profile": user_profile,
        "filter_stats": filter_stats,
        "jobs_found": len(jobs),
        "jobs_raw": len(raw_jobs),
        "search_strategy": search_result.get("strategy"),
        "search_query_used": search_result.get("query_used"),
        "results": results,
        "job_provider": job_provider,
    }
    return analysis, notices


def format_profile_geo_summary(profile: dict[str, Any]) -> tuple[str, str, str]:
    """Return human-readable (regions, departments, cities) labels for display."""
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


def render_auth_styles() -> None:
    """Inject CSS for the login/register page."""
    st.markdown(
        """
        <style>
        .dowson-hero {
            text-align: center;
            padding: 1.5rem 0 0.5rem 0;
        }
        .dowson-hero h1 {
            font-size: 2.4rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .dowson-hero p {
            color: #94a3b8;
            font-size: 1.05rem;
        }
        .dowson-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_page() -> None:
    """Login and registration page."""
    render_auth_styles()

    st.markdown(
        f"""
        <div class="dowson-hero">
            <h1>{APP_NAME}</h1>
            <p>Auto Job Finder & CV Matcher — connectez-vous pour accéder à l'outil</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _left, center, _right = st.columns([1, 1.2, 1])
    with center:
        tab_login, tab_register, tab_reset = st.tabs(
            ["Connexion", "Créer un compte", "Mot de passe oublié"]
        )

        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                login_email = st.text_input("E-mail", placeholder="vous@exemple.com")
                login_password = st.text_input(
                    "Mot de passe", type="password", placeholder="••••••••"
                )
                if st.form_submit_button(
                    "Se connecter", type="primary", use_container_width=True
                ):
                    ok, message, user = authenticate_user(login_email, login_password)
                    if ok and user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

        with tab_register:
            st.markdown("**Localisation**")
            reg_admin_regions, reg_departments = render_region_department_selectors(
                {},
                key_prefix="register",
            )
            reg_cities, reg_all_cities = render_city_selector(
                {},
                key_prefix="register",
                selected_departments=reg_departments,
                country="France",
            )
            with st.form("register_form", clear_on_submit=False):
                reg_name = st.text_input("Nom complet", placeholder="Jean Dupont")
                reg_email = st.text_input("E-mail", placeholder="vous@exemple.com")
                reg_password = st.text_input(
                    "Mot de passe", type="password", placeholder="8 caractères minimum"
                )
                reg_password2 = st.text_input(
                    "Confirmer le mot de passe", type="password"
                )
                st.markdown("**Préférences de recherche d'emploi**")
                r1, r2 = st.columns(2)
                with r1:
                    reg_home_city = st.text_input(
                        "Ville de domicile (centre du rayon)",
                        placeholder="Lyon",
                    )
                    reg_postal = st.text_input("Code postal", placeholder="69001")
                with r2:
                    reg_country = st.selectbox(
                        "Pays",
                        COUNTRY_OPTIONS,
                        index=0,
                    )
                    reg_contract = st.selectbox(
                        "Type de contrat recherché",
                        CONTRACT_TYPES,
                        index=0,
                    )
                reg_geo = st.selectbox(
                    "Contrainte de distance supplémentaire",
                    GEO_FILTER_MODES,
                    index=1,
                    format_func=lambda x: {
                        "ville": "Villes sélectionnées uniquement",
                        "departement": "Pays, régions, départements et villes sélectionnés",
                        "rayon": "Critères ci-dessus + rayon autour du domicile",
                    }[x],
                )
                reg_radius = st.slider("Rayon (km)", 5, 100, 20, disabled=(reg_geo != "rayon"))
                reg_experience = st.selectbox(
                    "Niveau d'expérience recherché",
                    EXPERIENCE_LEVELS,
                    index=1,
                    format_func=lambda x: EXPERIENCE_LABELS[x],
                )
                reg_sectors = st.multiselect(
                    "Secteurs d'activité ciblés (optionnel — sinon déduits du CV)",
                    SECTOR_OPTIONS,
                    default=["Informatique"],
                    key="register_target_sectors",
                )
                if st.form_submit_button(
                    "Créer mon compte", type="primary", use_container_width=True
                ):
                    if reg_password != reg_password2:
                        st.error("Les mots de passe ne correspondent pas.")
                    else:
                        cities = reg_cities
                        if not reg_all_cities and not cities and reg_home_city.strip():
                            cities = [reg_home_city.strip()]
                        ok, message = register_user(
                            reg_name,
                            reg_email,
                            reg_password,
                            home_city=reg_home_city,
                            postal_code=reg_postal,
                            admin_regions=reg_admin_regions,
                            selected_departments=reg_departments,
                            selected_cities=cities,
                            all_cities=reg_all_cities,
                            country=reg_country,
                            contract_type=reg_contract,
                            geo_filter_mode=reg_geo,
                            search_radius_km=reg_radius,
                            experience_level=reg_experience,
                            target_sectors=reg_sectors,
                        )
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)

        with tab_reset:
            st.caption(
                "Saisissez votre e-mail et votre **nom complet** (identique à l'inscription) "
                "pour définir un nouveau mot de passe."
            )
            with st.form("reset_form", clear_on_submit=False):
                reset_email = st.text_input("E-mail", placeholder="vous@exemple.com")
                reset_name = st.text_input("Nom complet", placeholder="Jean Dupont")
                reset_password_1 = st.text_input(
                    "Nouveau mot de passe", type="password", placeholder="8 caractères minimum"
                )
                reset_password_2 = st.text_input(
                    "Confirmer le nouveau mot de passe", type="password"
                )
                if st.form_submit_button(
                    "Réinitialiser le mot de passe", type="primary", use_container_width=True
                ):
                    if reset_password_1 != reset_password_2:
                        st.error("Les mots de passe ne correspondent pas.")
                    else:
                        ok, message = reset_password(
                            reset_email, reset_name, reset_password_1
                        )
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)


def render_profile_page(user: dict[str, Any]) -> None:
    """Profile settings: view info, update name, change password."""
    _flush_analysis_notices()
    profile = get_user_by_id(user["id"]) or user

    st.subheader("Mon profil")
    st.caption("Gérez vos informations personnelles et votre mot de passe.")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("E-mail", profile.get("email", "—"))
    with col2:
        member_since = profile.get("created_at", "")
        st.metric(
            "Membre depuis",
            format_member_since(member_since) if member_since else "—",
        )

    st.markdown("---")

    col_info, col_password = st.columns(2)

    with col_info:
        st.markdown("#### Informations personnelles")
        admin_regions, selected_departments = render_region_department_selectors(
            profile,
            key_prefix=f"profile_{user['id']}",
        )
        profile_cities, profile_all_cities = render_city_selector(
            profile,
            key_prefix=f"profile_{user['id']}",
            selected_departments=selected_departments,
            country=profile.get("country", "France"),
        )
        with st.form("profile_form"):
            new_name = st.text_input(
                "Nom complet",
                value=profile.get("full_name", ""),
            )
            p1, p2 = st.columns(2)
            with p1:
                home_city = st.text_input(
                    "Ville de domicile (centre du rayon)",
                    value=profile.get("home_city", ""),
                )
                postal_code = st.text_input(
                    "Code postal",
                    value=profile.get("postal_code", ""),
                )
            with p2:
                profile_country_value = st.selectbox(
                    "Pays",
                    COUNTRY_OPTIONS,
                    index=COUNTRY_OPTIONS.index(profile.get("country", "France"))
                    if profile.get("country") in COUNTRY_OPTIONS
                    else 0,
                )
                contract_type = st.selectbox(
                    "Type de contrat recherché",
                    CONTRACT_TYPES,
                    index=CONTRACT_TYPES.index(profile.get("contract_type", "CDI"))
                    if profile.get("contract_type") in CONTRACT_TYPES
                    else 0,
                )
            geo_mode = st.selectbox(
                "Contrainte de distance supplémentaire",
                GEO_FILTER_MODES,
                index=GEO_FILTER_MODES.index(profile.get("geo_filter_mode", "departement"))
                if profile.get("geo_filter_mode") in GEO_FILTER_MODES
                else 1,
                format_func=lambda x: {
                    "ville": "Villes sélectionnées uniquement",
                    "departement": "Pays, régions, départements et villes sélectionnés",
                    "rayon": "Critères ci-dessus + rayon autour du domicile",
                }[x],
            )
            search_radius = st.slider(
                "Rayon de recherche (km)",
                5,
                100,
                int(profile.get("search_radius_km") or 20),
                disabled=(geo_mode != "rayon"),
            )
            exp_index = (
                EXPERIENCE_LEVELS.index(profile.get("experience_level", "confirme"))
                if profile.get("experience_level") in EXPERIENCE_LEVELS
                else 1
            )
            experience_level = st.selectbox(
                "Niveau d'expérience recherché",
                EXPERIENCE_LEVELS,
                index=exp_index,
                format_func=lambda x: EXPERIENCE_LABELS[x],
            )
            current_sectors = profile.get("target_sectors") or []
            sectors_key = f"profile_sectors_{user['id']}"
            if sectors_key not in st.session_state:
                st.session_state[sectors_key] = [
                    s for s in current_sectors if s in SECTOR_OPTIONS
                ]
            target_sectors = st.multiselect(
                "Secteurs d'activité ciblés",
                SECTOR_OPTIONS,
                help="Laisser vide pour utiliser les secteurs détectés dans le CV.",
                key=sectors_key,
            )
            st.caption(
                "Seules les offres correspondant à votre **pays**, **régions**, "
                "**départements**, **villes**, **contrat**, **niveau** et **secteur(s)** "
                "seront proposées."
            )
            if st.form_submit_button("Enregistrer le profil", use_container_width=True):
                cities = profile_cities
                if not profile_all_cities and not cities and home_city.strip():
                    cities = [home_city.strip()]
                ok, message, updated = update_user_profile(
                    user["id"],
                    new_name,
                    home_city,
                    postal_code,
                    admin_regions,
                    selected_departments,
                    cities,
                    profile_all_cities,
                    profile_country_value,
                    contract_type,
                    geo_mode,
                    search_radius,
                    experience_level,
                    target_sectors,
                )
                if ok and updated:
                    st.session_state.user = updated
                    st.session_state.pop(sectors_key, None)
                    prefix = f"profile_{user['id']}"
                    st.session_state.pop(f"{prefix}_admin_regions", None)
                    st.session_state.pop(f"{prefix}_department_labels", None)
                    st.session_state.pop(f"{prefix}_last_admin_regions", None)
                    st.session_state.pop(f"{prefix}_selected_cities", None)
                    st.session_state.pop(f"{prefix}_last_departments_for_cities", None)
                    st.session_state.pop(f"{prefix}_all_cities", None)
                    st.session_state.analysis_notices = [
                        {"level": "success", "text": message}
                    ]
                    st.rerun()
                else:
                    st.error(message)

    with col_password:
        st.markdown("#### Changer le mot de passe")
        with st.form("password_form"):
            current_pw = st.text_input("Mot de passe actuel", type="password")
            new_pw = st.text_input("Nouveau mot de passe", type="password")
            new_pw2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
            if st.form_submit_button("Modifier le mot de passe", use_container_width=True):
                if new_pw != new_pw2:
                    st.error("Les nouveaux mots de passe ne correspondent pas.")
                else:
                    ok, message = change_password(user["id"], current_pw, new_pw)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)


def render_cv_analysis(job_provider: str, user: dict[str, Any]) -> None:
    """CV upload and matching workflow."""
    ready, _ = ai_setup_status()
    if not ready:
        render_ai_setup_help()
        return

    user_profile = get_user_by_id(user["id"]) or user
    profile_ok, profile_msg = profile_ready_for_matching(user_profile)
    if not profile_ok:
        st.warning(profile_msg)
        st.info(
            "Complétez votre **ville**, **code postal** et **type de contrat** "
            "dans **Mon profil** avant de lancer une analyse."
        )
        return

    active_level = resolve_experience_level(user_profile, {})
    active_sectors = resolve_target_sectors(user_profile, {})
    region_text, dept_text, city_text = format_profile_geo_summary(user_profile)
    st.caption(
        f"Filtres actifs : contrat **{user_profile.get('contract_type')}** · "
        f"pays **{user_profile.get('country', 'France')}** · "
        f"niveau **{EXPERIENCE_LABELS.get(active_level, active_level)}** · "
        f"secteurs **{', '.join(active_sectors) if active_sectors else 'CV'}** · "
        f"régions **{region_text}** · départements **{dept_text}** · "
        f"villes **{city_text}**"
    )

    uploaded_file = st.file_uploader(
        "Déposez votre CV (PDF)",
        type=["pdf"],
        help="PDF natif ou scanné — l'OCR Gemini s'active automatiquement si besoin.",
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
            _flush_analysis_notices()
            render_analysis_results(st.session_state.analysis)
        else:
            st.info("Uploadez votre CV pour démarrer l'analyse automatique.")
        return

    if fp_matches:
        st.info("Résultats en cache pour ce CV — relancez pour forcer une nouvelle analyse.")

    if st.button(
        "Lancer l'analyse complète",
        type="primary",
        use_container_width=True,
        key="run_full_analysis",
    ):
        try:
            with st.spinner(
                "Analyse en cours — extraction CV, recherche, filtrage et matching IA…"
            ):
                analysis, notices = run_cv_analysis_pipeline(
                    pdf_bytes,
                    job_provider,
                    user_profile,
                )
            st.session_state.analysis_notices = notices
            if analysis:
                st.session_state.analysis = analysis
                st.session_state.pdf_fingerprint = current_fp
            else:
                st.session_state.analysis = None
                st.session_state.pdf_fingerprint = None
        except requests.HTTPError as exc:
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            status = exc.response.status_code if exc.response is not None else None
            st.session_state.analysis_notices = []
            if status == 401 or (body and "401" in body):
                st.session_state.adzuna_error_body = body
            else:
                st.session_state.analysis_notices = [
                    {
                        "level": "error",
                        "text": (
                            f"Erreur API emploi : {status} — {body}"
                            if status is not None
                            else str(exc)
                        ),
                    }
                ]
        except json.JSONDecodeError:
            st.session_state.analysis_notices = [
                {
                    "level": "error",
                    "text": (
                        "L'IA a renvoyé une réponse invalide lors de l'extraction du CV. "
                        "Sidebar → **Vider le cache**, puis relancez l'analyse."
                    ),
                }
            ]
        except RuntimeError as exc:
            st.session_state.analysis_notices = [
                {"level": "error", "text": str(exc)}
            ]
        except Exception as exc:  # noqa: BLE001
            error_text = str(exc)
            if (
                "API key not valid" in error_text
                or "API_KEY_INVALID" in error_text
                or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in error_text
                or "invalid authentication credentials" in error_text.lower()
            ):
                st.session_state.analysis_notices = [
                    {
                        "level": "error",
                        "text": "Clé Gemini invalide — consultez l'aide dans la sidebar.",
                    }
                ]
            else:
                st.session_state.analysis_notices = [
                    {"level": "error", "text": f"Erreur inattendue : {exc}"}
                ]
        st.rerun()

    if st.session_state.pop("adzuna_error_body", None):
        render_adzuna_auth_help(get_secret("ADZUNA_APP_ID"))

    _flush_analysis_notices()

    if fp_matches and st.session_state.analysis:
        render_analysis_results(st.session_state.analysis)


def render_app() -> None:
    """Main application shell with navigation."""
    user = st.session_state.user or {}

    with st.sidebar:
        st.header(APP_NAME)
        st.caption(f"Connecté : **{user.get('email', '')}**")

        page = st.radio(
            "Navigation",
            ["Analyse CV", "Mon profil"],
            label_visibility="collapsed",
            key="main_navigation",
        )

        if st.button("Se déconnecter", use_container_width=True, key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.analysis = None
            st.session_state.pdf_fingerprint = None
            st.rerun()

        st.markdown("---")
        st.header("Configuration")
        st.caption(f"Version : `{APP_VERSION}`")

        adzuna_id = get_secret("ADZUNA_APP_ID")
        adzuna_key = get_secret("ADZUNA_APP_KEY")
        provider_secrets = provider_secrets_from_getter(get_secret)
        serp_configured = bool(provider_secrets["serpapi_api_key"])
        jooble_configured = bool(provider_secrets["jooble_api_key"])
        careerjet_configured = bool(provider_secrets["careerjet_api_key"])
        apify_configured = bool(provider_secrets["apify_api_token"])
        has_adzuna = bool(adzuna_id and adzuna_key)
        default_provider = default_job_provider(secrets=provider_secrets)
        default_provider_index = JOB_PROVIDER_SIDEBAR_ORDER.index(default_provider)

        job_provider = st.selectbox(
            "Moteur(s) de recherche d'emploi",
            JOB_PROVIDER_SIDEBAR_ORDER,
            index=default_provider_index,
            format_func=lambda x: JOB_PROVIDER_LABELS.get(x, x),
            help=(
                "WTTJ est gratuit. Jooble et OptionCarriere nécessitent une clé API gratuite. "
                "Indeed, LinkedIn et Glassdoor passent par SerpApi. JobTeaser utilise Apify."
            ),
        )

        gemini_status, gemini_message = gemini_key_status()
        openai_configured = bool(get_secret("OPENAI_API_KEY"))
        groq_configured = bool(get_secret("GROQ_API_KEY"))
        ai_pref = get_ai_provider_preference()
        ai_ready, ai_status = ai_setup_status()
        active = resolve_llm_provider()

        st.markdown(f"**Préférence IA :** `{ai_pref}`")
        st.markdown(f"**Actif :** `{active}`")

        if ai_ready:
            st.success(ai_status)
        else:
            st.error(ai_status)

        if groq_configured:
            st.success("Groq : clé présente *(gratuit)*")
        else:
            st.warning("Groq : clé absente — [créer ici](https://console.groq.com/keys)")

        if openai_configured:
            st.info("OpenAI : clé présente *(crédits requis)*")

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
        else:
            st.caption(
                "OptionCarriere : [clé gratuite](https://www.optioncarriere.com/partners/api)"
            )

        if apify_configured:
            st.success("JobTeaser (Apify) : token présent")
        else:
            st.caption("JobTeaser : token Apify requis — [apify.com](https://apify.com/)")

        if serp_configured:
            st.success("SerpApi : clé présente *(Indeed, LinkedIn, Glassdoor, Google Jobs)*")
        else:
            st.caption("SerpApi : non configuré — [serpapi.com](https://serpapi.com/)")

        if st.button(
            "Tester Welcome to the Jungle",
            use_container_width=True,
            key="test_wttj",
        ):
            ok, message = test_wttj_connection()
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Jooble", use_container_width=True, key="test_jooble"):
            ok, message = test_jooble_connection(provider_secrets["jooble_api_key"])
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button(
            "Tester OptionCarriere",
            use_container_width=True,
            key="test_optioncarriere",
        ):
            ok, message = test_optioncarriere_connection(
                provider_secrets["careerjet_api_key"]
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester JobTeaser", use_container_width=True, key="test_jobteaser"):
            ok, message = test_jobteaser_connection(provider_secrets["apify_api_token"])
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester Indeed (SerpApi)", use_container_width=True, key="test_indeed"):
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
            key="test_linkedin",
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
            key="test_glassdoor",
        ):
            ok, message = test_serpapi_platform_connection(
                provider_secrets["serpapi_api_key"], "glassdoor"
            )
            if ok:
                st.success(message)
            else:
                st.warning(message)

        if st.button("Tester connexion Adzuna", use_container_width=True, key="test_adzuna"):
            ok, message = test_adzuna_connection()
            if ok:
                st.success(message)
            else:
                st.error(message)
                render_adzuna_auth_help(adzuna_id)

        if st.button("Tester connexion IA", use_container_width=True, key="test_ai"):
            ok, message, provider = test_ai_connection()
            if ok:
                st.success(f"{provider} — {message}")
            else:
                st.error(f"{provider} — {message}")
                if groq_configured:
                    fp = hashlib.sha256(get_secret("GROQ_API_KEY").encode()).hexdigest()[:16]
                    models = fetch_groq_model_ids(fp)
                    if models:
                        st.caption("Modèles Groq détectés : " + ", ".join(f"`{m}`" for m in models[:6]))

        if page == "Analyse CV" and st.button(
            "Vider le cache", use_container_width=True, key="clear_cache"
        ):
            st.cache_data.clear()
            st.session_state.analysis = None
            st.session_state.pdf_fingerprint = None
            st.session_state.analysis_notices = []
            st.success("Cache vidé.")
            st.rerun()

    st.title(APP_NAME)

    if page == "Mon profil":
        render_profile_page(user)
        return

    st.caption(
        f"Bienvenue **{user.get('full_name', 'Utilisateur')}** — déposez votre CV. "
        "L'IA analyse votre profil, recherche les offres et ne retient que celles "
        "correspondant à **votre contrat** et **votre zone géographique** (Mon profil)."
    )
    render_cv_analysis(job_provider, user)


def main() -> None:
    """Application entry point — auth gate then main tool."""
    init_db()
    init_session_state()

    if not st.session_state.authenticated:
        render_auth_page()
        return

    render_app()


if __name__ == "__main__":
    main()
