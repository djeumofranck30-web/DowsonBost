"""Student control centre: duplicates, follow-up, honest apply."""

from __future__ import annotations

import json
from pathlib import Path

from persistence import normalize_company_name

ROOT = Path(__file__).resolve().parents[1]


def test_normalize_company_name_folds_legal_suffix() -> None:
    assert normalize_company_name("Foo SAS") == normalize_company_name("Foo")
    assert normalize_company_name("Société Générale") == "societe generale"
    assert normalize_company_name("") == ""


def test_student_control_locale_and_ui() -> None:
    fr = json.loads((ROOT / "locales/fr.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    for key in (
        "overview.control_title",
        "overview.kpi_found",
        "overview.kpi_applied",
        "overview.kpi_waiting",
        "overview.kpi_rejected",
        "overview.kpi_offer",
        "overview.followup_banner",
        "overview.student_plan",
        "job.apply_duplicate",
        "profile.freelance_mode",
        "profile.search_mode",
    ):
        assert fr[key].strip(), key
        assert en[key].strip(), key
    assert "{company}" in fr["job.apply_duplicate"]
    assert "ne postule pas" in fr["overview.student_plan"].lower()
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "control_center_counts" in source
    assert "already_applied_to_company" in source
    assert "applications_needing_followup" in source
    assert "profile.search_mode" in source
