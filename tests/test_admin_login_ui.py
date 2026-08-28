"""Admin login reuses the candidate sign-in chrome."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_login_uses_split_screen_not_inline_card():
    source = (ROOT / "pages/dashboard.py").read_text(encoding="utf-8")
    assert "render_auth_styles" in source
    assert 'id="auth-split-screen"' in source
    assert 'key="admin_login_email"' in source
    assert 'key="admin_login_password"' in source
    assert 'key="admin_login_submit"' in source
    assert "st.columns([0.94, 1.06]" in source
    assert "auth_left_panel_html" in source
    assert "auth.admin.subtitle" in source
    assert 'st.form("admin_login")' not in source
    assert "ADMIN_EMAIL" not in source
    assert "max-width:420px" not in source
    login_fn = source[source.index("def _render_login()") : source.index("def _user_label")]
    assert login_fn.index('key="admin_login_email"') < login_fn.index(
        'key="admin_login_password"'
    )
    assert login_fn.index('key="admin_login_password"') < login_fn.index(
        'key="admin_login_submit"'
    )
    assert "Créer un compte" not in login_fn
    assert "auth_go_register" not in login_fn


def test_admin_login_does_not_paint_gold_mesh_before_auth():
    source = (ROOT / "pages/dashboard.py").read_text(encoding="utf-8")
    main_fn = source[source.index("def main()") :]
    login_idx = main_fn.index("_render_login()")
    chrome_after_login = main_fn.index("_inject_admin_chrome()", login_idx)
    assert login_idx < chrome_after_login
    assert "if not user:" in main_fn


def test_admin_login_cta_shares_candidate_field_chrome():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "st-key-admin_login_submit" in css
    assert "stTextInputRootElement" in css
    assert "min-height: 3.15rem !important" in css
    chrome = (ROOT / "ui/auth_chrome.py").read_text(encoding="utf-8")
    assert "auth-illustration" in chrome
    assert "def auth_left_panel_html" in chrome


def test_admin_login_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        assert data["auth.admin.left.title"]
        assert data["auth.admin.left.tip"]
        assert data["auth.admin.subtitle"]
        assert data["auth.admin.title"]
        assert "{app_name}" in data["auth.admin.left.title"]
