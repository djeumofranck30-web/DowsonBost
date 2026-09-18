"""FastAPI stays optional; Streamlit Cloud stays in-process (faster clicks)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_imports_data_from_frontend_store():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from services.frontend_store import" in source
    assert "authenticate_user" in source
    auth_block = source[source.index("from auth import") : source.index("from database import")]
    assert "authenticate_user" not in auth_block
    assert "register_user" not in auth_block
    persist_block = source[
        source.index("from persistence import") : source.index("from ui.theme import")
    ]
    assert "list_analyses" not in persist_block
    assert "list_dashboard_results" not in persist_block
    assert "record_application" not in persist_block


def test_streamlit_skips_http_without_api_base_url():
    from services.frontend_store import backend_uses_http, ensure_backend

    ensure_backend()
    assert backend_uses_http() is False


def test_config_exposes_api_base_url():
    from config import get_api_base_url, get_embedded_api_port

    assert get_embedded_api_port() == 8765
    assert get_api_base_url() == ""
