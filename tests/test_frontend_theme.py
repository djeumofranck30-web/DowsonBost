"""Frontend visual language."""

from __future__ import annotations

from pathlib import Path

from ui.theme import THEME

ROOT = Path(__file__).resolve().parents[1]


def test_theme_uses_saas_palette():
    assert THEME["primary"] == "#2563EB"
    assert THEME["primary_dark"] == "#1E3A8A"
    assert THEME["primary_deep"] == "#1E3A8A"
    assert THEME["surface"] == "#FFFFFF"
    assert THEME["surface_soft"] == "#F3F4F6"
    assert THEME["muted"] == "#374151"
    assert THEME["success"] == "#10B981"
    assert THEME["danger"] == "#EF4444"
    assert THEME["accent"] == "#2563EB"
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#2563EB"' in config
    assert 'backgroundColor = "#FFFFFF"' in config
    assert "#7c3aed" not in config
    assert "#0E7490" not in config
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert 'accent-color: {t["primary"]}' in css or "accent-color:" in css
    assert "[data-baseweb=\"tag\"]" in css


def test_theme_has_saas_buttons_and_motion():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "@keyframes db-rise" in css
    assert "@keyframes db-shine" in css
    assert "@keyframes db-skeleton" in css
    assert "min-height: 48px !important" in css
    assert "border-radius: 8px !important" in css
    assert "padding: 14px 22px !important" in css
    assert "animation: db-rise" in css
    assert "cursor: pointer !important" in css
    assert "scale(0.98)" in css
    button_css = css.split("/* —— Buttons")[1].split("/* —— Inputs")[0]
    assert "overflow: hidden" not in button_css
    assert "::after" not in button_css


def test_admin_and_auth_follow_the_saas_palette():
    admin = (ROOT / "admin/static/index.html").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "--violet: #2563EB" in admin
    assert "#7c3aed" not in admin
    assert "#0E7490" not in admin
    assert 'fill="#1E3A8A"' in app
    assert 'fill="#2563EB"' in app
