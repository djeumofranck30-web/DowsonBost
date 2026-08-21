"""Email alerts for new matching job offers."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests


def _get_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, "") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


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
) -> str:
    rows = []
    for entry in offers[:10]:
        job = entry.get("job") or {}
        score = entry.get("score", 0)
        title = job.get("title", "Offre")
        company = job.get("company", "")
        url = job.get("url", "")
        link = f'<a href="{url}">Voir l\'offre</a>' if url else ""
        rows.append(
            f"<li><strong>{title}</strong> — {company} — score {score}% {link}</li>"
        )
    items = "\n".join(rows) if rows else "<li>Aucune offre</li>"
    return f"""
    <html><body>
    <p>Bonjour {user_name},</p>
    <p>De nouvelles offres correspondent à votre profil (<strong>{target_title}</strong>) :</p>
    <ul>{items}</ul>
    <p>Connectez-vous à DowsonBost pour consulter l'analyse détaillée et le suivi candidatures.</p>
    </body></html>
    """


def send_alert_email(
    to_email: str,
    subject: str,
    html_body: str,
    *,
    text_body: str = "",
) -> tuple[bool, str]:
    """Send alert email via Resend or SMTP."""
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
                    "text": text_body or "Consultez DowsonBost pour vos offres.",
                },
                timeout=30,
            )
            if response.status_code >= 400:
                return False, f"Resend {response.status_code}: {response.text[:200]}"
            return True, "E-mail envoyé via Resend."
        except requests.RequestException as exc:
            return False, str(exc)

    smtp_host = _get_secret("SMTP_HOST")
    smtp_port = int(_get_secret("SMTP_PORT") or "587")
    smtp_user = _get_secret("SMTP_USER")
    smtp_password = _get_secret("SMTP_PASSWORD")
    smtp_from = _get_secret("SMTP_FROM") or smtp_user

    if not smtp_host or not smtp_user:
        return False, "E-mail non configuré (RESEND_API_KEY ou SMTP_HOST/SMTP_USER)."

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    message.attach(MIMEText(text_body or "Consultez DowsonBost.", "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], message.as_string())
        return True, "E-mail envoyé via SMTP."
    except smtplib.SMTPException as exc:
        return False, str(exc)


def maybe_send_analysis_alert(
    user_email: str,
    user_name: str,
    target_title: str,
    offers: list[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[bool, str]:
    """Send alert if enabled and offers meet minimum score."""
    if not settings.get("email_alerts_enabled"):
        return False, "Alertes désactivées."
    if not email_configured():
        return False, "Service e-mail non configuré."
    min_score = int(settings.get("alert_min_score", 70))
    filtered = [o for o in offers if int(o.get("score", 0)) >= min_score]
    if not filtered:
        return False, "Aucune offre au-dessus du seuil d'alerte."
    subject = f"[DowsonBost] {len(filtered)} nouvelle(s) offre(s) — {target_title}"
    html = build_alert_html(user_name, target_title, filtered)
    return send_alert_email(user_email, subject, html)
