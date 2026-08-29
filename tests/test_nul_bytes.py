"""PostgreSQL rejects U+0000 in text fields; persist paths must strip it."""

from __future__ import annotations

from auth import authenticate_user, register_user
from persistence import (
    _db_text,
    _json_dumps,
    get_analysis,
    get_analysis_result,
    init_persistence_tables,
    save_analysis,
    strip_nul_bytes,
    upsert_active_cv_document,
)
from services.analysis_queue import enqueue_analysis_job, get_analysis_job


def _register(email: str = "jane.nul@example.com") -> int:
    ok, msg = register_user(
        "Jane Doe",
        email,
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
    ok_login, _, user = authenticate_user(email, "Secret123!")
    assert ok_login and user is not None
    return int(user["id"])


def test_strip_nul_bytes_from_nested_payload() -> None:
    cleaned = strip_nul_bytes(
        {
            "title": "Dev\x00Ops",
            "lines": ["hello\x00", {"note": "a\x00b"}],
        }
    )
    assert cleaned == {"title": "DevOps", "lines": ["hello", {"note": "ab"}]}
    assert "\x00" not in _json_dumps({"description": "Hello\x00World"})
    assert "HelloWorld" in _json_dumps({"description": "Hello\x00World"})
    assert _db_text("CV\x00 texte") == "CV texte"


def test_save_analysis_strips_nul_from_cv_and_job_text(sqlite_db) -> None:
    init_persistence_tables()
    user_id = _register()
    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "Mon CV\x00 PDF",
            "criteria": {"metier": "Dev\x00eloper"},
            "user_profile": {"full_name": "Jane\x00 Doe"},
            "target_job_title": "Dev\x00eloper",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 3,
            "search_strategy": "demo\x00",
            "search_query_used": "Developer\x00",
            "job_provider": "adzuna",
            "results": [
                {
                    "job": {
                        "title": "Ingénieur\x00 Python",
                        "company": "Acme",
                        "url": "https://example.com/1",
                        "description": "Mission\x00 fullstack",
                    },
                    "match": {
                        "score_correspondance": 88,
                        "synthese_ats": "Bon\x00 match",
                    },
                }
            ],
        },
        cv_fingerprint="nul-demo",
    )
    stored = get_analysis(user_id, analysis_id)
    assert stored is not None
    assert "\x00" not in stored["cv_text"]
    assert stored["cv_text"] == "Mon CV PDF"
    assert stored["target_job_title"] == "Developer"
    assert stored["criteria"]["metier"] == "Developer"
    result = get_analysis_result(user_id, stored["results"][0]["result_id"])
    assert result is not None
    assert result["job"]["title"] == "Ingénieur Python"
    assert result["job"]["description"] == "Mission fullstack"
    assert result["match"]["synthese_ats"] == "Bon match"


def test_enqueue_and_cv_document_strip_nul(sqlite_db) -> None:
    init_persistence_tables()
    user_id = _register("jane.nul.queue@example.com")
    upsert_active_cv_document(user_id, "fp\x00cv", "Texte\x00 CV", {"metier": "Dev\x00"})
    job_id, err = enqueue_analysis_job(
        user_id,
        {"id": user_id, "full_name": "Jane\x00", "target_job_title": "Dev"},
        job_provider="adzuna",
        analysis_depth="rapide",
        cv_fingerprint="fp\x00cv",
        cv_text="CV avec\x00 NUL",
    )
    assert err == ""
    stored = get_analysis_job(job_id, user_id)
    assert stored is not None
    assert stored["cv_text"] == "CV avec NUL"
    assert "\x00" not in stored["cv_text"]
    assert stored["cv_fingerprint"] == "fpcv"
    profile = stored.get("user_profile_json") or {}
    assert profile["full_name"] == "Jane"
