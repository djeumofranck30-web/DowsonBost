"""Application configuration — env first, Streamlit secrets as fallback."""

from __future__ import annotations

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
    except (KeyError, FileNotFoundError, AttributeError, ImportError):
        return default


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
