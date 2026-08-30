"""Honest apply UX: 3-step register, no job-board password, depth caps."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_register_wizard_keeps_six_steps() -> None:
    source = _read("app.py")
    start = source.index("REGISTER_WIZARD_STEPS = (")
    end = source.index(")", start)
    body = source[start : end + 1]
    assert body.count("auth.register.wizard.") == 6
    assert "auth.register.wizard.language" in body
    assert "auth.register.wizard.countries" in body
    assert "auth.register.wizard.identity" in body
    assert "auth.register.wizard.job" in body
    assert "auth.register.wizard.location" in body
    assert "auth.register.wizard.preferences" in body


def test_job_board_connect_form_does_not_ask_password() -> None:
    source = _read("app.py")
    start = source.index("def render_connected_accounts_section(")
    end = source.index("def _profile_header_chips(", start)
    body = source[start:end]
    assert "accounts.login_password" not in body
    assert "connect_password" not in body
    assert "accounts.login_id" in body


def test_depth_labels_are_caps_not_guarantees() -> None:
    fr = json.loads(_read("locales/fr.json"))
    en = json.loads(_read("locales/en.json"))
    assert "jusqu'à 25" in fr["depth.rapide"]
    assert "jusqu'à 60" in fr["depth.standard"]
    assert "jusqu'à 100" in fr["depth.complet"]
    assert "up to 25" in en["depth.rapide"]
    assert "up to 100" in en["depth.complet"]
    assert "plafond" in fr["app.analysis_depth_help"].lower()


def test_apply_auto_label_is_honest() -> None:
    fr = json.loads(_read("locales/fr.json"))
    en = json.loads(_read("locales/en.json"))
    assert "automatiquement" not in fr["job.apply_auto"].lower()
    assert "préparer" in fr["job.apply_auto"].lower()
    assert "automatically" not in en["job.apply_auto"].lower()
    assert "prepare" in en["job.apply_auto"].lower()
    assert "j'ai postulé" in fr["job.apply_manual_confirm"].lower()
