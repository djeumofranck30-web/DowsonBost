"""Frontend visual language."""

from __future__ import annotations

from pathlib import Path

from ui.theme import THEME

ROOT = Path(__file__).resolve().parents[1]


def test_theme_uses_career_platform_palette():
    assert THEME["primary"] == "#0E7490"
    assert THEME["accent"] == "#E8B923"
    assert THEME["primary_deep"] == "#0B1220"
    assert "7c3aed" not in THEME["primary"]
    assert "F4F1EA" in THEME["bg_gradient"]


def test_theme_has_motion_and_compact_buttons():
    css = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "@keyframes db-rise" in css
    assert "@keyframes db-shine" in css
    assert "min-height: 2rem !important" in css
    assert "border-radius: 999px !important" in css
    assert "animation: db-rise" in css


def test_admin_and_auth_follow_the_new_palette():
    admin = (ROOT / "admin/static/index.html").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "--violet: #0E7490" in admin
    assert "#7c3aed" not in admin
    assert 'fill="#155E75"' in app
    assert 'color="#0E7490"' in app
