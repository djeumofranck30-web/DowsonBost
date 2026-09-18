"""Hunter.io recruiter e-mail lookup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from services.application import extract_apply_email, resolve_apply_email
from services.hunter import (
    clear_hunter_cache,
    find_recruiter_email,
    infer_company_domain,
    is_job_board_or_ats_host,
    pick_recruiter_email,
)

ROOT = Path(__file__).resolve().parents[1]

HUNTER_PAYLOAD = {
    "data": {
        "domain": "acme.fr",
        "emails": [
            {
                "value": "jean.dupont@acme.fr",
                "type": "personal",
                "confidence": 94,
                "department": "sales",
                "position": "Account Executive",
            },
            {
                "value": "jobs@acme.fr",
                "type": "generic",
                "confidence": 88,
                "department": "hr",
                "position": None,
            },
        ],
    }
}


def test_infer_domain_skips_job_boards() -> None:
    assert is_job_board_or_ats_host("www.indeed.fr")
    assert is_job_board_or_ats_host("boards.greenhouse.io")
    assert infer_company_domain(
        {"url": "https://www.indeed.fr/viewjob?jk=abc", "company": "Acme"}
    ) is None
    assert infer_company_domain({"company_url": "https://www.acme.fr/jobs/1"}) == "acme.fr"
    assert infer_company_domain({"website": "acme.fr"}) == "acme.fr"


def test_pick_recruiter_email_prefers_hr_generic() -> None:
    assert pick_recruiter_email(HUNTER_PAYLOAD) == "jobs@acme.fr"
    assert pick_recruiter_email({"data": {"emails": []}}) is None
    personal_only = {
        "data": {
            "emails": [
                {
                    "value": "jean.dupont@acme.fr",
                    "type": "personal",
                    "confidence": 99,
                    "department": "sales",
                }
            ]
        }
    }
    assert pick_recruiter_email(personal_only) is None


def test_find_recruiter_email_calls_hunter_and_caches() -> None:
    clear_hunter_cache()
    job = {"company": "Acme", "company_url": "https://www.acme.fr"}
    with patch("services.hunter._hunter_get", return_value=HUNTER_PAYLOAD) as mocked:
        first = find_recruiter_email(job, api_key="hunter-test")
        second = find_recruiter_email(job, api_key="hunter-test")
    assert first == "jobs@acme.fr"
    assert second == "jobs@acme.fr"
    assert mocked.call_count == 1
    params = mocked.call_args.args[0]
    assert params["domain"] == "acme.fr"
    assert params["department"] == "hr"
    clear_hunter_cache()


def test_resolve_apply_email_prefers_listing_over_hunter() -> None:
    job = {
        "description": "Envoyez à recrutement@acme.fr",
        "company": "Acme",
        "company_url": "https://www.acme.fr",
    }
    with patch("services.hunter.find_recruiter_email", return_value="jobs@acme.fr") as mocked:
        assert extract_apply_email(job) == "recrutement@acme.fr"
        assert resolve_apply_email(job) == "recrutement@acme.fr"
        mocked.assert_not_called()


def test_resolve_apply_email_falls_back_to_hunter() -> None:
    job = {
        "description": "Postulez en ligne.",
        "company": "Acme",
        "company_url": "https://www.acme.fr",
        "url": "https://www.indeed.fr/viewjob?jk=1",
    }
    with patch("services.hunter.find_recruiter_email", return_value="jobs@acme.fr"):
        assert extract_apply_email(job) is None
        assert resolve_apply_email(job) == "jobs@acme.fr"


def test_submit_uses_hunter_when_listing_has_no_email() -> None:
    from unittest.mock import patch as _patch
    from services.application import submit_application_automatically

    job = {
        "title": "Dev Python",
        "company": "Acme",
        "location": "Paris",
        "description": "Mission intéressante sans e-mail.",
        "url": "https://www.acme.fr/jobs/1",
        "company_url": "https://www.acme.fr",
    }
    user = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "target_job_title": "Dev Python",
    }

    def fake_llm(_system: str, _user: str, **kwargs: object) -> str:
        return "Document généré."

    with (
        _patch("services.application.resolve_apply_email", return_value="jobs@acme.fr"),
        _patch("services.application.email_configured", return_value=True),
        _patch("services.application.send_application_email", return_value=(True, "ok")),
        _patch("services.application.notify_candidate_application", return_value=True),
    ):
        result = submit_application_automatically(
            "CV source",
            job,
            {"score_correspondance": 80},
            user,
            llm_call=fake_llm,
        )
    assert result["success"] is True
    assert result["method"] == "email"
    assert result["apply_email"] == "jobs@acme.fr"


def test_hunter_ui_and_secret_hooks() -> None:
    fr = json.loads((ROOT / "locales/fr.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    for key in (
        "job.hunter_lookup",
        "job.recruiter_email_hunter",
        "job.hunter_not_found",
    ):
        assert fr[key].strip(), key
        assert en[key].strip(), key
    assert "Hunter" in fr["job.apply_auto_help"]
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "find_recruiter_email" in source
    assert "hunter_configured" in source
    assert "resolve_apply_email" in (ROOT / "services/application.py").read_text(encoding="utf-8")
    secrets = (ROOT / ".streamlit/secrets.toml.example").read_text(encoding="utf-8")
    assert "HUNTER_API_KEY" in secrets
    config = (ROOT / "config.py").read_text(encoding="utf-8")
    assert "HUNTER_API_KEY" in config
