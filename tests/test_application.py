"""Tests for job application helpers."""

from __future__ import annotations

from unittest.mock import patch

from services.application import (
    build_application_profile,
    extract_apply_email,
    format_application_autofill_text,
    format_application_profile_text,
    job_listing_open_script,
    notify_candidate_application,
    prepare_manual_application,
    submit_application_automatically,
)


def test_extract_apply_email_prefers_recruitment_address():
    job = {
        "description": "Contact: support@example.com ou recrutement@acme.fr pour postuler.",
        "url": "",
    }
    assert extract_apply_email(job) == "recrutement@acme.fr"


def test_extract_apply_email_ignores_noreply():
    job = {"description": "Write to noreply@company.com or jobs@company.com", "url": ""}
    assert extract_apply_email(job) == "jobs@company.com"


def test_extract_apply_email_from_mailto():
    job = {
        "description": '<a href="mailto:recrutement@acme.fr">Postuler</a>',
        "url": "",
    }
    assert extract_apply_email(job) == "recrutement@acme.fr"


def test_extract_apply_email_from_obfuscated():
    job = {"description": "Contact: candidats [at] acme [dot] fr", "url": ""}
    assert extract_apply_email(job) == "candidats@acme.fr"


def test_build_application_profile_formats_core_fields():
    profile = build_application_profile(
        {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+33 6 00 00 00 00",
            "target_job_title": "Data Engineer",
            "home_city": "Lyon",
            "contract_type": "CDI",
            "experience_level": "senior",
        }
    )
    text = format_application_profile_text(profile)
    assert "Jane Doe" in text
    assert "jane@example.com" in text
    assert "Data Engineer" in text
    assert "Lyon" in text
    assert profile["first_name"] == "Jane"
    assert profile["last_name"] == "Doe"
    fill = format_application_autofill_text(
        profile,
        cover_letter="Lettre type",
        adapted_cv="CV type",
    )
    assert "Prénom : Jane" in fill
    assert "E-mail : jane@example.com" in fill
    assert "Lettre type" in fill


@patch("services.application._send_user_application_copy", return_value=True)
def test_submit_application_automatically_generates_and_prepares_external(
    _user_copy: object,
):
    job = {
        "title": "Dev Python",
        "company": "Acme",
        "location": "Paris",
        "description": "Mission intéressante sans e-mail.",
        "url": "https://example.com/jobs/1",
    }
    match = {"score_correspondance": 80, "titre_cv_recommande": "Dev Python"}
    user = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+33600000000",
        "target_job_title": "Dev Python",
    }

    def fake_llm(_system: str, _user: str, **kwargs: object) -> str:
        if "lettre" in _user.lower() or "motivation" in _system.lower():
            return "Lettre de motivation générée."
        return "CV adapté généré."

    result = submit_application_automatically(
        "CV source",
        job,
        match,
        user,
        llm_call=fake_llm,
        locale="fr",
    )
    assert result["success"] is True
    assert result["method"] == "external_prepared"
    assert "Lettre" in result["cover_letter"]
    assert "CV adapté" in result["adapted_cv"]
    assert result["user_notified"] is True
    assert "préparée" in result["message"].lower()
    assert "nouvel onglet" in result["message"].lower() or "ouvre" in result["message"].lower()


def test_job_listing_open_script_embeds_safe_url():
    html = job_listing_open_script(
        "https://www.indeed.com/viewjob?jk=abc",
        "Prénom : Jane",
    )
    assert "https://www.indeed.com/viewjob?jk=abc" in html
    assert "Prénom : Jane" in html
    assert "clipboard.writeText" in html
    assert "window.top" in html
    assert job_listing_open_script("") == ""
    assert job_listing_open_script("   ") == ""
    unsafe = job_listing_open_script("https://x.test/</script>alert(1)")
    assert "</script>alert" not in unsafe


@patch("services.application.notify_candidate_application", return_value=True)
@patch("services.application.send_application_email", return_value=(True, "ok"))
@patch("services.application.email_configured", return_value=True)
def test_submit_application_automatically_sends_email_when_found(
    _configured: object,
    _send: object,
    notify_user: object,
):
    job = {
        "title": "Dev Python",
        "company": "Acme",
        "location": "Paris",
        "description": "Envoyez votre CV à recrutement@acme.fr",
        "url": "https://example.com/jobs/1",
    }
    match = {"score_correspondance": 80}
    user = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "target_job_title": "Dev Python",
    }

    def fake_llm(_system: str, _user: str, **kwargs: object) -> str:
        return "Document généré."

    result = submit_application_automatically(
        "CV source",
        job,
        match,
        user,
        llm_call=fake_llm,
    )
    assert result["success"] is True
    assert result["method"] == "email"
    assert result["apply_email"] == "recrutement@acme.fr"
    assert result["user_notified"] is True
    attachments = _send.call_args.kwargs["attachments"]
    assert attachments[0][0].endswith(".pdf")
    assert attachments[0][1].startswith(b"%PDF")
    assert attachments[1][0].endswith(".pdf")
    notify_user.assert_called_once()
    assert notify_user.call_args.kwargs["method"] == "email"
    assert notify_user.call_args.kwargs["recruiter_email"] == "recrutement@acme.fr"
    assert "confirmation" in result["message"].lower()


@patch("services.application.send_application_confirmation_email", return_value=(True, "ok"))
def test_notify_candidate_application_sends_confirmation(_send: object):
    ok = notify_candidate_application(
        {"full_name": "Jane Doe", "email": "jane@example.com"},
        {"title": "Dev Python", "company": "Acme", "url": "https://example.com/jobs/1"},
        method="manual",
        locale="fr",
    )
    assert ok is True
    _send.assert_called_once()
    assert _send.call_args.args[0] == "jane@example.com"
    assert _send.call_args.kwargs["method"] == "manual"


def test_notify_candidate_application_skips_without_email():
    ok = notify_candidate_application(
        {"full_name": "Jane Doe", "email": ""},
        {"title": "Dev Python"},
        method="manual",
    )
    assert ok is False


def test_prepare_manual_application_requires_url():
    result = prepare_manual_application(
        "CV",
        {"title": "Job", "description": "", "url": ""},
        {},
        {"full_name": "Jane", "email": "jane@example.com"},
        llm_call=lambda *_a, **_k: "",
        generate_documents=False,
    )
    assert result["success"] is False
    assert result["method"] == "missing_url"
