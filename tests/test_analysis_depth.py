"""Analysis depth volumes: rapide 30, standard 60, complet 100."""

from __future__ import annotations

import json
from pathlib import Path

from constants import ANALYSIS_DEPTH_POOL, ANALYSIS_DEPTH_TOP
from i18n import _load_locale_file, analysis_depth_label
from persistence import init_persistence_tables
from services.analysis_queue import enqueue_analysis_job, get_analysis_job

ROOT = Path(__file__).resolve().parents[1]


def test_depth_volumes_are_30_60_100() -> None:
    assert ANALYSIS_DEPTH_POOL == {"rapide": 30, "standard": 60, "complet": 100}
    assert ANALYSIS_DEPTH_TOP == {"rapide": 30, "standard": 60, "complet": 100}


def test_depth_labels_show_offer_counts() -> None:
    _load_locale_file.cache_clear()
    fr = json.loads((ROOT / "locales/fr.json").read_text(encoding="utf-8"))
    assert "30" in fr["depth.rapide"]
    assert "60" in fr["depth.standard"]
    assert "100" in fr["depth.complet"]
    en = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    assert "30" in en["depth.rapide"]
    assert "60" in en["depth.standard"]
    assert "100" in en["depth.complet"]
    _load_locale_file.cache_clear()
    assert "30" in analysis_depth_label("rapide")
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


def test_matching_keeps_every_analysed_offer_not_a_best_subset() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def build_matching_results(")
    end = source.index("def generate_matching_report_pdf(", start)
    body = source[start:end]
    assert "return results[:top_n]" not in body
    assert "return results, partial_matches" in body


def test_build_matching_results_returns_all_pool_offers(monkeypatch) -> None:
    import app as app_mod

    jobs = [
        {"title": f"Job {i}", "company": "Acme", "url": f"https://example.com/{i}"}
        for i in range(30)
    ]

    monkeypatch.setattr(
        app_mod,
        "rank_jobs_for_cv",
        lambda ranked_jobs, *args, **kwargs: ranked_jobs[: kwargs.get("top_n", len(ranked_jobs))],
    )
    monkeypatch.setattr(
        app_mod,
        "collect_parallel_llm_slots",
        lambda _n: [("groq", "k1"), ("groq", "k2")],
    )

    def fake_match(_cv_text, job, **_kwargs):
        idx = int(str(job["title"]).split()[-1])
        return {"score_correspondance": idx, "_fallback": True}

    monkeypatch.setattr(app_mod, "match_cv_to_job", fake_match)

    results, partial = app_mod.build_matching_results(
        jobs,
        "cv text",
        ["python"],
        top_n=10,
        pool_size=30,
    )
    assert len(results) == 30
    assert partial == 30
    scores = [int(entry["match"]["score_correspondance"]) for entry in results]
    assert scores == list(range(29, -1, -1))


def test_enqueue_rapide_stores_30_offers(sqlite_db) -> None:
    from auth import authenticate_user, register_user

    init_persistence_tables()
    ok, msg = register_user(
        "Jane Doe",
        "jane.rapide@example.com",
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
    ok_login, _, user = authenticate_user("jane.rapide@example.com", "Secret123!")
    assert ok_login and user is not None
    job_id, err = enqueue_analysis_job(
        int(user["id"]),
        {
            "id": int(user["id"]),
            "full_name": "Jane Doe",
            "email": "jane.rapide@example.com",
            "target_job_title": "Developer",
            "contract_type": "CDI",
            "country": "France",
        },
        job_provider="adzuna",
        analysis_depth="rapide",
        cv_fingerprint="fp-rapide",
        cv_text="CV texte de Jane " * 10,
    )
    assert err == ""
    stored = get_analysis_job(job_id, int(user["id"]))
    assert stored is not None
    assert stored["analysis_depth"] == "rapide"
    assert int(stored["matching_pool"]) == 30
    assert int(stored["matching_top"]) == 30
