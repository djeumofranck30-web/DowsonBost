"""Login page uses a stacked 2026 form layout inside the card."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_login_form_stacks_actions_inside_the_card():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "auth-forgot-row-marker" in source
    assert "auth-signup-row-marker" in source
    assert "_forgot_spacer" not in source
    assert 'id="auth-create-between-marker"' not in source
    assert 'key="auth_go_register"' in source
    assert 'key="auth_login_submit"' in source
    assert 'key="auth_go_reset"' in source
    forgot_idx = source.index('key="auth_go_reset"')
    submit_idx = source.index('key="auth_login_submit"')
    create_idx = source.index('key="auth_go_register"')
    login_fn_idx = source.index("def _render_auth_login_form()")
    render_page_idx = source.index("def render_auth_page()")
    assert login_fn_idx < forgot_idx < submit_idx < create_idx < render_page_idx
    assert source.index('t("auth.footer.no_account")') < create_idx


def test_auth_styles_drop_overlay_and_size_the_primary_cta():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "auth-create-between-marker" not in css
    assert "auth-lang-pulse" not in css
    assert "st-key-auth_login_submit" in css
    assert "min-height: 2.9rem !important" in css
    assert "border-radius: 14px !important" in css
    assert "auth-signup-row-marker" in css
    assert "st-key-auth_go_register" in css
    assert 'data-testid="stColumn"' in css
    assert "has(#auth-split-screen)" in css
    assert "stLayoutWrapper" in css
    assert "stElementContainer" in css


def test_auth_footer_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        assert data["auth.footer.no_account"]
        assert data["auth.footer.create"]
        assert data["auth.login.submit"]
        assert data["auth.login.forgot"]
