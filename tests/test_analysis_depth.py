"""Analysis depth volumes: rapide 25, standard 60, complet 100."""

from __future__ import annotations

import json
from pathlib import Path

from constants import ANALYSIS_DEPTH_POOL, ANALYSIS_DEPTH_TOP
from i18n import _load_locale_file, analysis_depth_label
from persistence import init_persistence_tables
from services.analysis_queue import enqueue_analysis_job, get_analysis_job

ROOT = Path(__file__).resolve().parents[1]


def test_depth_volumes_are_25_60_100() -> None:
    assert ANALYSIS_DEPTH_POOL == {"rapide": 25, "standard": 60, "complet": 100}
    assert ANALYSIS_DEPTH_TOP == {"rapide": 25, "standard": 60, "complet": 100}


def test_depth_labels_show_offer_counts() -> None:
    _load_locale_file.cache_clear()
    fr = json.loads((ROOT / "locales/fr.json").read_text(encoding="utf-8"))
    assert "25" in fr["depth.rapide"]
    assert "60" in fr["depth.standard"]
    assert "100" in fr["depth.complet"]
    en = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    assert "25" in en["depth.rapide"]
    assert "60" in en["depth.standard"]
    assert "100" in en["depth.complet"]
    _load_locale_file.cache_clear()
    assert "25" in analysis_depth_label("rapide")
    assert "60" in analysis_depth_label("standard")
    assert "100" in analysis_depth_label("complet")


def test_enqueue_stores_depth_pool_and_top(sqlite_db) -> None:
    from auth import authenticate_user, register_user

    init_persistence_tables()
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok_login, _, user = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login and user is not None
    profile = {
        "id": int(user["id"]),
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "target_job_title": "Developer",
        "contract_type": "CDI",
        "country": "France",
    }
    job_id, err = enqueue_analysis_job(
        int(user["id"]),
        profile,
        job_provider="adzuna",
        analysis_depth="complet",
        cv_fingerprint="fp",
        cv_text="CV texte de Jane " * 10,
    )
    assert err == ""
    stored = get_analysis_job(job_id, int(user["id"]))
    assert stored is not None
    assert stored["analysis_depth"] == "complet"
    assert int(stored["matching_pool"]) == 100
    assert int(stored["matching_top"]) == 100


def test_ui_starts_analysis_immediately() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "kick_embedded_analysis_worker()" in source
    worker = (ROOT / "services/analysis_worker.py").read_text(encoding="utf-8")
    assert "def kick_embedded_analysis_worker" in worker
    assert "idle_sleep: float = 0.25" in worker
