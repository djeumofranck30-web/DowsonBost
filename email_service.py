"""Transactional e-mails: alerts, welcome, password reset, applications."""

from __future__ import annotations

import base64
import html
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from typing import Any

import requests

from i18n import get_locale, t


from config import get_secret

BREVO_SMTP_URL = "https://api.brevo.com/v3/smtp/email"


def _get_secret(name: str) -> str:
    return get_secret(name, "")


def _parse_mailbox(value: str) -> tuple[str, str]:
    name, email = parseaddr((value or "").strip())
    return name.strip(), email.strip()


def _from_header() -> str:
    raw = (
        _get_secret("EMAIL_FROM")
        or _get_secret("SMTP_FROM")
        or _get_secret("SMTP_USER")
        or "DowsonBost"
    )
    name, email = _parse_mailbox(raw)
    if not email or "@" not in email:
        fallback = _get_secret("SMTP_USER")
        name, email = _parse_mailbox(fallback)
    if not email or "@" not in email:
        return raw
    return formataddr((name or "DowsonBost", email))


def _from_email() -> str:
    _, email = _parse_mailbox(_from_header())
    return email


def _identity_header(from_email: str | None, from_name: str | None) -> str | None:
    """Build a From header for the logged-in candidate, if an address is present."""
    email = str(from_email or "").strip()
    if not email or "@" not in email:
        return None
    name = str(from_name or "").strip() or email.split("@", 1)[0]
    return formataddr((name, email))


def email_configured() -> bool:
    if _get_secret("RESEND_API_KEY") or _get_secret("BREVO_API_KEY"):
        return True
    return bool(
        _get_secret("SMTP_HOST")
        and _get_secret("SMTP_USER")
        and _get_secret("SMTP_PASSWORD")
    )


def _attachment_bytes(content: str | bytes) -> bytes:
    if isinstance(content, bytes):
        return content
    return content.encode("utf-8")


def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[tuple[str, str | bytes, str]],
    reply_to: str | None,
    locale: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> tuple[bool, str]:
    key = _get_secret("RESEND_API_KEY")
    platform_name, platform_email = _parse_mailbox(_from_header())
    display_name = str(from_name or "").strip() or platform_name or "DowsonBost"
    payload: dict[str, Any] = {
        "from": formataddr((display_name, platform_email)) if platform_email else _from_header(),
        "to": [to_email],
        "subject": subject,
        "html": html_body or None,
        "text": text_body or t("email.text_fallback", locale=locale),
    }
    if not html_body:
        payload.pop("html", None)
    reply = (reply_to or from_email or "").strip()
    if reply:
        payload["reply_to"] = reply
    if attachments:
        payload["attachments"] = [
            {
                "filename": filename,
                "content": base64.b64encode(_attachment_bytes(content)).decode("ascii"),
            }
            for filename, content, _mime in attachments
        ]
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={k: v for k, v in payload.items() if v is not None},
            timeout=30,
        )
    except requests.RequestException as exc:
        return False, str(exc)
    if response.status_code >= 400:
        return False, f"Resend {response.status_code}: {response.text[:200]}"
    return True, t("email.sent_resend", locale=locale)


