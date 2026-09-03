"""Shared application constants."""

from __future__ import annotations

APP_NAME = "DowsonBost"
PROJECT_SLUG = "DowsonBost"

MIN_CV_TEXT_LENGTH = 50
MAX_OCR_PAGES = 5
CACHE_TTL_SECONDS = 86_400  # 24 h
TOP_MATCHING_JOBS = 60
MATCHING_CANDIDATE_POOL = 60
GROQ_MATCH_BATCH_SIZE = 1
GROQ_INTER_CALL_DELAY_SEC = 0.25
GROQ_RATE_LIMIT_RETRY_SEC = 3.0
PARALLEL_MATCH_MAX_WORKERS = 8
PARALLEL_MATCH_KEYS_PER_PROVIDER = 8
PARALLEL_MATCH_NUMBERED_KEY_MAX = 8
SEARCH_LOCATION_MAX_WORKERS = 4
CV_MATCH_TEXT_LIMIT_WITH_PROFILE = 4500
ATS_MATCH_MAX_TOKENS = 3500

ANALYSIS_DEPTH_OPTIONS = ("rapide", "standard", "complet")
ANALYSIS_DEPTH_POOL = {"rapide": 25, "standard": 60, "complet": 100}
ANALYSIS_DEPTH_TOP = {"rapide": 25, "standard": 60, "complet": 100}
NAV_PAGE_KEYS = ("dashboard", "analysis", "events", "support", "profile")
EVENTS_TAB_KEYS = ("applications", "history")
NAV_PAGE_ALIASES = {
    "applications": "events",
    "history": "events",
    "overview": "dashboard",
    "synthese": "dashboard",
    "diagnostic": "analysis",
}
ADMIN_PAGE_PATH = "pages/dashboard.py"
JOB_CARDS_PER_PAGE = 25
HISTORY_ROWS_PER_PAGE = 8
PROFILE_SECTION_KEYS = ("search", "accounts", "alerts", "security")
APPLICATION_CHANNEL_KEYS = ("all", "automatic", "manual")
SUPPORT_MESSAGE_MAX_LEN = 4000
PROFILE_PHOTO_MAX_UPLOAD_BYTES = 3 * 1024 * 1024
PROFILE_PHOTO_SIZE_PX = 256
PROFILE_PHOTO_SIDEBAR_PX = 64

PASSWORD_RESET_TOKEN_TTL_HOURS = 24
PASSWORD_RESET_CODE_LENGTH = 8
PASSWORD_RESET_CODE_TTL_SECONDS = 120
PASSWORD_RESET_CODE_MAX_ATTEMPTS = 5
PASSWORD_RESET_CODE_RESEND_COOLDOWN_SECONDS = 30
PASSWORD_RESET_VERIFIED_TTL_SECONDS = 300
PASSWORD_RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ANALYSIS_JOB_POLL_SECONDS = 1
ANALYSIS_JOB_STALE_SECONDS = 45 * 60
ANALYSIS_JOB_MAX_PDF_BYTES = 8 * 1024 * 1024


def canonical_nav_page(page: str | None) -> str | None:
    """Map a nav key or legacy alias onto the current sidebar page."""
    if page is None:
        return None
    key = str(page).strip().lower()
    if not key:
        return None
    mapped = NAV_PAGE_ALIASES.get(key, key)
    return mapped if mapped in NAV_PAGE_KEYS else None


def events_tab_for(page: str | None, *, fallback: str | None = "applications") -> str | None:
    """Return the Events sub-tab implied by a page key or alias."""
    key = str(page or "").strip().lower()
    if key in EVENTS_TAB_KEYS:
        return key
    if fallback in EVENTS_TAB_KEYS:
        return fallback
    return None
