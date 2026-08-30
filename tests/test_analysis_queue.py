"""CV analysis queue: click stores a ticket, a worker runs the same pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from auth import authenticate_user, register_user
from database import connect
from persistence import get_analysis, init_persistence_tables
from services.analysis_queue import (
    claim_next_analysis_job,
    enqueue_analysis_job,
    get_active_analysis_job,
    get_analysis_job,
    get_latest_analysis_job,
)
from services.analysis_worker import process_next_analysis_job

ROOT = Path(__file__).resolve().parents[1]


def _register():
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
    return int(user["id"])


def _profile():
    return {
        "id": 1,
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "target_job_title": "Developer",
        "contract_type": "CDI",
        "country": "France",
    }


def test_enqueue_survives_streamlit_rerun(sqlite_db):
    class RerunException(BaseException):
        pass

    RerunException.__module__ = "streamlit.runtime.scriptrunner_utils.exceptions"
    init_persistence_tables()
    user_id = _register()
    with pytest.raises(RerunException):
        with connect():
            job_id, err = enqueue_analysis_job(
                user_id,
                _profile(),
                job_provider="adzuna",
                analysis_depth="standard",
                cv_fingerprint="fp-rerun",
                cv_text="CV texte de Jane",
            )
            assert err == ""
            assert job_id
            raise RerunException()
    stored = get_latest_analysis_job(user_id)
    assert stored is not None
    assert stored["status"] == "queued"
    assert stored["cv_fingerprint"] == "fp-rerun"


def test_enqueue_then_claim_oldest_ticket(sqlite_db):
    init_persistence_tables()
    _register()
    job_id, err = enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="standard",
        cv_fingerprint="fp1",
        cv_text="CV texte de Jane " * 10,
        pdf_bytes=b"%PDF-fake",
        trigger_source="ui",
    )
    assert err == ""
    assert job_id
    stored = get_analysis_job(job_id, 1)
    assert stored["status"] == "queued"
    assert stored["pdf_blob"] == b"%PDF-fake"
    claimed = claim_next_analysis_job()
    assert claimed is not None
    assert int(claimed["id"]) == job_id
    assert claimed["status"] == "running"
    assert claim_next_analysis_job() is None


def test_second_enqueue_is_rejected_while_active(sqlite_db):
    init_persistence_tables()
    _register()
    first, err = enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="rapide",
        cv_fingerprint="fp1",
        cv_text="CV texte",
    )
    assert err == ""
    second, err = enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="rapide",
        cv_fingerprint="fp2",
        cv_text="Autre CV",
    )
    assert err == "already"
    assert second == first
    assert get_active_analysis_job(1)["id"] == first


def test_enqueue_requires_cv(sqlite_db):
    init_persistence_tables()
    _register()
    job_id, err = enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="standard",
        cv_fingerprint="",
    )
    assert job_id is None
    assert err == "missing_cv"


def test_worker_saves_completed_analysis(sqlite_db):
    init_persistence_tables()
    _register()
    fake = {
        "cv_text": "CV texte de Jane",
        "extraction_method": "native",
        "criteria": {"metier": "Developer"},
        "user_profile": _profile(),
        "target_job_title": "Developer",
        "search_plan": {},
        "filter_stats": {},
        "jobs_found": 1,
        "jobs_raw": 1,
        "job_provider": "adzuna",
        "results": [
            {
                "job": {
                    "title": "Backend Dev",
                    "company": "Acme",
                    "location": "Paris",
                    "url": "https://example.com/1",
                    "description": "",
                },
                "match": {"score_correspondance": 88},
            }
        ],
    }
    enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="standard",
        cv_fingerprint="fp-ok",
        cv_text="CV texte de Jane",
        pdf_bytes=b"%PDF-fake",
    )
    with patch(
        "services.pipeline.run_cv_analysis_pipeline",
        return_value=(fake, [{"level": "info", "text": "ok"}]),
    ):
        assert process_next_analysis_job() is True
    job = get_latest_analysis_job(1)
    assert job["status"] == "completed"
    assert job["analysis_id"]
    assert job.get("pdf_blob") in (None, b"")
    stored = get_analysis(1, int(job["analysis_id"]))
    assert stored is not None
    assert stored["results"][0]["match"]["score_correspondance"] == 88
    assert get_active_analysis_job(1) is None


def test_worker_survives_progress_database_blip(sqlite_db):
    init_persistence_tables()
    _register()
    fake = {
        "cv_text": "CV texte de Jane",
        "extraction_method": "native",
        "criteria": {"metier": "Developer"},
        "user_profile": _profile(),
        "target_job_title": "Developer",
        "search_plan": {},
        "filter_stats": {},
        "jobs_found": 1,
        "jobs_raw": 1,
        "job_provider": "adzuna",
        "results": [
            {
                "job": {
                    "title": "Backend Dev",
                    "company": "Acme",
                    "location": "Paris",
                    "url": "https://example.com/1",
                    "description": "",
                },
                "match": {"score_correspondance": 88},
            }
        ],
    }
    enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="standard",
        cv_fingerprint="fp-blip",
        cv_text="CV texte de Jane",
    )

    def _pipeline(_pdf, _provider, _profile, **kwargs):
        progress = kwargs.get("progress")
        if progress:
            progress(10, "Recherche…")
        return fake, [{"level": "info", "text": "ok"}]

    with (
        patch(
            "services.pipeline.run_cv_analysis_pipeline",
            side_effect=_pipeline,
        ),
        patch(
            "services.analysis_worker.update_analysis_job_progress",
            side_effect=RuntimeError(
                "Connexion PostgreSQL impossible (hôte=pooler port=6543 user=postgres db=postgres)"
            ),
        ),
    ):
        assert process_next_analysis_job() is True
    job = get_latest_analysis_job(1)
    assert job["status"] == "completed"
    assert job["analysis_id"]


def test_worker_marks_empty_pipeline_as_failed(sqlite_db):
    init_persistence_tables()
    _register()
    enqueue_analysis_job(
        1,
        _profile(),
        job_provider="adzuna",
        analysis_depth="standard",
        cv_fingerprint="fp-empty",
        cv_text="CV texte",
    )
    with patch(
        "services.pipeline.run_cv_analysis_pipeline",
        return_value=(None, [{"level": "warning", "text": "Aucune offre"}]),
    ):
        assert process_next_analysis_job() is True
    job = get_latest_analysis_job(1)
    assert job["status"] == "failed"
    assert "offre" in (job.get("error_message") or "").lower() or job.get("error_message")


def test_analysis_ui_enqueues_instead_of_blocking():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    fn = source[
        source.index("def render_cv_analysis(") : source.index("def render_config_tests_panel")
    ]
    assert "enqueue_analysis_job" in fn
    assert 'key="run_full_analysis"' in fn
    assert "_render_analysis_job_progress" in fn
    button_block = fn[fn.index('key="run_full_analysis"') :]
    assert "run_cv_analysis_pipeline" not in button_block


def test_progress_ui_hides_ticket_number():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def _render_analysis_job_progress(")
    end = source.index("def _format_history_datetime(", start)
    body = source[start:end]
    assert "analysis.queue.ticket" not in body
    assert "Ticket n" not in body
    assert "analysis.progress.working" in body
    assert "st.caption" not in body


def test_queue_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        for key in (
            "analysis.queue.queued",
            "analysis.queue.running",
            "analysis.queue.already",
            "analysis.queue.failed",
            "analysis.progress.working",
        ):
            assert data[key]
        assert "ticket" not in data["analysis.queue.queued"].lower()
        assert "ticket" not in data["analysis.progress.working"].lower()
