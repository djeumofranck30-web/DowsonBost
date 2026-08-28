"""Transactional e-mail content tests."""

from __future__ import annotations

from unittest.mock import patch

from email_service import (
    send_application_confirmation_email,
    send_password_reset_code_email,
    send_welcome_email,
)


@patch("email_service.send_alert_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_send_welcome_email_builds_message(_configured: object, send: object):
    ok, _ = send_welcome_email(
        "alice@example.com",
        "Alice Doe",
        "http://localhost:8501/",
        locale="fr",
    )
    assert ok
    send.assert_called_once()
    to_email, subject, html = send.call_args.args[:3]
    assert to_email == "alice@example.com"
    assert "Bienvenue" in subject
    assert "Alice Doe" in html
    assert "http://localhost:8501/" in html


@patch("email_service.send_alert_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_send_application_confirmation_email_builds_message(_configured: object, send: object):
    ok, _ = send_application_confirmation_email(
        "jane@example.com",
        "Jane Doe",
        {
            "title": "Dev Python",
            "company": "Acme",
            "url": "https://example.com/jobs/1",
        },
        method="email",
        recruiter_email="recrutement@acme.fr",
        locale="fr",
    )
    assert ok
    send.assert_called_once()
    to_email, subject, html = send.call_args.args[:3]
    assert to_email == "jane@example.com"
    assert "Confirmation de candidature" in subject
    assert "Dev Python" in html
    assert "Acme" in html
    assert "recrutement@acme.fr" in html
    assert "https://example.com/jobs/1" in html


@patch("email_service.send_alert_email", return_value=(True, "ok"))
@patch("email_service.email_configured", return_value=True)
def test_send_password_reset_code_email_shows_code(_configured: object, send: object):
    ok, _ = send_password_reset_code_email("jane@example.com", "AB23K7NP", locale="fr")
    assert ok
    to_email, subject, html = send.call_args.args[:3]
    assert to_email == "jane@example.com"
    assert "AB23K7NP" in html
    assert "2 minutes" in html
    assert "réinitialisation" in subject.lower() or "code" in subject.lower()


@patch("email_service.email_configured", return_value=False)
def test_send_welcome_email_requires_configuration(_configured: object):
    ok, message = send_welcome_email("a@b.com", "A", "http://x/", locale="fr")
    assert ok is False
    assert message
