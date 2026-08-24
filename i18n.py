"""UI internationalization — 40+ languages via JSON locale files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_MANIFEST_PATH = _LOCALES_DIR / "manifest.json"

_DEFAULT_MANIFEST: dict[str, Any] = {
    "default": "fr",
    "fallback": "en",
    "locales": {"fr": "Français", "en": "English"},
}

try:
    with _MANIFEST_PATH.open(encoding="utf-8") as _manifest_file:
        _MANIFEST = json.load(_manifest_file)
except (FileNotFoundError, json.JSONDecodeError, OSError):
    _MANIFEST = _DEFAULT_MANIFEST

DEFAULT_LOCALE: str = _MANIFEST.get("default", "fr")
FALLBACK_LOCALE: str = _MANIFEST.get("fallback", "en")
LOCALE_LABELS: dict[str, str] = dict(_MANIFEST.get("locales", {}))
SUPPORTED_LOCALES: tuple[str, ...] = tuple(LOCALE_LABELS.keys())

_LOCALE_ALIASES: dict[str, str] = {
    "fr-fr": "fr",
    "fr_fr": "fr",
    "en-us": "en",
    "en-gb": "en",
    "en_us": "en",
    "en_gb": "en",
    "pt-br": "pt",
    "pt_br": "pt",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh_cn": "zh",
    "nb": "no",
    "nn": "no",
    "iw": "he",
}


@lru_cache(maxsize=64)
def _load_locale_file(code: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{code}.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(k): str(v) for k, v in data.items()}


def normalize_locale(value: str | None) -> str:
    raw = (value or DEFAULT_LOCALE).strip().lower().replace("_", "-")
    if raw in _LOCALE_ALIASES:
        raw = _LOCALE_ALIASES[raw]
    if raw in LOCALE_LABELS:
        return raw
    primary = raw.split("-")[0]
    if primary in LOCALE_LABELS:
        return primary
    if primary == "en":
        return "en"
    return DEFAULT_LOCALE


def get_locale() -> str:
    try:
        import streamlit as st

        stored = st.session_state.get("locale")
        if stored:
            return normalize_locale(str(stored))
        user = st.session_state.get("user")
        if isinstance(user, dict) and user.get("preferred_language"):
            return normalize_locale(str(user["preferred_language"]))
        query_lang = st.query_params.get("lang")
        if isinstance(query_lang, list):
            query_lang = query_lang[0] if query_lang else ""
        if query_lang:
            return normalize_locale(str(query_lang))
    except Exception:
        pass
    return DEFAULT_LOCALE


def set_locale(locale: str) -> str:
    locale = normalize_locale(locale)
    try:
        import streamlit as st

        st.session_state.locale = locale
        st.query_params["lang"] = locale
    except Exception:
        pass
    return locale


def init_locale() -> str:
    locale = get_locale()
    try:
        import streamlit as st

        st.session_state.locale = locale
    except Exception:
        pass
    return locale


def _lookup(key: str, lang: str) -> str | None:
    for code in (lang, FALLBACK_LOCALE, DEFAULT_LOCALE):
        value = _load_locale_file(code).get(key)
        if value:
            return value
    return None


def t(key: str, *, locale: str | None = None, **kwargs: Any) -> str:
    lang = normalize_locale(locale or get_locale())
    template = _lookup(key, lang) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


def nav_label(page_key: str) -> str:
    return t(f"nav.{page_key}")


def geo_mode_label(mode: str, *, register: bool = False) -> str:
    prefix = "geo_mode.register." if register else "geo_mode."
    return t(f"{prefix}{mode}")


def experience_label(level: str) -> str:
    return t(f"experience.{level}")


def job_age_label(days: int) -> str:
    return t(f"job_age.{days}")


def analysis_depth_label(depth: str) -> str:
    return t(f"depth.{depth}")


def application_status_label(status: str) -> str:
    return t(f"status.{status}")


def application_method_label(method: str | None) -> str:
    if not method:
        return t("apply_method.unknown")
    return t(f"apply_method.{method}")


def weekday_label(day: str) -> str:
    return t(f"weekday.{day}")


def job_provider_label(provider: str) -> str:
    key_map = {
        "all": "provider.all",
        "adzuna": "provider.adzuna",
        "wttj": "provider.wttj",
        "jobteaser": "provider.jobteaser",
        "hellowork": "provider.hellowork",
        "jooble": "provider.jooble",
        "optioncarriere": "provider.optioncarriere",
        "indeed": "provider.indeed",
        "linkedin": "provider.linkedin",
        "glassdoor": "provider.glassdoor",
        "monster": "provider.monster",
        "talent": "provider.talent",
        "serpapi": "provider.serpapi",
    }
    return t(key_map.get(provider, f"provider.{provider}"))


def contract_label(contract: str) -> str:
    return t(f"contract.{contract}")


def sector_label(sector: str) -> str:
    return t(f"sector.{sector}")


def sort_label(sort_key: str) -> str:
    return t(f"sort.{sort_key}")


def published_label(days: int | None = None, *, unknown: bool = False) -> str:
    if unknown or days is None:
        return t("published.unknown")
    if days == 0:
        return t("published.today")
    if days == 1:
        return t("published.yesterday")
    return t("published.days_ago", days=days)
