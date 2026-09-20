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


def test_profile_job_sites_open_inside_expander() -> None:
    source = _read("app.py")
    start = source.index("def render_connected_accounts_section(")
    end = source.index("def _profile_header_chips(", start)
    body = source[start:end]
    assert "job_board_access_url" in body
    assert "accounts.open_site" in body
    assert body.index("with st.expander") < body.index("accounts.open_site")
    assert "st.columns" not in body


def test_open_site_locale_keys() -> None:
    fr = json.loads(_read("locales/fr.json"))
    en = json.loads(_read("locales/en.json"))
    assert "{name}" in fr["accounts.open_site"]
    assert "ouvrir" in fr["accounts.open_site"].lower()
    assert "{name}" in en["accounts.open_site"]
    assert "open" in en["accounts.open_site"].lower()
    assert "dépliez" in fr["accounts.hint"].lower()


def test_every_connectable_site_has_https_access_url() -> None:
    from job_providers import CONNECTABLE_JOB_PROVIDERS, job_board_access_url

    for provider in CONNECTABLE_JOB_PROVIDERS:
        url = job_board_access_url(provider)
        assert url, provider
        assert url.startswith("https://"), provider


def test_depth_labels_are_caps_not_guarantees() -> None:
    fr = json.loads(_read("locales/fr.json"))
    en = json.loads(_read("locales/en.json"))
    assert "jusqu'à 25" in fr["depth.rapide"]
    assert "jusqu'à 60" in fr["depth.standard"]
    assert "jusqu'à 100" in fr["depth.complet"]
    assert "jusqu'à 150" in fr["depth.etendu"]
    assert "up to 25" in en["depth.rapide"]
    assert "up to 100" in en["depth.complet"]
    assert "up to 150" in en["depth.etendu"]
    assert "plafond" in fr["app.analysis_depth_help"].lower()


def test_apply_auto_label_is_honest() -> None:
    fr = json.loads(_read("locales/fr.json"))
    en = json.loads(_read("locales/en.json"))
    source = _read("app.py")
    assert fr["job.apply_auto"].lower() == "postuler automatiquement"
    assert fr["job.apply_manual"].lower() == "postuler manuellement"
    assert "hunter" in fr["job.apply_auto_help"].lower()
    assert "e-mail" in fr["job.apply_auto_help"].lower()
    assert "notifi" in fr["job.apply_auto_help"].lower()
    assert "hunter" in en["job.apply_auto_help"].lower()
    assert "e-mail" in en["job.apply_auto_help"].lower()
    assert 't("job.apply_auto")' in source
    assert 't("job.apply_manual")' in source
    assert "def _render_apply_action_buttons(" in source
    assert "_pending_auto_apply" in source
    assert "can_apply = bool(user_id and cv_text and user_profile)" in source
    assert "auto_prepared" in source
    assert "job.apply_unexpected" in fr
    assert "job.apply_unexpected" in en
    assert 't("job.hunter_lookup")' not in source
    assert 't("job.apply_manual_confirm")' not in source
    assert "open_job_listing_tab(" not in source.split("def open_job_listing_tab")[-1]