def _send_via_brevo(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[tuple[str, str | bytes, str]],
    reply_to: str | None,
    locale: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> tuple[bool, str]:
    key = _get_secret("BREVO_API_KEY")
    platform_name, platform_email = _parse_mailbox(_from_header())
    if not platform_email:
        return False, t("email.not_configured", locale=locale)
    display_name = str(from_name or "").strip() or platform_name or "DowsonBost"
    payload: dict[str, Any] = {
        "sender": {"name": display_name, "email": platform_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text_body or t("email.text_fallback", locale=locale),
    }
    if html_body:
        payload["htmlContent"] = html_body
    reply = (reply_to or from_email or "").strip()
    if reply:
        payload["replyTo"] = {"email": reply, "name": display_name}
    if attachments:
        payload["attachment"] = [
            {
                "name": filename,
                "content": base64.b64encode(_attachment_bytes(content)).decode("ascii"),
            }
            for filename, content, _mime in attachments
        ]
    try:
        response = requests.post(
            BREVO_SMTP_URL,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": key,
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        return False, str(exc)
    if response.status_code >= 400:
        return False, f"Brevo {response.status_code}: {response.text[:200]}"
    return True, t("email.sent_brevo", locale=locale)


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[tuple[str, str | bytes, str]],
    reply_to: str | None,
    locale: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> tuple[bool, str]:
    smtp_host = _get_secret("SMTP_HOST")
    smtp_port = int(_get_secret("SMTP_PORT") or "587")
    smtp_user = _get_secret("SMTP_USER")
    smtp_password = _get_secret("SMTP_PASSWORD")
    platform_header = _from_header()
    envelope = _from_email() or smtp_user
    if not smtp_host or not smtp_user:
        return False, t("email.not_configured", locale=locale)

    candidate_header = _identity_header(from_email, from_name)
    reply = (reply_to or from_email or "").strip() or None
    candidate_mailbox = (_parse_mailbox(candidate_header or "")[1] or "").lower()
    platform_mailbox = (_parse_mailbox(platform_header)[1] or "").lower()
    # Gmail/SMTP will not send as another person's mailbox. Trying it first
    # often hangs until timeout, so the click looks like it did nothing.
    can_send_as_candidate = bool(
        candidate_mailbox and platform_mailbox and candidate_mailbox == platform_mailbox
    )
    if can_send_as_candidate and candidate_header:
        display_from = candidate_header
    elif from_name and (_from_email() or smtp_user):
        display_from = formataddr(
            (str(from_name).strip(), _from_email() or smtp_user)
        )
    else:
        display_from = platform_header

    def _build(display_from: str) -> MIMEMultipart:
        if attachments:
            message: MIMEMultipart = MIMEMultipart("mixed")
            body_part = MIMEMultipart("alternative")
            body_part.attach(
                MIMEText(text_body or t("email.text_fallback", locale=locale), "plain", "utf-8")
            )
            if html_body:
                body_part.attach(MIMEText(html_body, "html", "utf-8"))
            message.attach(body_part)
            for filename, content, mime in attachments:
                raw = _attachment_bytes(content)
                if (mime or "").startswith("application/pdf") or str(filename).lower().endswith(".pdf"):
                    part = MIMEApplication(raw, _subtype="pdf")
                    part.add_header("Content-Disposition", "attachment", filename=filename)
                else:
                    part = MIMEText(raw.decode("utf-8"), "plain", "utf-8")
                    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                message.attach(part)
        else:
            message = MIMEMultipart("alternative")
            message.attach(
                MIMEText(text_body or t("email.text_fallback", locale=locale), "plain", "utf-8")
            )
            if html_body:
                message.attach(MIMEText(html_body, "html", "utf-8"))
        message["Subject"] = subject
        message["From"] = display_from
        message["To"] = to_email
        if reply:
            message["Reply-To"] = reply
        return message

    def _transmit(display_from: str) -> None:
        message = _build(display_from)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(envelope, [to_email], message.as_string())

    try:
        _transmit(display_from)
        return True, t("email.sent_smtp", locale=locale)
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        if display_from != platform_header:
            try:
                _transmit(platform_header)
                return True, t("email.sent_smtp", locale=locale)
            except (smtplib.SMTPException, OSError, TimeoutError) as retry_exc:
                return False, str(retry_exc)
        return False, str(exc)


def _deliver_email(
    to_email: str,
    subject: str,
    *,
    html_body: str = "",
    text_body: str = "",
    attachments: list[tuple[str, str | bytes, str]] | None = None,
    reply_to: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    locale: str = "fr",
) -> tuple[bool, str]:
    files = attachments or []
    kwargs = {
        "to_email": to_email,
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
        "attachments": files,
        "reply_to": reply_to,
        "from_email": from_email,
        "from_name": from_name,
        "locale": locale,
    }
    if _get_secret("RESEND_API_KEY"):
        return _send_via_resend(**kwargs)
    if _get_secret("BREVO_API_KEY"):
        return _send_via_brevo(**kwargs)
    if _get_secret("SMTP_HOST") and _get_secret("SMTP_USER"):
        return _send_via_smtp(**kwargs)
    return False, t("email.not_configured", locale=locale)


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
    """Send alert email via Gmail SMTP, Brevo or Resend."""
    lang = locale or get_locale()
    return _deliver_email(
        to_email,
        subject,
        html_body=html_body,
        text_body=text_body,
        locale=lang,
    )


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
    try:
        daily_limit = max(1, min(50, int(settings.get("auto_search_daily_limit") or 10)))
    except (TypeError, ValueError):
        daily_limit = 10
    filtered = filtered[:daily_limit]
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


def _plain_to_simple_html(text: str) -> str:
    """Turn a short plain-text mail into readable HTML paragraphs."""
    blocks = [
        html.escape(part.strip())
        for part in (text or "").replace("\r\n", "\n").split("\n\n")
        if part.strip()
    ]
    if not blocks:
        return ""
    inner = "".join(
        f"<p style='margin:0 0 14px 0;line-height:1.55;font-size:15px;'>"
        f"{block.replace(chr(10), '<br>')}</p>"
        for block in blocks
    )
    return (
        "<html><body style=\"font-family:Georgia,'Times New Roman',serif;"
        f'color:#111827;background:#ffffff;padding:4px 2px;">{inner}</body></html>'
    )


def send_application_email(
    to_email: str,
    subject: str,
    body_text: str,
    *,
    attachments: list[tuple[str, str | bytes, str]] | None = None,
    reply_to: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send a job application e-mail from the candidate's address when possible."""
    lang = locale or get_locale()
    sender = str(from_email or "").strip() or None
    ok, detail = _deliver_email(
        to_email,
        subject,
        html_body=_plain_to_simple_html(body_text),
        text_body=body_text,
        attachments=attachments,
        reply_to=reply_to or sender,
        from_email=sender,
        from_name=from_name,
        locale=lang,
    )
    if ok:
        return True, t("email.application_sent", locale=lang)
    return False, detail


def send_password_reset_code_email(
    user_email: str,
    code: str,
    *,
    locale: str | None = None,
) -> tuple[bool, str]:
    """Send a short-lived 8-character password reset code."""
    lang = locale or get_locale()
    if not email_configured():
        return False, t("email.service_not_configured", locale=lang)
    safe_code = html.escape(str(code or "").strip().upper())
    subject = t("email.reset_code_subject", locale=lang)
    html_body = f"""
    <html><body style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.5;color:#0B1220">
      <p>{t("email.reset_code_intro", locale=lang)}</p>
      <p style="margin:1.2rem 0;padding:1rem 1.15rem;background:#F5F7F8;border:1px solid #E5E7EB;border-radius:12px;text-align:center;font-size:1.65rem;letter-spacing:0.28em;font-weight:800;font-family:ui-monospace,SFMono-Regular,Menlo,monospace">{safe_code}</p>
      <p>{t("email.reset_code_ttl", locale=lang)}</p>
      <p style="color:#64748b;font-size:12px">{t("email.reset_code_footer", locale=lang)}</p>
    </body></html>
    """
    text_body = (
        f"{t('email.reset_code_intro', locale=lang)}\n\n"
        f"{code}\n\n"
        f"{t('email.reset_code_ttl', locale=lang)}\n"
        f"{t('email.reset_code_footer', locale=lang)}\n"
    )
    return send_alert_email(
        user_email, subject, html_body, text_body=text_body, locale=lang
    )


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

