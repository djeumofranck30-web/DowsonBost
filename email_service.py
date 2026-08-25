"""Transactional e-mails: alerts, welcome, password reset, applications."""

from __future__ import annotations

import base64
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

from i18n import get_locale, t


from config import get_secret


def _get_secret(name: str) -> str:
    return get_secret(name, "")


def email_configured() -> bool:
    if _get_secret("RESEND_API_KEY"):
        return True
    host = _get_secret("SMTP_HOST")
    user = _get_secret("SMTP_USER")
    return bool(host and user)


def build_alert_html(
    user_name: str,
    target_title: str,
    offers: list[dict[str, Any]],
    *,
    locale: str | None = None,
) -> str:
    lang = locale or get_locale()
    rows = []
    for entry in offers[:10]:
        job = entry.get("job") or {}
        score = entry.get("score", 0)
        title = job.get("title", t("email.default_job", locale=lang))
        company = job.get("company", "")
        url = job.get("url", "")
        link = (
            f'<a href="{url}">{t("email.view_offer", locale=lang)}</a>'
            if url
            else ""
        )
        rows.append(
            f"<li><strong>{title}</strong> — {company} — score {score}% {link}</li>"
        )
    items = "\n".join(rows) if rows else f"<li>{t('email.no_offers', locale=lang)}</li>"
    return f"""
    <html><body>
    <p>{t('email.greeting', locale=lang, name=user_name)}</p>
    <p>{t('email.intro', locale=lang, title=f'<strong>{target_title}</strong>')}</p>
    <ul>{items}</ul>
    <p>{t('email.footer', locale=lang)}</p>
    </body></html>
    """


