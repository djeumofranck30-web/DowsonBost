"""Tests for job application helpers."""

from __future__ import annotations

from unittest.mock import patch

from services.application import (
    auto_apply_readiness,
    build_application_profile,
    enrich_application_profile,
    extract_apply_email,
    format_application_autofill_text,
    format_application_profile_text,
    job_listing_open_script,
    notify_candidate_application,
    prepare_manual_application,
    submit_application_automatically,
)


@patch("services.application.llm_keys_configured", return_value=True)
@patch("services.application.email_configured", return_value=True)
@patch("services.hunter.hunter_configured", return_value=True)
def test_auto_apply_readiness_is_ready_when_all_secrets_exist(
    _hunter: object,
    _mail: object,
    _llm: object,
) -> None:
    status = auto_apply_readiness()
    assert status["ready"] is True
    assert status["missing"] == []


@patch("services.application.llm_keys_configured", return_value=False)
@patch("services.application.email_configured", return_value=False)
@patch("services.hunter.hunter_configured", return_value=False)
def test_auto_apply_readiness_lists_missing_secrets(
    _hunter: object,
    _mail: object,
    _llm: object,
) -> None:
    status = auto_apply_readiness()
    assert status["ready"] is False
    assert "HUNTER_API_KEY" in status["missing"]
    assert any("SMTP" in item or "BREVO" in item for item in status["missing"])


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


@patch("services.application.notify_candidate_application", return_value=True)
@patch("services.application.send_application_email", return_value=(True, "ok"))
@patch("services.hunter.hunter_configured", return_value=True)
@patch("services.application.email_configured", return_value=True)
@patch("services.application.resolve_apply_email", return_value=None)
def test_submit_application_automatically_prepares_pack_without_recruiter_email(
    _resolve: object,
    _mail: object,
    _hunter: object,
    send_mail: object,
    notify_user: object,
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
    assert result["method"] == "prepared"
    assert result["cover_letter"]
    assert result["adapted_cv"]
    assert result["email_to"] == "jane@example.com"
    assert result["email_from"] == "jane@example.com"
    assert result["email_body"]
    assert "dossier" in result["message"].lower()
    assert "manuellement" in result["message"].lower()
    send_mail.assert_called_once()
    assert send_mail.call_args.kwargs["to_email"] == "jane@example.com"
    assert send_mail.call_args.kwargs["from_email"] == "jane@example.com"
    notify_user.assert_called_once()
    assert notify_user.call_args.kwargs["method"] == "auto_prepared"


def test_enrich_application_profile_fills_account_email():
    with patch(
        "auth.get_user_by_id",
        return_value={"email": "jane@example.com", "full_name": "Jane Doe", "phone": "+33600000000"},
    ):
        out = enrich_application_profile({"id": 7, "target_job_title": "Dev"})
    assert out["email"] == "jane@example.com"
    assert out["full_name"] == "Jane Doe"
    assert out["phone"] == "+33600000000"


@patch("services.application.notify_candidate_application", return_value=True)
@patch("services.application.send_application_email", return_value=(True, "ok"))
@patch("services.application.email_configured", return_value=True)
@patch("services.application.resolve_apply_email", return_value="jobs@acme.fr")
def test_submit_application_automatically_enriches_missing_snapshot_email(
    _resolve: object,
    _configured: object,
    _send: object,
    _notify: object,
):
    with patch(
        "auth.get_user_by_id",
        return_value={"email": "jane@example.com", "full_name": "Jane Doe"},
    ):
        result = submit_application_automatically(
            "CV source",
            {
                "title": "Dev Python",
                "company": "Acme",
                "description": "Postulez.",
                "url": "https://example.com/jobs/1",
            },
            {"score_correspondance": 80},
            {"id": 7, "target_job_title": "Dev Python"},
            llm_call=lambda *_a, **_k: "Document généré.",
            locale="fr",
        )
    assert result["success"] is True
    assert result["method"] == "email"
    assert _send.call_args.kwargs["from_email"] == "jane@example.com"
    _notify.assert_called_once()


@patch("services.application.email_configured", return_value=False)
def test_submit_application_automatically_fails_when_mail_not_configured(
    _configured: object,
):
    result = submit_application_automatically(
        "CV source",
        {
            "title": "Dev Python",
            "company": "Acme",
            "description": "Postulez en ligne.",
            "url": "https://example.com/jobs/1",
        },
        {"score_correspondance": 80},
        {"full_name": "Jane Doe", "email": "jane@example.com"},
        llm_call=lambda *_a, **_k: "Document généré.",
        locale="fr",
    )
    assert result["success"] is False
    assert result["method"] == "email_not_configured"
    assert "resend" in result["message"].lower() or "smtp" in result["message"].lower()


def test_job_listing_open_script_embeds_safe_url():
    html = job_listing_open_script(
        "https://www.indeed.com/viewjob?jk=abc",
        "Prénom : Jane",
    )
    assert "https://www.indeed.com/viewjob?jk=abc" in html
    assert "Prénom : Jane" in html or "Pr\\u00e9nom : Jane" in html
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
    assert result["email_to"] == "recrutement@acme.fr"
    assert result["email_from"] == "jane@example.com"
    assert result["email_subject"]
    assert result["email_body"]
    assert result["user_notified"] is True
    _send.assert_called_once()
    assert _send.call_args.kwargs["to_email"] == "recrutement@acme.fr"
    assert _send.call_args.kwargs["from_email"] == "jane@example.com"
    assert _send.call_args.kwargs["reply_to"] == "jane@example.com"
    attachments = _send.call_args.kwargs["attachments"]
    assert attachments[0][0].endswith(".pdf")
    assert attachments[0][1].startswith(b"%PDF")
    assert attachments[1][0].endswith(".pdf")
    notify_user.assert_called_once()
    assert notify_user.call_args.kwargs["method"] == "email"
    assert notify_user.call_args.kwargs["recruiter_email"] == "recrutement@acme.fr"
    assert "jane@example.com" in result["message"]
    assert "recrutement@acme.fr" in result["message"]
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
