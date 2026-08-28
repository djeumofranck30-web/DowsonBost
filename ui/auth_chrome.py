"""Shared login chrome for candidate and admin sign-in pages."""

from __future__ import annotations

import html
from datetime import datetime

from i18n import t


def auth_illustration_svg() -> str:
    """Dusk city illustration for the left auth panel."""
    return """
<svg class="auth-illustration" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <rect width="320" height="220" fill="#155E75"/>
  <circle cx="248" cy="52" r="34" fill="#E8B923"/>
  <ellipse cx="210" cy="58" rx="38" ry="18" fill="#0E7490"/>
  <ellipse cx="255" cy="62" rx="30" ry="14" fill="#0E7490"/>
  <path d="M0 150 Q80 120 160 145 T320 138 L320 220 L0 220 Z" fill="#0B4A5C"/>
  <path d="M0 170 Q90 145 180 168 T320 158 L320 220 L0 220 Z" fill="#0E7490"/>
  <path d="M0 188 Q100 165 200 185 T320 176 L320 220 L0 220 Z" fill="#124E5E"/>
  <line x1="40" y1="28" x2="58" y2="8" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <line x1="120" y1="18" x2="128" y2="2" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <line x1="180" y1="36" x2="198" y2="16" stroke="#F4F1EA" stroke-width="2" stroke-linecap="round"/>
  <circle cx="90" cy="40" r="2" fill="#F4F1EA"/>
  <circle cx="150" cy="24" r="2" fill="#F4F1EA"/>
  <circle cx="200" cy="30" r="2" fill="#F4F1EA"/>
</svg>
"""


def auth_left_panel_html(*, title: str, tip: str) -> str:
    """Decorative left column for the auth card."""
    return f"""
<div class="auth-left-panel">
  <div class="auth-illustration-wrap">
    {auth_illustration_svg()}
  </div>
  <p class="auth-left-title">
    {html.escape(title)}
  </p>
  <p class="auth-left-tip">
    {html.escape(tip)}
  </p>
</div>
"""


def auth_time_greeting() -> tuple[str, str]:
    """Return headline and sub-greeting for the auth panel."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return t("auth.greeting.morning"), t("auth.greeting.morning_sub")
    if 12 <= hour < 18:
        return t("auth.greeting.morning"), t("auth.greeting.afternoon_sub")
    if 18 <= hour < 23:
        return t("auth.greeting.evening"), t("auth.greeting.evening_sub")
    return t("auth.greeting.evening"), t("auth.greeting.night_sub")