def send_alert_email(
    to_email: str,
    subject: str,
    html_body: str,
    *,
    text_body: str = "",
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send alert email via Resend or SMTP."""
    lang = locale or get_locale()
    resend_key = _get_secret("RESEND_API_KEY")
    from_resend = _get_secret("EMAIL_FROM") or "DowsonBost <onboarding@resend.dev>"

    if resend_key:
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_resend,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body or t("email.text_fallback", locale=lang),
                },
                timeout=30,
            )
            if response.status_code >= 400:
                return False, f"Resend {response.status_code}: {response.text[:200]}"
            return True, t("email.sent_resend", locale=lang)
        except requests.RequestException as exc:
            return False, str(exc)

    smtp_host = _get_secret("SMTP_HOST")
    smtp_port = int(_get_secret("SMTP_PORT") or "587")
    smtp_user = _get_secret("SMTP_USER")
    smtp_password = _get_secret("SMTP_PASSWORD")
    smtp_from = _get_secret("SMTP_FROM") or smtp_user

    if not smtp_host or not smtp_user:
        return False, t("email.not_configured", locale=lang)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    message.attach(
        MIMEText(text_body or t("email.text_fallback", locale=lang), "plain", "utf-8")
    )
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], message.as_string())
        return True, t("email.sent_smtp", locale=lang)
    except smtplib.SMTPException as exc:
        return False, str(exc)


def maybe_send_analysis_alert(
    user_email: str,
    user_name: str,
    target_title: str,
    offers: list[dict[str, Any]],
    settings: dict[str, Any],
    *,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send alert if enabled and offers meet minimum score."""
    lang = locale or get_locale()
    if not settings.get("email_alerts_enabled"):
        return False, t("email.alerts_disabled", locale=lang)
    if not email_configured():
        return False, t("email.service_not_configured", locale=lang)
    min_score = int(settings.get("alert_min_score", 70))
    filtered = [o for o in offers if int(o.get("score", 0)) >= min_score]
    if not filtered:
        return False, t("email.below_threshold", locale=lang)
    subject = t(
        "email.subject",
        locale=lang,
        count=len(filtered),
        title=target_title,
    )
    html = build_alert_html(user_name, target_title, filtered, locale=lang)
    return send_alert_email(user_email, subject, html, locale=lang)


def send_application_email(
    to_email: str,
    subject: str,
    body_text: str,
    *,
    attachments: list[tuple[str, str, str]] | None = None,
    reply_to: str | None = None,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send a job application e-mail with optional text attachments."""
    lang = locale or get_locale()
    resend_key = _get_secret("RESEND_API_KEY")
    from_resend = _get_secret("EMAIL_FROM") or "DowsonBost <onboarding@resend.dev>"
    attachment_items = attachments or []

    if resend_key:
        try:
            payload: dict[str, Any] = {
                "from": from_resend,
                "to": [to_email],
                "subject": subject,
                "text": body_text,
            }
            if reply_to:
                payload["reply_to"] = reply_to
            if attachment_items:
                payload["attachments"] = [
                    {
                        "filename": filename,
                        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    }
                    for filename, content, _mime in attachment_items
                ]
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            if response.status_code >= 400:
                return False, f"Resend {response.status_code}: {response.text[:200]}"
            return True, t("email.application_sent", locale=lang)
        except requests.RequestException as exc:
            return False, str(exc)

    smtp_host = _get_secret("SMTP_HOST")
    smtp_port = int(_get_secret("SMTP_PORT") or "587")
    smtp_user = _get_secret("SMTP_USER")
    smtp_password = _get_secret("SMTP_PASSWORD")
    smtp_from = _get_secret("SMTP_FROM") or smtp_user

    if not smtp_host or not smtp_user:
        return False, t("email.not_configured", locale=lang)

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    if reply_to:
        message["Reply-To"] = reply_to

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_text, "plain", "utf-8"))
    message.attach(body_part)

    for filename, content, _mime in attachment_items:
        part = MIMEText(content, "plain", "utf-8")
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        message.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], message.as_string())
        return True, t("email.application_sent", locale=lang)
    except smtplib.SMTPException as exc:
        return False, str(exc)


def send_password_reset_email(user_email: str, reset_url: str, *, locale: str | None = None) -> tuple[bool, str]:
    """Send password reset link."""
    lang = locale or get_locale()
    if not email_configured():
        return False, t("email.service_not_configured", locale=lang)
    subject = t("email.reset_subject", locale=lang)
    html = f"""
    <html><body style="font-family:sans-serif;line-height:1.5">
      <p>{t("email.reset_intro", locale=lang)}</p>
      <p><a href="{reset_url}">{t("email.reset_button", locale=lang)}</a></p>
      <p style="color:#64748b;font-size:12px">{t("email.reset_footer", locale=lang)}</p>
    </body></html>
    """
    return send_alert_email(user_email, subject, html, locale=lang)


def send_welcome_email(
    user_email: str,
    user_name: str,
    login_url: str,
    *,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send account creation confirmation e-mail."""
    lang = locale or get_locale()
    if not email_configured():
        return False, t("email.service_not_configured", locale=lang)
    safe_name = html.escape(user_name or user_email)
    safe_url = html.escape(login_url, quote=True)
    subject = t("email.welcome_subject", locale=lang)
    html_body = f"""
    <html><body style="font-family:sans-serif;line-height:1.5">
      <p>{t("email.greeting", locale=lang, name=safe_name)}</p>
      <p>{t("email.welcome_intro", locale=lang)}</p>
      <p>{t("email.welcome_body", locale=lang)}</p>
      <p><a href="{safe_url}">{t("email.welcome_button", locale=lang)}</a></p>
      <p style="color:#64748b;font-size:12px">{t("email.welcome_footer", locale=lang)}</p>
    </body></html>
    """
    text_body = (
        f"{t('email.greeting', locale=lang, name=user_name or user_email)}\n\n"
        f"{t('email.welcome_intro', locale=lang)}\n"
        f"{t('email.welcome_body', locale=lang)}\n\n"
        f"{login_url}\n"
    )
    return send_alert_email(
        user_email, subject, html_body, text_body=text_body, locale=lang
    )


def send_application_confirmation_email(
    user_email: str,
    user_name: str,
    job: dict[str, Any],
    *,
    method: str = "manual",
    recruiter_email: str | None = None,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send the candidate a confirmation that their application was recorded."""
    lang = locale or get_locale()
    if not user_email:
        return False, t("email.service_not_configured", locale=lang)
    if not email_configured():
        return False, t("email.service_not_configured", locale=lang)

    title = str(job.get("title") or t("email.default_job", locale=lang)).strip()
    company = str(job.get("company") or "").strip()
    job_url = str(job.get("url") or job.get("apply_url") or "").strip()
    safe_name = html.escape(user_name or user_email)
    safe_title = html.escape(title)
    safe_company = html.escape(company)
    safe_url = html.escape(job_url, quote=True)

    if method == "email" and recruiter_email:
        method_html = t(
            "email.apply_confirm_method_email",
            locale=lang,
            email=html.escape(recruiter_email),
        )
        method_text = t(
            "email.apply_confirm_method_email",
            locale=lang,
            email=recruiter_email,
        )
    elif method in {"external_prepared", "auto_prepared"}:
        method_html = method_text = t("email.apply_confirm_method_prepared", locale=lang)
    else:
        method_html = method_text = t("email.apply_confirm_method_manual", locale=lang)

    subject = t("email.apply_confirm_subject", locale=lang, title=title)
    offer_link = (
        f'<p><a href="{safe_url}">{t("email.apply_confirm_view", locale=lang)}</a></p>'
        if job_url
        else ""
    )
    company_html = (
        f"<p>{t('email.apply_confirm_company', locale=lang, company=safe_company)}</p>"
        if company
        else ""
    )
    html_body = f"""
    <html><body style="font-family:sans-serif;line-height:1.5">
      <p>{t("email.greeting", locale=lang, name=safe_name)}</p>
      <p>{t("email.apply_confirm_intro", locale=lang)}</p>
      <p>{t("email.apply_confirm_job", locale=lang, title=safe_title)}</p>
      {company_html}
      <p>{method_html}</p>
      {offer_link}
      <p style="color:#64748b;font-size:12px">{t("email.apply_confirm_footer", locale=lang)}</p>
    </body></html>
    """
    text_parts = [
        t("email.greeting", locale=lang, name=user_name or user_email),
        "",
        t("email.apply_confirm_intro", locale=lang),
        t("email.apply_confirm_job", locale=lang, title=title),
    ]
    if company:
        text_parts.append(t("email.apply_confirm_company", locale=lang, company=company))
    text_parts.append(method_text)
    if job_url:
        text_parts.extend(["", job_url])
    return send_alert_email(
        user_email,
        subject,
        html_body,
        text_body="\n".join(text_parts),
        locale=lang,
    )

