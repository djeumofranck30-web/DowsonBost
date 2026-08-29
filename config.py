"""Application configuration — env first, Streamlit secrets as fallback."""

from __future__ import annotations

import json
import os
from typing import Any


def normalize_secret(value: Any) -> str:
    """Strip whitespace and surrounding quotes from secret values."""
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'").strip()


def get_secret_raw(key: str, default: Any = "") -> Any:
    """Read a secret without forcing to a single string (supports TOML arrays)."""
    env_value = os.getenv(key)
    if env_value is not None and str(env_value).strip():
        return env_value
    try:
        import streamlit as st

        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError, ImportError, RuntimeError):
        return default


_secrets_exported = False


def export_streamlit_secrets_to_environ() -> int:
    """Copy Streamlit secrets into os.environ for background worker threads.

    ``st.secrets`` is unreliable from a daemon thread (no ScriptRunContext).
    Call this on the Streamlit request thread before starting the analysis worker.
    """
    global _secrets_exported
    if _secrets_exported:
        return 0
    copied = 0
    secrets: Any = None
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:  # noqa: BLE001 — secrets are optional in local/CLI workers
        secrets = None
    if secrets is None:
        return 0

    keys: list[str] = []
    try:
        keys.extend(str(key) for key in secrets.keys())
    except Exception:  # noqa: BLE001
        keys = []
    for fallback in (
        "DATABASE_URL",
        "DATABASE_PASSWORD",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "AI_PROVIDER",
        "ADZUNA_APP_ID",
        "ADZUNA_APP_KEY",
        "SERPAPI_API_KEY",
        "JOOBLE_API_KEY",
        "CAREERJET_API_KEY",
        "APIFY_API_TOKEN",
        "RESEND_API_KEY",
    ):
        if fallback not in keys:
            keys.append(fallback)

    for key in keys:
        if str(os.environ.get(key) or "").strip():
            continue
        try:
            raw = secrets[key]
        except Exception:  # noqa: BLE001
            continue
        if isinstance(raw, dict):
            continue
        if isinstance(raw, list):
            text = normalize_secret(str(raw[0])) if raw else ""
        else:
            text = normalize_secret(raw)
        if not text:
            continue
        os.environ[key] = text
        copied += 1
    _secrets_exported = True
    return copied


def get_secret(key: str, default: str = "") -> str:
    """Read from environment first, then Streamlit secrets."""
    raw = get_secret_raw(key, default)
    if isinstance(raw, list):
        return normalize_secret(str(raw[0])) if raw else default
    return normalize_secret(raw)


def get_database_url() -> str:
    return get_secret("DATABASE_URL", "")


def get_database_password() -> str:
    return get_secret("DATABASE_PASSWORD", "")


def get_jwt_secret() -> str:
    return get_secret("JWT_SECRET", get_secret("SECRET_KEY", "change-me-in-production"))


def get_app_base_url() -> str:
    return get_secret("APP_BASE_URL", "http://localhost:8501").rstrip("/")


def _as_secret_list(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


def get_admin_emails() -> frozenset[str]:
    """Admin e-mails configured in secrets (passwords are required separately)."""
    return frozenset(email for email, _password in get_admin_accounts())


def get_admin_accounts() -> list[tuple[str, str]]:
    """Admin login pairs from Streamlit secrets / env: e-mail + password.

    Supported formats:
    - ADMIN_EMAIL + ADMIN_PASSWORD
    - ADMIN_EMAILS = ["a@x.com"] and ADMIN_PASSWORDS = ["secret"] (same order)
    - ADMIN_ACCOUNTS = [{email = "...", password = "..."}]
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(email: str, password: str) -> None:
        cleaned_email = normalize_secret(email).lower()
        cleaned_password = str(password or "").strip()
        if not cleaned_email or "@" not in cleaned_email or not cleaned_password:
            return
        if cleaned_email in seen:
            pairs[:] = [(e, p) for e, p in pairs if e != cleaned_email]
        seen.add(cleaned_email)
        pairs.append((cleaned_email, cleaned_password))

    raw_accounts = get_secret_raw("ADMIN_ACCOUNTS", "")
    if isinstance(raw_accounts, str) and raw_accounts.strip().startswith("["):
        try:
            raw_accounts = json.loads(raw_accounts)
        except json.JSONDecodeError:
            raw_accounts = []
    if isinstance(raw_accounts, list):
        for item in raw_accounts:
            if isinstance(item, dict):
                _add(
                    str(item.get("email") or item.get("EMAIL") or ""),
                    str(item.get("password") or item.get("PASSWORD") or ""),
                )

    emails = [normalize_secret(item).lower() for item in _as_secret_list(get_secret_raw("ADMIN_EMAILS", ""))]
    emails = [email for email in emails if email and "@" in email]
    passwords = [str(item).strip() for item in _as_secret_list(get_secret_raw("ADMIN_PASSWORDS", ""))]
    for email, password in zip(emails, passwords):
        _add(email, password)

    _add(get_secret("ADMIN_EMAIL", ""), get_secret("ADMIN_PASSWORD", ""))
    return pairs
