"""Hunter.io recruiter e-mail lookup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from services.application import (
    extract_apply_email,
    extract_apply_email_from_pages,
    resolve_apply_email,
)
from services.hunter import (
    clean_company_name,
    clear_hunter_cache,
    company_slug_from_job,
    domain_from_company_name,
    find_recruiter_email,
    infer_company_domain,
    is_job_board_or_ats_host,
    mailbox_domain_from_host,
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


def test_infer_thales_career_portal_uses_company_mailbox_domain() -> None:
    assert mailbox_domain_from_host("careers.thalesgroup.com") == "thalesgroup.com"
    assert mailbox_domain_from_host("jobs.thalesgroup.com") == "thalesgroup.com"
    assert domain_from_company_name("Thales") == "thalesgroup.com"
    assert (
        infer_company_domain(
            {
                "company": "Thales",
                "url": "https://careers.thalesgroup.com/job/radar-engineer",
            }
        )
        == "thalesgroup.com"
    )
    assert (
        infer_company_domain(
            {
                "company": "Thales Group",
                "url": "https://www.indeed.fr/viewjob?jk=thales",
            }
        )
        == "thalesgroup.com"
    )


def test_infer_domain_from_description_website() -> None:
    job = {
        "url": "https://www.indeed.fr/viewjob?jk=abc",
        "company": "Acme",
        "description": "Plus d'infos sur https://www.acme.fr/carrieres",
    }
    assert infer_company_domain(job) == "acme.fr"


def test_company_slug_from_wttj_and_ats_urls() -> None:
    assert (
        company_slug_from_job(
            {
                "url": "https://www.welcometothejungle.com/fr/companies/malt/jobs/dev-python"
            }
        )
        == "malt"
    )
    assert (
        company_slug_from_job({"url": "https://boards.greenhouse.io/acme/jobs/123"})
        == "acme"
    )


def test_clean_company_name_strips_legal_noise() -> None:
    assert clean_company_name("Acme SAS (Paris)") == "Acme"
    assert clean_company_name("N/A") == ""
    assert clean_company_name("L'Oréal") == "L'Oréal"


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
    low_generic = {
        "data": {
            "emails": [
                {
                    "value": "contact@acme.fr",
                    "type": "generic",
                    "confidence": 8,
                    "department": None,
                }
            ]
        }
    }
    assert pick_recruiter_email(low_generic) == "contact@acme.fr"


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
    assert params.get("type") == "generic"
    assert "department" not in params
    clear_hunter_cache()


def test_find_recruiter_email_retries_company_without_hr_filter() -> None:
    clear_hunter_cache()
    job = {
        "company": "Acme SAS (Paris)",
        "url": "https://www.indeed.fr/viewjob?jk=abc",
        "description": "Postulez en ligne.",
    }
    empty = {"data": {"emails": []}}
    with patch(
        "services.hunter._hunter_get",
        side_effect=[empty, HUNTER_PAYLOAD],
    ) as mocked:
        email = find_recruiter_email(job, api_key="hunter-test")
    assert email == "jobs@acme.fr"
    assert mocked.call_count == 2
    first, second = mocked.call_args_list[0].args[0], mocked.call_args_list[1].args[0]
    assert first["company"] == "Acme"
    assert first.get("type") == "generic"
    assert "department" not in first
    assert second["company"] == "Acme"
    assert "type" not in second
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


def test_resolve_apply_email_reads_thales_listing_page() -> None:
    job = {
        "title": "Ingénieur radar",
        "company": "Thales",
        "description": "Postulez en ligne sur le portail carrière.",
        "url": "https://careers.thalesgroup.com/job/radar-engineer",
        "apply_url": "https://careers.thalesgroup.com/job/radar-engineer",
    }
    html = (
        "<html><body>"
        '<a href="mailto:recrutement@thalesgroup.com">Postuler</a>'
        "</body></html>"
    )

    class _Resp:
        status_code = 200
        text = html

    with (
        patch("services.application.requests.get", return_value=_Resp()) as mocked,
        patch("services.hunter.find_recruiter_email") as hunter,
    ):
        assert extract_apply_email(job) is None
        assert extract_apply_email_from_pages(job) == "recrutement@thalesgroup.com"
        assert resolve_apply_email(job) == "recrutement@thalesgroup.com"
        hunter.assert_not_called()
    assert mocked.call_count >= 1
    assert "careers.thalesgroup.com" in mocked.call_args_list[0].args[0]


def test_indeed_thales_listing_uses_hunter_company_domain() -> None:
    clear_hunter_cache()
    job = {
        "title": "Ingénieur radar",
        "company": "Thales",
        "description": "Postulez sur Indeed.",
        "url": "https://www.indeed.fr/viewjob?jk=thales",
    }
    payload = {
        "data": {
            "domain": "thalesgroup.com",
            "emails": [
                {
                    "value": "recrutement@thalesgroup.com",
                    "type": "generic",
                    "confidence": 91,
                    "department": "hr",
                    "position": None,
                }
            ],
        }
    }
    class _Empty:
        status_code = 200
        text = "<html><body>Postuler en ligne</body></html>"

    with (
        patch("services.application.requests.get", return_value=_Empty()) as page,
        patch("services.hunter.hunter_api_key", return_value="hunter-test"),
        patch("services.hunter._hunter_get", return_value=payload) as hunter,
    ):
        assert extract_apply_email(job) is None
        assert resolve_apply_email(job) == "recrutement@thalesgroup.com"
    assert hunter.call_count >= 1
    assert hunter.call_args_list[0].args[0]["domain"] == "thalesgroup.com"
    assert page.call_count >= 1
    assert any("thalesgroup.com" in str(call.args[0]) for call in page.call_args_list)
    clear_hunter_cache()


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
    assert "Hunter" in fr["job.apply_auto_help"]
    assert "Hunter" in en["job.apply_auto_help"]
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 't("job.apply_auto")' in app_source
    assert "find_recruiter_email(" not in app_source
    assert "hunter_lookup" not in app_source
    assert "resolve_apply_email" in (ROOT / "services/application.py").read_text(encoding="utf-8")
    secrets = (ROOT / ".streamlit/secrets.toml.example").read_text(encoding="utf-8")
    assert "HUNTER_API_KEY" in secrets
    assert "SMTP_HOST" in secrets
    assert "smtp.gmail.com" in secrets
    assert not secrets.split("HUNTER_API_KEY")[0].rstrip().endswith("#")
    config = (ROOT / "config.py").read_text(encoding="utf-8")
    assert "HUNTER_API_KEY" in config
