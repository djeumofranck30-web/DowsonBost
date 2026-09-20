"""Transactional e-mail content tests."""

from __future__ import annotations

from unittest.mock import patch

from email_service import (
    _from_header,
    email_configured,
    send_application_confirmation_email,
    send_alert_email,
    send_application_email,
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
    assert "votre adresse" in html
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


def test_email_configured_accepts_gmail_smtp(monkeypatch):
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_USER": "me@gmail.com",
        "SMTP_PASSWORD": "abcd efgh ijkl mnop",
    }.get(name, ""))
    assert email_configured() is True


def test_email_configured_accepts_brevo(monkeypatch):
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "BREVO_API_KEY": "xkeysib-test",
        "EMAIL_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    assert email_configured() is True


def test_from_header_uses_gmail_address(monkeypatch):
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "SMTP_USER": "me@gmail.com",
        "SMTP_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    assert "me@gmail.com" in _from_header()


@patch("email_service.requests.post")
def test_send_alert_email_uses_brevo_when_no_resend(mocked_post, monkeypatch):
    mocked_post.return_value.status_code = 201
    mocked_post.return_value.text = "{}"
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "BREVO_API_KEY": "xkeysib-test",
        "EMAIL_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    ok, message = send_alert_email("jane@example.com", "Sujet", "<p>Hi</p>", locale="fr")
    assert ok is True
    assert "Brevo" in message
    assert mocked_post.call_args.args[0] == "https://api.brevo.com/v3/smtp/email"


@patch("email_service.smtplib.SMTP")
def test_send_application_email_uses_gmail_smtp(mocked_smtp, monkeypatch):
    server = mocked_smtp.return_value.__enter__.return_value
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "me@gmail.com",
        "SMTP_PASSWORD": "app-pass",
        "SMTP_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    ok, message = send_application_email(
        "recrutement@acme.fr",
        "Candidature",
        "Bonjour",
        locale="fr",
    )
    assert ok is True
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("me@gmail.com", "app-pass")
    server.sendmail.assert_called_once()
    assert server.sendmail.call_args.args[0] == "me@gmail.com"


@patch("email_service.smtplib.SMTP")
def test_send_application_email_uses_candidate_from_and_reply_to(mocked_smtp, monkeypatch):
    server = mocked_smtp.return_value.__enter__.return_value
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "me@gmail.com",
        "SMTP_PASSWORD": "app-pass",
        "SMTP_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    ok, _message = send_application_email(
        "recrutement@acme.fr",
        "Candidature",
        "Bonjour",
        from_email="jane@example.com",
        from_name="Jane Doe",
        locale="fr",
    )
    assert ok is True
    raw = server.sendmail.call_args.args[2]
    assert "jane@example.com" in raw
    assert "Jane Doe" in raw
    assert "Reply-To" in raw
    assert server.sendmail.call_args.args[0] == "me@gmail.com"



@patch("email_service.smtplib.SMTP", side_effect=OSError("timed out"))
def test_send_application_email_reports_smtp_timeout(mocked_smtp, monkeypatch):
    monkeypatch.setattr("email_service._get_secret", lambda name: {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "me@gmail.com",
        "SMTP_PASSWORD": "app-pass",
        "SMTP_FROM": "DowsonBost <me@gmail.com>",
    }.get(name, ""))
    ok, message = send_application_email(
        "recrutement@acme.fr",
        "Candidature",
        "Bonjour",
        locale="fr",
    )
    assert ok is False
    assert "timed out" in message
    mocked_smtp.assert_called()
