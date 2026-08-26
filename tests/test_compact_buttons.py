"""Compact button styling is applied globally."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_theme_compacts_streamlit_buttons():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "min-height: 2rem !important" in css
    assert ".stLinkButton a" in css
    assert '[data-testid^="stBaseLinkButton-"]' in css
    assert "padding: 0.22rem 0.75rem !important" in css


def test_admin_html_buttons_are_compact():
    html = (ROOT / "admin/static/index.html").read_text(encoding="utf-8")
    assert "padding: .32rem .75rem" in html
    assert "min-height: 2rem" in html


def test_application_actions_share_a_compact_row():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "pack_col1, pack_col2 = st.columns(2)" in source
    confirm_idx = source.index('t("job.apply_manual_confirm")')
    prepare_idx = source.index('t("job.apply_manual_prepare")')
    pack_idx = source.index("pack_col1, pack_col2 = st.columns(2)")
    assert pack_idx < confirm_idx < prepare_idx
