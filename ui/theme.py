"""Modern design system — CSS injection for Streamlit."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# Career-platform tokens — LinkedIn trust + Welcome to the Jungle energy
THEME = {
    "bg_gradient": "linear-gradient(160deg, #F4F1EA 0%, #E7F1EE 48%, #DCE8F2 100%)",
    "bg_mesh": (
        "radial-gradient(ellipse 70% 50% at 8% 0%, rgba(14,116,144,0.16), transparent 55%), "
        "radial-gradient(ellipse 55% 45% at 96% 6%, rgba(232,185,35,0.20), transparent 50%)"
    ),
    "primary": "#0E7490",
    "primary_dark": "#155E75",
    "primary_deep": "#0B1220",
    "surface": "#ffffff",
    "surface_soft": "#F7F5F1",
    "surface_glass": "rgba(255, 255, 255, 0.82)",
    "muted": "#5B6573",
    "accent": "#E8B923",
    "success": "#0F9F6E",
    "warning": "#E8B923",
    "danger": "#E11D48",
    "radius_sm": "10px",
    "radius_md": "14px",
    "radius_lg": "18px",
    "radius_xl": "24px",
    "shadow_sm": "0 2px 10px rgba(11, 18, 32, 0.05)",
    "shadow_md": "0 14px 36px rgba(11, 18, 32, 0.08)",
    "shadow_lg": "0 28px 56px rgba(11, 18, 32, 0.12)",
    "font": 'system-ui, -apple-system, "Segoe UI", sans-serif',
}

CHAT_FAB_PATH = Path(__file__).resolve().parents[1] / "static" / "chat-fab.png"
_chat_fab_data_url_cache = ""


def chat_fab_data_url() -> str:
    global _chat_fab_data_url_cache
    if _chat_fab_data_url_cache:
        return _chat_fab_data_url_cache
    raw = CHAT_FAB_PATH.read_bytes()
    _chat_fab_data_url_cache = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    return _chat_fab_data_url_cache

NAV_ICONS: dict[str, str] = {
    "analysis": "📄",
    "dashboard": "▦",
    "applications": "☑️",
    "history": "🕓",
    "support": "💬",
    "profile": "👤",
}


def nav_label_with_icon(page_key: str, label: str) -> str:
    icon = NAV_ICONS.get(page_key, "•")
    return f"{icon}  {label}"


def _font_import() -> str:
    # System fonts only — skip Google Fonts so first paint is not blocked.
    return ""


def _shared_components_css(t: dict[str, str]) -> str:
    return f"""
        /* —— Motion —— */
        @keyframes db-rise {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes db-shine {{
            from {{ transform: translateX(-130%) skewX(-12deg); }}
            to {{ transform: translateX(220%) skewX(-12deg); }}
        }}
        @keyframes db-pulse-ring {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(14, 116, 144, 0.28); }}
            50% {{ box-shadow: 0 0 0 7px rgba(14, 116, 144, 0); }}
        }}

        /* —— Buttons (compact, used everywhere) —— */
        .stButton > button,
        div[data-testid="stFormSubmitButton"] button,
        .stDownloadButton > button,
        .stLinkButton a,
        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-tertiary"],
        [data-testid="stBaseButton-primaryFormSubmit"],
        [data-testid="stBaseButton-secondaryFormSubmit"],
        [data-testid^="stBaseLinkButton-"] {{
            font-family: {t["font"]} !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            line-height: 1.2 !important;
            min-height: 2rem !important;
            height: auto !important;
            padding: 0.22rem 0.75rem !important;
            border-radius: 999px !important;
            position: relative !important;
            overflow: hidden !important;
            letter-spacing: 0.01em !important;
            transition: transform 0.18s cubic-bezier(.2,.8,.2,1), box-shadow 0.18s ease, background 0.18s ease, border-color 0.18s ease !important;
        }}
        .stButton > button::after,
        div[data-testid="stFormSubmitButton"] button::after,
        .stDownloadButton > button::after,
        .stLinkButton a::after,
        [data-testid^="stBaseLinkButton-"]::after {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 42%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.38), transparent);
            transform: translateX(-130%) skewX(-12deg);
            pointer-events: none;
        }}
        .stButton > button:hover::after,
        div[data-testid="stFormSubmitButton"] button:hover::after,
        .stDownloadButton > button:hover::after,
        .stLinkButton a:hover::after,
        [data-testid^="stBaseLinkButton-"]:hover::after {{
            animation: db-shine 0.55s ease;
        }}
        .stButton > button:active,
        div[data-testid="stFormSubmitButton"] button:active,
        .stDownloadButton > button:active,
        .stLinkButton a:active {{
            transform: translateY(1px) scale(0.98) !important;
        }}
        .stButton,
        .stDownloadButton,
        .stLinkButton,
        [data-testid="stFormSubmitButton"] {{
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }}
        [data-testid="stHorizontalBlock"] .stButton,
        [data-testid="stHorizontalBlock"] .stDownloadButton,
        [data-testid="stHorizontalBlock"] .stLinkButton,
        [data-testid="stHorizontalBlock"] [data-testid="stFormSubmitButton"] {{
            align-self: stretch;
        }}
        [data-testid="stHorizontalBlock"] .stButton > button,
        [data-testid="stHorizontalBlock"] .stDownloadButton > button,
        [data-testid="stHorizontalBlock"] .stLinkButton a,
        [data-testid="stHorizontalBlock"] [data-testid^="stBaseLinkButton-"] {{
            width: 100%;
        }}
        div[data-testid="stElementContainer"]:has(.stButton),
        div[data-testid="stElementContainer"]:has(.stLinkButton),
        div[data-testid="stElementContainer"]:has(.stDownloadButton),
        div[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) {{
            margin-bottom: 0 !important;
        }}
        .stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button,
        .stDownloadButton > button {{
            background: linear-gradient(135deg, {t["primary"]} 0%, {t["primary_dark"]} 100%) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 3px 10px rgba(14, 116, 144, 0.28) !important;
        }}
        .stButton > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button:hover,
        .stDownloadButton > button:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 18px rgba(14, 116, 144, 0.32) !important;
            background: linear-gradient(135deg, {t["primary_dark"]} 0%, #0B4A5C 100%) !important;
            color: #fff !important;
        }}
        .stButton > button[kind="secondary"] {{
            background: {t["surface"]} !important;
            border: 1.5px solid rgba(14, 116, 144, 0.22) !important;
            color: {t["primary"]} !important;
        }}
        .stButton > button[kind="secondary"]:hover {{
            background: {t["surface_soft"]} !important;
            border-color: {t["primary"]} !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 14px rgba(14, 116, 144, 0.12) !important;
        }}

        /* —— Inputs —— */
        div[data-testid="stTextInput"] input,
       div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
            border-radius: {t["radius_sm"]} !important;
            border-color: rgba(14, 116, 144, 0.15) !important;
            font-family: {t["font"]} !important;
        }}
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {{
            border-color: {t["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(14, 116, 144, 0.12) !important;
        }}

        span[data-baseweb="tag"],
        [data-baseweb="tag"] {{
            background: rgba(14, 116, 144, 0.12) !important;
            color: {t["primary_dark"]} !important;
        }}
        [data-baseweb="tag"] span {{
            color: {t["primary_dark"]} !important;
        }}
        [data-testid="stSlider"] [role="slider"] {{
            background: {t["primary"]} !important;
        }}
        input[type="checkbox"],
        input[type="radio"],
        input[type="range"] {{
            accent-color: {t["primary"]} !important;
        }}
        [data-baseweb="checkbox"] > div:first-child {{
            border-color: {t["primary"]} !important;
        }}
        [data-baseweb="radio"] div[aria-checked="true"] {{
            background: {t["primary"]} !important;
            border-color: {t["primary"]} !important;
        }}
        label[data-testid="stWidgetLabel"] {{
            font-weight: 600 !important;
            color: {t["primary_deep"]} !important;
            font-size: 0.88rem !important;
        }}

        /* —— Metrics —— */
        [data-testid="stMetric"] {{
            background: linear-gradient(145deg, {t["surface"]} 0%, {t["surface_soft"]} 100%);
            border: 1px solid rgba(14, 116, 144, 0.08);
            border-radius: {t["radius_md"]};
            padding: 0.75rem 1rem;
            box-shadow: {t["shadow_sm"]};
        }}
        [data-testid="stMetricLabel"] {{
            color: {t["muted"]} !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        [data-testid="stMetricValue"] {{
            color: {t["primary_deep"]} !important;
            font-weight: 800 !important;
        }}

        /* —— Alerts —— */
        .main [data-testid="stAlert"],
        [data-testid="stSidebar"] [data-testid="stAlert"] {{
            border-radius: {t["radius_md"]} !important;
            border: none !important;
            box-shadow: {t["shadow_sm"]};
        }}

        /* —— Expanders —— */
        details[data-testid="stExpander"] {{
            background: {t["surface"]};
            border-radius: {t["radius_md"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            box-shadow: {t["shadow_sm"]};
        }}

        /* —— Progress —— */
        [data-testid="stProgressBar"] > div > div {{
            background: linear-gradient(90deg, {t["primary"]}, {t["accent"]}) !important;
            border-radius: 999px !important;
        }}

        h1, h2, h3, h4 {{
            font-family: {t["font"]} !important;
            color: {t["primary_deep"]} !important;
        }}
        .support-thread {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            border-radius: {t["radius_lg"]};
            padding: 1rem 1.1rem 1.15rem;
            max-height: 28rem;
            overflow-y: auto;
            margin-bottom: 0.75rem;
        }}
        .support-bubble {{
            max-width: min(86%, 36rem);
            padding: 0.7rem 0.9rem;
            border-radius: 16px;
            margin: 0.45rem 0;
        }}
        .support-bubble.user {{
            margin-left: auto;
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]});
            color: #fff;
            border-bottom-right-radius: 6px;
        }}
        .support-bubble.admin {{
            margin-right: auto;
            background: {t["surface_soft"]};
            color: {t["primary_deep"]};
            border: 1px solid rgba(14, 116, 144, 0.12);
            border-bottom-left-radius: 6px;
        }}
        .support-bubble .meta {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            opacity: 0.82;
            margin: 0 0 0.28rem;
        }}
        .support-bubble p {{
            margin: 0;
            white-space: pre-wrap;
            line-height: 1.45;
            font-size: 0.92rem;
        }}

        /* —— Messagerie page —— */
        .msg-title {{
            margin: 0;
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: {t["primary_deep"]};
        }}
        .msg-sub {{
            margin: 0.35rem 0 1.15rem;
            color: {t["muted"]};
            font-size: 1rem;
        }}
        .msg-list-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.6rem;
            margin-bottom: 0.35rem;
        }}
        .msg-list-head strong {{
            font-size: 1.02rem;
            color: {t["primary_deep"]};
        }}
        .msg-empty-list {{
            color: {t["muted"]};
            font-size: 0.9rem;
            line-height: 1.45;
            padding: 0.4rem 0.15rem 0.8rem;
        }}
        .msg-conv-item {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.12);
            border-radius: 12px;
            padding: 0.75rem 0.85rem;
            cursor: default;
        }}
        .msg-conv-item.active {{
            background: rgba(14, 116, 144, 0.08);
            border-color: rgba(14, 116, 144, 0.28);
        }}
        .msg-conv-item strong {{ display: block; color: {t["primary_deep"]}; }}
        .msg-conv-item small {{ color: {t["muted"]}; }}
        .msg-empty-pane {{
            min-height: 22rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            color: {t["muted"]};
            text-align: center;
        }}
        .msg-empty-pane svg {{
            width: 72px;
            height: 72px;
            opacity: 0.35;
        }}

        /* —— Floating chat logo (native link on document.body) —— */
        @keyframes db-chat-pulse {{
            0%, 100% {{
                transform: scale(1);
                box-shadow: 0 0 0 3px {t["accent"]}, 0 12px 26px rgba(14, 116, 144, 0.42);
            }}
            50% {{
                transform: scale(1.07);
                box-shadow: 0 0 0 3px {t["accent"]}, 0 16px 32px rgba(14, 116, 144, 0.5);
            }}
        }}
        #db-chat-fab {{
            position: fixed !important;
            right: 20px !important;
            bottom: 20px !important;
            z-index: 2147483647 !important;
            width: 64px !important;
            height: 64px !important;
            padding: 14px !important;
            border: 0 !important;
            border-radius: 50% !important;
            cursor: pointer !important;
            display: block !important;
            box-sizing: border-box !important;
            text-decoration: none !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            overflow: hidden !important;
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]}) !important;
            box-shadow: 0 0 0 3px {t["accent"]}, 0 12px 26px rgba(14, 116, 144, 0.42) !important;
            animation: db-chat-pulse 2.2s ease-in-out infinite !important;
        }}
        #db-chat-fab svg {{
            width: 100% !important;
            height: 100% !important;
            display: block !important;
            pointer-events: none !important;
        }}
        #db-chat-fab:hover {{
            animation: none !important;
            transform: scale(1.08) !important;
        }}
        #db-chat-fab-badge {{
            position: fixed !important;
            right: 16px !important;
            bottom: 76px !important;
            z-index: 2147483647 !important;
            min-width: 20px;
            height: 20px;
            padding: 0 6px;
            border-radius: 999px;
            background: {t["accent"]};
            color: #0B1220;
            font: 800 11px/20px system-ui, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
        }}
        [data-testid="stAppViewContainer"] {{
            overflow: hidden !important;
        }}
        [data-testid="stMain"],
        .main {{
            overflow-x: hidden !important;
            overflow-y: auto !important;
            height: 100vh !important;
        }}
        .main .block-container {{
            overflow: visible !important;
        }}
        .st-key-support_new button {{
            background: {t["primary"]} !important;
            color: #fff !important;
            border: 0 !important;
            box-shadow: 0 6px 16px rgba(14, 116, 144, 0.28) !important;
        }}
        .st-key-support_new button:hover {{
            filter: brightness(1.06);
        }}
        .main .block-container {{
            padding-bottom: 6.5rem;
            padding-right: 5.5rem;
        }}
    """


def render_app_styles() -> None:
    """Global styles for the authenticated app."""
    t = THEME
    st.markdown(
        f"""
        <style>
        {_font_import()}

        html, body, [data-testid="stAppViewContainer"] {{
            background: {t["bg_gradient"]} !important;
            font-family: {t["font"]};
        }}
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            inset: 0;
            background: {t["bg_mesh"]};
            pointer-events: none;
            z-index: 0;
        }}
        [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        [data-testid="stSidebarNav"] {{
            display: none !important;
        }}

        /* —— Sidebar (full-height rail, no gap on page scroll) —— */
        section[data-testid="stSidebar"] {{
            position: sticky !important;
            top: 0 !important;
            height: 100vh !important;
            min-height: 100vh !important;
            max-height: 100vh !important;
            transform: none !important;
            overflow: hidden !important;
            background:
                radial-gradient(ellipse 80% 40% at 50% 0%, rgba(232,185,35,0.16), transparent 55%),
                linear-gradient(180deg, #0B1628 0%, #0A1220 100%) !important;
            backdrop-filter: none;
            -webkit-backdrop-filter: none;
            border-right: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: 8px 0 28px rgba(11, 18, 32, 0.22);
        }}
        section[data-testid="stSidebar"] > div:first-child,
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarUserContent"] {{
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
            min-height: 100vh !important;
            max-height: 100vh !important;
            overflow-x: hidden !important;
            overflow-y: auto !important;
            padding-top: 1.1rem;
            background:
                radial-gradient(ellipse 80% 40% at 50% 0%, rgba(232,185,35,0.16), transparent 55%),
                linear-gradient(180deg, #0B1628 0%, #0A1220 100%) !important;
        }}
        [data-testid="stSidebarUserContent"] {{
            flex: 1 1 auto !important;
            min-height: 0 !important;
            padding-top: 0;
        }}
        [data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"],
        [data-testid="stSidebarContent"] > div > [data-testid="stVerticalBlock"] {{
            display: flex !important;
            flex-direction: column !important;
            flex: 1 1 auto !important;
            min-height: 100% !important;
        }}
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-flex-spacer) {{
            flex: 1 1 auto !important;
            min-height: 1.25rem !important;
        }}
        [data-testid="stSidebar"] .sidebar-brand {{
            text-align: center;
            padding: 0.35rem 0.35rem 1.1rem;
            margin-bottom: 0.35rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        [data-testid="stSidebar"] .sidebar-avatar-ring {{
            width: 64px;
            height: 64px;
            margin: 0 auto 0.7rem;
            border-radius: 50%;
            padding: 3px;
            background: linear-gradient(135deg, #F97316, {t["accent"]}, {t["primary"]});
            box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.22), 0 10px 22px rgba(249, 115, 22, 0.28);
        }}
        [data-testid="stSidebar"] .sidebar-avatar-img,
        [data-testid="stSidebar"] .sidebar-avatar-fallback {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #122033;
            color: #fff;
            font-weight: 800;
            font-size: 1.05rem;
        }}
        [data-testid="stSidebar"] .sidebar-logo {{
            width: 48px;
            height: 48px;
            margin: 0 auto 0.65rem;
            border-radius: 14px;
            background: linear-gradient(135deg, {t["primary"]}, {t["accent"]});
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.35rem;
            box-shadow: 0 8px 20px rgba(14, 116, 144, 0.35);
        }}
        [data-testid="stSidebar"] .sidebar-brand-name {{
            font-size: 1.05rem;
            font-weight: 800;
            color: #F8FAFC;
            margin: 0;
            letter-spacing: -0.02em;
        }}
        [data-testid="stSidebar"] .sidebar-brand-name span {{
            background: linear-gradient(135deg, {t["accent"]}, #F97316);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        [data-testid="stSidebar"] .sidebar-user {{
            font-size: 0.72rem;
            color: rgba(248, 250, 252, 0.62);
            margin: 0.3rem 0 0;
            font-weight: 500;
            word-break: break-all;
        }}
        [data-testid="stSidebar"] .sidebar-nav-label {{
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(248, 250, 252, 0.45);
            margin: 0.5rem 0 0.35rem 0.15rem;
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] .stMarkdown {{
            color: rgba(248, 250, 252, 0.86);
        }}

        /* Nav radio — icon rail */
        [data-testid="stSidebar"] div[data-testid="stRadio"] > div {{
            gap: 0.28rem;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 14px !important;
            padding: 0.55rem 0.7rem !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
            color: rgba(248, 250, 252, 0.82) !important;
            transition: all 0.2s cubic-bezier(.2,.8,.2,1) !important;
            position: relative;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {{
            border-color: rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.06);
            transform: none;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label[data-checked="true"],
        [data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {{
            background: rgba(255, 255, 255, 0.10) !important;
            color: #fff !important;
            border-color: transparent !important;
            box-shadow: none;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked)::before {{
            content: "";
            position: absolute;
            left: 0;
            top: 8px;
            bottom: 8px;
            width: 3px;
            border-radius: 999px;
            background: #F97316;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background: rgba(255, 255, 255, 0.06) !important;
            color: #fff !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
        }}

        /* —— Main —— */
        .main .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 6.5rem;
            padding-right: 5.5rem;
            max-width: 1100px;
        }}
        .main [data-testid="stVerticalBlock"] {{
            gap: 0.5rem !important;
        }}

        .app-page-hero {{
            position: relative;
            background: {t["surface"]};
            border-radius: {t["radius_xl"]};
            padding: 1.75rem 2rem;
            margin-bottom: 1.5rem;
            box-shadow: {t["shadow_md"]};
            border: 1px solid rgba(255, 255, 255, 0.8);
            overflow: hidden;
            animation: db-rise 0.18s ease both;
        }}
        .app-page-hero::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, {t["primary"]}, {t["accent"]}, #E8B923);
        }}
        .app-page-hero h1 {{
            margin: 0 0 0.4rem 0;
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: {t["primary_deep"]};
        }}
        .app-page-hero p {{
            margin: 0;
            color: {t["muted"]};
            font-size: 0.98rem;
            line-height: 1.55;
            max-width: 52rem;
        }}
        .app-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: linear-gradient(135deg, rgba(14,116,144,0.1), rgba(232,185,35,0.08));
            color: {t["primary"]};
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(14, 116, 144, 0.12);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {t["surface"]} !important;
            border-radius: {t["radius_lg"]} !important;
            border: 1px solid rgba(14, 116, 144, 0.06) !important;
            box-shadow: {t["shadow_md"]} !important;
            padding: 0.5rem 0.65rem 0.85rem !important;
        }}

        .section-title {{
            font-size: 1.1rem;
            font-weight: 700;
            color: {t["primary_deep"]};
            margin: 0 0 0.75rem 0;
        }}

        /* —— Job cards —— */
        .job-match-card {{
            background: {t["surface"]};
            border-radius: {t["radius_lg"]};
            padding: 1.35rem 1.6rem 0.65rem;
            margin-bottom: 1.1rem;
            border: 1px solid rgba(14, 116, 144, 0.08);
            box-shadow: {t["shadow_sm"]};
            border-left: 4px solid {t["primary"]};
            transition: box-shadow 0.22s ease, transform 0.22s ease, border-color 0.22s ease;
            animation: db-rise 0.16s ease both;
        }}
        .job-match-card:hover {{
            box-shadow: {t["shadow_md"]};
            transform: translateY(-4px);
            border-left-color: {t["accent"]};
        }}
        .job-match-card h3 {{
            color: {t["primary_deep"]};
            margin-top: 0;
            font-weight: 700;
        }}
        .job-score-pill {{
            text-align: center;
            padding: 1rem;
            border-radius: {t["radius_md"]};
        }}

        /* —— Profile —— */
        .profile-header-card {{
            display: flex;
            align-items: center;
            gap: 1.35rem;
            padding: 1.6rem 1.85rem;
            margin-bottom: 1.35rem;
            border-radius: {t["radius_lg"]};
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            box-shadow: {t["shadow_md"]};
            animation: db-rise 0.16s ease both;
        }}
        .profile-avatar {{
            width: 72px;
            height: 72px;
            border-radius: 50%;
            background: linear-gradient(135deg, {t["primary"]}, {t["accent"]});
            color: #fff;
            font-size: 1.4rem;
            font-weight: 800;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            overflow: hidden;
            box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.28), 0 8px 20px rgba(14, 116, 144, 0.3);
        }}
        .profile-avatar img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}
        .profile-header-text h2 {{
            margin: 0 0 0.2rem 0 !important;
            font-size: 1.4rem !important;
            font-weight: 800 !important;
        }}
        .profile-header-text p {{
            margin: 0 0 0.5rem 0;
            color: {t["muted"]};
        }}
        .profile-badge {{
            display: inline-block;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            background: rgba(14, 116, 144, 0.08);
            color: {t["primary_dark"]};
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .profile-section-hint {{
            color: {t["muted"]};
            font-size: 0.88rem;
            margin: 0 0 0.85rem 0;
        }}
        .profile-chip-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.65rem;
        }}
        .profile-chip {{
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            background: rgba(14, 116, 144, 0.08);
            color: {t["primary_dark"]};
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .profile-header-card {{
            margin-top: 0.15rem;
        }}
        .profile-header-meta {{
            color: {t["muted"]};
            font-size: 0.9rem;
            margin: 0.15rem 0 0 !important;
        }}
        .profile-section-card {{
            margin: 0;
        }}
        .profile-divider {{
            border: 0;
            height: 1px;
            margin: 1.4rem 0 1.1rem;
            background: linear-gradient(90deg, rgba(14,116,144,0.25), transparent);
        }}
        .job-match-card {{
            padding: 1.1rem 1.25rem 0.55rem;
        }}

        .stat-card-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.85rem;
            margin: 0 0 1.2rem 0;
        }}
        .stat-card {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.1);
            border-radius: {t["radius_md"]};
            padding: 1rem 1.1rem 0.95rem;
            box-shadow: {t["shadow_sm"]};
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-3px);
            box-shadow: {t["shadow_md"]};
        }}
        .stat-card::after {{
            content: "";
            position: absolute;
            right: -12px;
            bottom: -18px;
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, rgba(14,116,144,0.12), transparent);
        }}
        .stat-card-label {{
            margin: 0;
            color: {t["muted"]};
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .stat-card-value {{
            margin: 0.25rem 0 0.1rem;
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: {t["primary_deep"]};
        }}
        .stat-card-hint {{
            margin: 0;
            color: {t["muted"]};
            font-size: 0.78rem;
        }}
        .empty-panel {{
            text-align: center;
            background: {t["surface"]};
            border-radius: {t["radius_xl"]};
            padding: 2.4rem 1.5rem;
            box-shadow: {t["shadow_md"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            margin-bottom: 1rem;
            animation: db-rise 0.18s ease both;
        }}
        .empty-panel h2 {{
            margin: 0.4rem 0 0.35rem;
            color: {t["primary_deep"]};
            font-size: 1.35rem;
        }}
        .empty-panel p {{
            margin: 0 auto;
            max-width: 32rem;
            color: {t["muted"]};
        }}
        .empty-icon {{
            font-size: 2rem;
        }}
        .dash-meta-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.35rem 0 1rem;
        }}
        .dash-meta-pill {{
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.7rem;
            border-radius: 999px;
            background: rgba(14, 116, 144, 0.08);
            color: {t["primary_deep"]};
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .dash-results-line {{
            color: {t["muted"]};
            font-size: 0.88rem;
            font-weight: 600;
            margin: 0.35rem 0 0.85rem;
        }}
        .filter-bar-title {{
            margin: 0 0 0.35rem;
            color: {t["primary_deep"]};
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .dash-chart-panel {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            border-radius: {t["radius_lg"]};
            padding: 0.75rem 0.85rem 0.45rem;
            box-shadow: {t["shadow_sm"]};
            margin-bottom: 0.85rem;
        }}
        .dash-quality {{
            display: flex;
            flex-direction: column;
            gap: 0.9rem;
            margin: 0 0 1.1rem;
        }}
        .dash-quality-kpis {{
            display: grid;
            grid-template-columns: 1.35fr repeat(3, 1fr);
            gap: 0.85rem;
        }}
        .dash-quality-hero {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 0.9rem;
            align-items: center;
        }}
        .dash-quality-title {{
            font-size: 1.05rem !important;
            margin: 0.15rem 0 0.2rem !important;
        }}
        .dash-score-ring {{
            width: 74px;
            height: 74px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            background: conic-gradient(var(--ring, {t["primary"]}) calc(var(--p, 0) * 1%), #E7F1EE 0);
            flex-shrink: 0;
        }}
        .dash-score-ring span {{
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: #fff;
            display: grid;
            place-items: center;
            font-weight: 800;
            font-size: 1.05rem;
            letter-spacing: -0.03em;
            color: {t["primary_deep"]};
        }}
        .dash-quality-split {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.85rem;
        }}
        .dash-quality-panel {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            border-radius: {t["radius_lg"]};
            padding: 0.95rem 1rem 1rem;
            box-shadow: {t["shadow_sm"]};
        }}
        .dash-quality-panel h3 {{
            margin: 0;
            font-size: 0.95rem;
            color: {t["primary_deep"]};
        }}
        .dash-quality-panel > p {{
            margin: 0.2rem 0 0.75rem;
            color: {t["muted"]};
            font-size: 0.78rem;
        }}
        .dash-band-list, .dash-top-list {{
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
        }}
        .dash-band {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 0.3rem;
            font-size: 0.8rem;
            font-weight: 600;
            color: {t["primary_deep"]};
        }}
        .dash-band .meta {{
            color: {t["muted"]};
            font-variant-numeric: tabular-nums;
        }}
        .dash-band-track {{
            grid-column: 1 / -1;
            height: 8px;
            border-radius: 999px;
            background: #E7F1EE;
            overflow: hidden;
        }}
        .dash-band-track i {{
            display: block;
            height: 100%;
            border-radius: inherit;
        }}
        .dash-band-track i.high {{ background: {t["success"]}; }}
        .dash-band-track i.mid {{ background: {t["accent"]}; }}
        .dash-band-track i.low {{ background: {t["danger"]}; }}
        .dash-top-match {{
            display: grid;
            grid-template-columns: 48px 1fr;
            gap: 0.7rem;
            align-items: center;
            padding: 0.55rem 0.65rem;
            border-radius: 14px;
            border: 1px solid rgba(14, 116, 144, 0.08);
            background: linear-gradient(180deg, #fff, {t["surface_soft"]});
        }}
        .dash-top-match strong {{
            display: block;
            font-size: 0.88rem;
            color: {t["primary_deep"]};
        }}
        .dash-top-match small {{
            color: {t["muted"]};
            font-size: 0.74rem;
        }}
        .dash-score-pill {{
            width: 48px;
            height: 48px;
            border-radius: 14px;
            display: grid;
            place-items: center;
            font-weight: 800;
            color: #fff;
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]});
        }}
        .dash-score-pill.high {{ background: linear-gradient(135deg, #0F9F6E, #0B7A55); }}
        .dash-score-pill.mid {{ background: linear-gradient(135deg, #E8B923, #C49212); color: #0B1220; }}
        .dash-score-pill.low {{ background: linear-gradient(135deg, #FB7185, #E11D48); }}
        .dash-empty-insight {{
            margin: 0.4rem 0 0;
            color: {t["muted"]};
            font-size: 0.86rem;
        }}
        .job-card-head {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
            margin-bottom: 0.55rem;
        }}
        .job-card-kicker {{
            margin: 0 0 0.2rem;
            color: {t["muted"]};
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}
        .job-card-title {{
            margin: 0 0 0.25rem !important;
            font-size: 1.15rem !important;
            font-weight: 800 !important;
            color: {t["primary_deep"]} !important;
            line-height: 1.3 !important;
        }}
        .job-card-sub {{
            margin: 0;
            color: {t["muted"]};
            font-size: 0.9rem;
        }}
        .job-card-facts {{
            margin: 0 0 0.45rem;
            color: {t["muted"]};
            font-size: 0.86rem;
            line-height: 1.55;
        }}
        .job-card-facts span {{
            display: inline-block;
            margin-right: 0.85rem;
        }}
        .job-score-badge {{
            min-width: 4.6rem;
            text-align: center;
            padding: 0.55rem 0.7rem 0.5rem;
            border-radius: 16px;
            flex-shrink: 0;
        }}
        .job-score-badge strong {{
            display: block;
            font-size: 1.4rem;
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.03em;
        }}
        .job-score-badge small {{
            color: {t["muted"]};
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .score-chip-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.2rem 0 0.65rem;
        }}
        .score-chip {{
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.65rem;
            border-radius: 999px;
            background: {t["surface_soft"]};
            border: 1px solid rgba(14, 116, 144, 0.1);
            color: {t["primary_deep"]};
            font-size: 0.78rem;
            font-weight: 700;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.35rem;
            background: rgba(255,255,255,0.55);
            padding: 0.35rem;
            border-radius: 999px;
            border: 1px solid rgba(14, 116, 144, 0.08);
            margin-bottom: 0.85rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 999px !important;
            font-weight: 700 !important;
            color: {t["muted"]} !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: #fff !important;
            color: {t["primary"]} !important;
            box-shadow: 0 4px 12px rgba(11, 18, 32, 0.1);
        }}
        @media (max-width: 900px) {{
            .stat-card-grid, .dash-quality-kpis, .dash-quality-split {{
                grid-template-columns: 1fr 1fr;
            }}
            .job-card-head {{
                flex-direction: column;
            }}
        }}
        @media (max-width: 560px) {{
            .stat-card-grid, .dash-quality-kpis, .dash-quality-split {{
                grid-template-columns: 1fr;
            }}
            .profile-header-card {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}

        /* —— Delete / danger zone —— */
        .danger-zone,
        .delete-account-zone {{
            margin-top: 0.15rem;
            padding: 0;
            border: 0;
            background: transparent;
        }}
        .danger-zone-kicker {{
            margin: 0 0 0.55rem;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #BE123C;
        }}
        .danger-zone-row {{
            display: flex;
            gap: 0.85rem;
            align-items: flex-start;
        }}
        .danger-zone-icon {{
            flex: 0 0 2.35rem;
            width: 2.35rem;
            height: 2.35rem;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.05rem;
            font-weight: 800;
            color: #fff;
            background: linear-gradient(135deg, #FB7185, #E11D48);
            box-shadow: 0 8px 18px rgba(225, 29, 72, 0.28);
        }}
        .danger-zone-title,
        .delete-account-zone .delete-account-title {{
            color: #9F1239;
            font-weight: 800;
            font-size: 1.08rem;
            letter-spacing: -0.02em;
            margin: 0 0 0.28rem;
        }}
        .danger-zone-text,
        .delete-account-zone .delete-account-text {{
            color: #4C0519;
            font-size: 0.9rem;
            line-height: 1.45;
            margin: 0;
        }}
        .danger-zone-confirm {{
            margin: 0.15rem 0 0.35rem;
            color: #9F1239;
            font-size: 0.9rem;
            font-weight: 600;
        }}

        /* —— Support chat —— */
        .support-thread {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.08);
            border-radius: {t["radius_lg"]};
            padding: 1rem 1.1rem 1.15rem;
            box-shadow: {t["shadow_sm"]};
            max-height: 28rem;
            overflow-y: auto;
            margin-bottom: 0.75rem;
        }}
        .support-bubble {{
            max-width: min(86%, 36rem);
            padding: 0.7rem 0.9rem;
            border-radius: 16px;
            margin: 0.45rem 0;
            animation: db-rise 0.16s ease both;
        }}
        .support-bubble.user {{
            margin-left: auto;
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]});
            color: #fff;
            border-bottom-right-radius: 6px;
        }}
        .support-bubble.admin {{
            margin-right: auto;
            background: {t["surface_soft"]};
            color: {t["primary_deep"]};
            border: 1px solid rgba(14, 116, 144, 0.12);
            border-bottom-left-radius: 6px;
        }}
        .support-bubble .meta {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            opacity: 0.82;
            margin: 0 0 0.28rem;
        }}
        .support-bubble p {{
            margin: 0;
            white-space: pre-wrap;
            line-height: 1.45;
            font-size: 0.92rem;
        }}
        .support-inbox-item {{
            padding: 0.75rem 0.85rem;
            border-radius: 14px;
            border: 1px solid rgba(14, 116, 144, 0.1);
            background: {t["surface"]};
            margin-bottom: 0.5rem;
        }}
        .support-inbox-item strong {{ display: block; }}
        .support-inbox-item small {{ color: {t["muted"]}; }}
        .support-space-header {{
            background: {t["surface"]};
            border: 1px solid rgba(14, 116, 144, 0.12);
            border-radius: {t["radius_lg"]};
            padding: 0.85rem 1rem 0.95rem;
            margin-bottom: 0.7rem;
            box-shadow: {t["shadow_sm"]};
        }}
        .support-space-header strong {{ display: block; font-size: 1.05rem; }}
        .support-space-header small {{ display: block; color: {t["muted"]}; margin: 0.15rem 0 0.35rem; }}
        .support-space-header span {{ display: block; font-size: 0.78rem; color: {t["primary"]}; font-weight: 600; }}

        /* —— File uploader —— */
        [data-testid="stFileUploader"] section {{
            background: {t["surface_soft"]};
            border: 2px dashed rgba(14, 116, 144, 0.2);
            border-radius: {t["radius_lg"]};
            padding: 0.75rem;
            transition: border-color 0.2s ease;
        }}
        [data-testid="stFileUploader"] section:hover {{
            border-color: {t["primary"]};
        }}

        {_shared_components_css(t)}

        /* Late overrides — beat compact button styles */
        [data-testid="stSidebar"] [class*="st-key-sidebar_locale_select"] {{
            padding-top: 0.85rem;
        }}
        [data-testid="stSidebar"] [class*="st-key-logout_button"] {{
            margin-top: auto !important;
            margin-bottom: 0 !important;
            padding: 0.85rem 0 1.15rem;
            position: sticky;
            bottom: 0;
            z-index: 3;
            background: linear-gradient(180deg, rgba(10, 18, 32, 0) 0%, #0A1220 32%);
        }}
        [data-testid="stSidebar"] [class*="st-key-logout_button"] button,
        [data-testid="stSidebar"] [class*="st-key-logout_button"] [data-testid="stBaseButton-secondary"],
        [data-testid="stSidebar"] [class*="st-key-logout_button"] [data-testid="stBaseButton-primary"] {{
            width: 100% !important;
            min-height: 2.4rem !important;
            height: auto !important;
            padding: 0.55rem 0.85rem !important;
            border-radius: 12px !important;
            background: rgba(225, 29, 72, 0.08) !important;
            color: #FECDD3 !important;
            border: 1px solid rgba(251, 113, 133, 0.32) !important;
            box-shadow: none !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
        }}
        [data-testid="stSidebar"] [class*="st-key-logout_button"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-logout_button"] [data-testid="stBaseButton-secondary"]:hover {{
            background: rgba(225, 29, 72, 0.22) !important;
            color: #fff !important;
            border-color: rgba(251, 113, 133, 0.55) !important;
            transform: none !important;
            filter: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.danger-zone),
        div[data-testid="stElementContainer"]:has(.delete-account-zone) {{
            background: linear-gradient(180deg, #fff 0%, #FFF1F2 100%);
            border: 1px solid rgba(225, 29, 72, 0.16);
            border-bottom: 0;
            border-radius: 18px 18px 0 0;
            padding: 1.15rem 1.2rem 0.35rem;
            box-shadow: 0 18px 40px rgba(159, 18, 57, 0.08);
            margin-bottom: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.danger-zone) + div[data-testid="stElementContainer"],
        div[data-testid="stElementContainer"]:has(.danger-zone-confirm) {{
            background: #FFF1F2;
            border-color: rgba(225, 29, 72, 0.16);
            border-style: solid;
            border-width: 0 1px;
            padding: 0.2rem 1.2rem 0.35rem;
            margin-bottom: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has([class*="st-key-delete_account_btn"]),
        div[data-testid="stElementContainer"]:has([class*="st-key-delete_account_yes"]),
        div[data-testid="stElementContainer"]:has([class*="st-key-delete_account_no"]) {{
            background: #FFF1F2;
            border: 1px solid rgba(225, 29, 72, 0.16);
            border-top: 0;
            border-radius: 0 0 18px 18px;
            padding: 0.15rem 1.2rem 1.15rem;
            box-shadow: 0 18px 40px rgba(159, 18, 57, 0.08);
        }}
        [class*="st-key-delete_account_btn"] button,
        [class*="st-key-delete_account_btn"] [data-testid="stBaseButton-secondary"],
        [class*="st-key-delete_account_btn"] [data-testid="stBaseButton-primary"] {{
            background: #fff !important;
            color: #E11D48 !important;
            border: 1.5px solid rgba(225, 29, 72, 0.38) !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            box-shadow: none !important;
            min-height: 2.45rem !important;
        }}
        [class*="st-key-delete_account_btn"] button:hover {{
            background: #E11D48 !important;
            color: #fff !important;
            transform: none !important;
        }}
        [class*="st-key-delete_account_yes"] button,
        [class*="st-key-delete_account_yes"] [data-testid="stBaseButton-secondary"],
        [class*="st-key-delete_account_yes"] [data-testid="stBaseButton-primary"] {{
            background: linear-gradient(135deg, #E11D48, #BE123C) !important;
            color: #fff !important;
            border: 0 !important;
            box-shadow: 0 8px 18px rgba(225, 29, 72, 0.28) !important;
        }}
        [class*="st-key-delete_account_no"] button {{
            background: #fff !important;
            color: #0B1220 !important;
            border: 1.5px solid rgba(11, 18, 32, 0.12) !important;
            box-shadow: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_styles() -> None:
    """Split-screen login / register styles — 2026 form rhythm."""
    t = THEME
    split = '#auth-split-screen + div[data-testid="stHorizontalBlock"]'
    split_left = f'{split} > div[data-testid="column"]:first-child'
    split_right = f'{split} > div[data-testid="column"]:last-child'
    lang_row = '.auth-lang-bar-marker + div[data-testid="stHorizontalBlock"]'
    forgot_row = '.auth-forgot-row-marker + div[data-testid="stHorizontalBlock"]'
    signup_row = '.auth-signup-row-marker + div[data-testid="stHorizontalBlock"]'
    st.markdown(
        f"""
        <style>
        {_font_import()}

        [data-testid="stAppViewContainer"] {{
            background: {t["bg_mesh"]}, {t["bg_gradient"]};
            font-family: {t["font"]};
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"], footer {{
            visibility: hidden;
            height: 0;
        }}
        .block-container {{
            padding-top: 4.5vh;
            padding-bottom: 4.5vh;
            max-width: 1080px;
        }}
        #auth-split-screen,
        .auth-lang-bar-marker,
        .auth-forgot-row-marker,
        .auth-signup-row-marker,
        .auth-back-link-marker {{
            display: none;
        }}
        {split} {{
            gap: 1.75rem !important;
            position: relative;
            align-items: stretch !important;
            border-radius: 0;
            overflow: visible;
            box-shadow: none;
            padding-bottom: 0;
            background: transparent !important;
        }}
        {split} > div[data-testid="column"] {{
            padding: 0 !important;
        }}
        {split_left} > div {{
            background: transparent !important;
            border-radius: 0;
            min-height: 620px;
            height: 100%;
            padding: 0.5rem 0 !important;
        }}
        {split_right} > div {{
            background: {t["surface"]};
            border-radius: 24px;
            box-shadow: 0 24px 56px rgba(11, 18, 32, 0.12), 0 8px 22px rgba(15, 23, 42, 0.06);
            border: 1px solid rgba(14, 116, 144, 0.08);
            min-height: 620px;
            height: 100%;
            padding: 1.65rem 2.35rem 2rem !important;
            display: flex;
            flex-direction: column;
        }}
        {lang_row} {{
            margin: 0 0 1.15rem !important;
            align-items: center !important;
        }}
        {split_right} [class*="st-key-auth_top_locale_select"] {{
            margin: 0 !important;
        }}
        {split_right} [class*="st-key-auth_top_locale_select"] [data-baseweb="select"] > div {{
            min-height: 2.2rem !important;
            border-radius: 12px !important;
            background: {t["surface_soft"]} !important;
            border-color: rgba(14, 116, 144, 0.14) !important;
        }}
        .auth-panel-right-inner {{
            display: flex;
            flex-direction: column;
            flex: 1;
            min-height: 100%;
        }}
        {forgot_row} {{
            margin: 0.15rem 0 0.35rem !important;
            align-items: center !important;
        }}
        {signup_row} {{
            margin-top: 1.35rem !important;
            padding-top: 1.1rem;
            border-top: 1px solid rgba(14, 116, 144, 0.12);
            align-items: center !important;
        }}
        .auth-no-account {{
            margin: 0;
            color: {t["muted"]};
            font-size: 0.9rem;
            font-weight: 500;
            text-align: right;
            line-height: 1.3;
            padding: 0.15rem 0.2rem 0 0;
        }}
        .auth-left-panel {{
            color: {t["primary_deep"]};
            text-align: center;
            padding: 1.75rem 1.15rem 2rem;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .auth-illustration-wrap {{
            background: linear-gradient(165deg, #0E7490 0%, #155E75 52%, #0B4A5C 100%);
            border-radius: 22px;
            padding: 1.4rem 1.15rem 1.55rem;
            margin-bottom: 1.45rem;
            width: min(100%, 320px);
            box-shadow: 0 18px 40px rgba(14, 116, 144, 0.22);
        }}
        .auth-illustration {{
            width: min(100%, 270px);
            margin: 0 auto;
            display: block;
            border-radius: 12px;
        }}
        .auth-left-title {{
            font-size: 1.08rem;
            line-height: 1.5;
            font-weight: 700;
            margin: 0 0 0.7rem;
            color: {t["primary_deep"]};
            max-width: 19rem;
        }}
        .auth-left-tip {{
            font-size: 0.86rem;
            line-height: 1.5;
            color: {t["muted"]};
            max-width: 17rem;
        }}
        .auth-greeting-main {{
            font-size: 0.88rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            color: {t["muted"]};
            margin: 0 0 0.2rem;
        }}
        .auth-greeting-sub {{
            font-size: 1.85rem;
            font-weight: 800;
            color: {t["primary_deep"]};
            margin: 0 0 0.55rem;
            letter-spacing: -0.035em;
            line-height: 1.15;
        }}
        .auth-form-title {{
            font-size: 0.95rem;
            color: {t["muted"]};
            margin: 0 0 1.35rem;
            line-height: 1.4;
        }}
        {split_right} [data-testid="stWidgetLabel"] p {{
            font-size: 0.8rem !important;
            font-weight: 650 !important;
            color: {t["primary_deep"]} !important;
            letter-spacing: 0.01em;
        }}
        {split_right} div[data-testid="stTextInput"] {{
            margin-bottom: 0.85rem;
        }}
        {split_right} div[data-testid="stTextInput"] input {{
            background: {t["surface"]} !important;
            border: 1.5px solid rgba(14, 116, 144, 0.18) !important;
            border-radius: 14px !important;
            min-height: 2.85rem !important;
            padding: 0.7rem 0.95rem !important;
            font-size: 0.95rem !important;
            color: {t["primary_deep"]} !important;
        }}
        {split_right} div[data-testid="stTextInput"] input:focus {{
            border-color: {t["primary"]} !important;
            box-shadow: 0 0 0 4px rgba(14, 116, 144, 0.12) !important;
        }}
        {split_right} div[data-testid="stFormSubmitButton"] button {{
            width: 100%;
            margin-top: 0.35rem;
        }}
        .reg-wizard-track {{
            display: flex;
            gap: 0.35rem;
            margin: 0 0 1.35rem 0;
            overflow-x: auto;
            padding-bottom: 0.25rem;
        }}
        .reg-wizard-step {{
            flex: 1;
            min-width: 0;
            text-align: center;
            opacity: 0.45;
        }}
        .reg-wizard-step.active,
        .reg-wizard-step.done {{
            opacity: 1;
        }}
        .reg-wizard-dot {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.65rem;
            height: 1.65rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            background: #e2e8f0;
            color: #64748b;
            margin-bottom: 0.25rem;
        }}
        .reg-wizard-step.active .reg-wizard-dot {{
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]});
            color: #fff;
        }}
        .reg-wizard-step.done .reg-wizard-dot {{
            background: #9FD6D2;
            color: {t["primary_deep"]};
        }}
        .reg-wizard-label {{
            display: block;
            font-size: 0.62rem;
            font-weight: 600;
            color: {t["muted"]};
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .reg-wizard-nav {{
            margin-top: 0.85rem;
        }}
        {_shared_components_css(t)}

        /* Auth form actions — beat compact global pills */
        {forgot_row} .stButton > button,
        {forgot_row} [data-testid="stBaseButton-secondary"],
        [class*="st-key-auth_go_reset"] button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {t["primary"]} !important;
            font-size: 0.82rem !important;
            font-weight: 650 !important;
            padding: 0.15rem 0 !important;
            min-height: 0 !important;
            height: auto !important;
            border-radius: 0 !important;
            text-decoration: none !important;
            width: 100%;
            justify-content: flex-end !important;
        }}
        {forgot_row} .stButton > button:hover,
        [class*="st-key-auth_go_reset"] button:hover {{
            color: {t["primary_dark"]} !important;
            transform: none !important;
            text-decoration: underline !important;
            text-underline-offset: 3px !important;
            box-shadow: none !important;
        }}
        [class*="st-key-auth_login_submit"] button,
        [class*="st-key-auth_login_submit"] [data-testid="stBaseButton-primary"] {{
            width: 100% !important;
            min-height: 2.9rem !important;
            height: auto !important;
            margin-top: 0.55rem !important;
            padding: 0.72rem 1.1rem !important;
            border-radius: 14px !important;
            font-size: 0.95rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
            box-shadow: 0 8px 20px rgba(14, 116, 144, 0.28) !important;
        }}
        {split_right} div[data-testid="stFormSubmitButton"] button {{
            min-height: 2.75rem !important;
            padding: 0.65rem 1rem !important;
            border-radius: 14px !important;
            font-size: 0.92rem !important;
        }}
        [class*="st-key-auth_go_register"] button,
        [class*="st-key-auth_go_register"] [data-testid="stBaseButton-secondary"] {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {t["primary"]} !important;
            font-size: 0.9rem !important;
            font-weight: 750 !important;
            padding: 0.15rem 0 !important;
            min-height: 0 !important;
            height: auto !important;
            border-radius: 0 !important;
            width: auto !important;
            justify-content: flex-start !important;
        }}
        [class*="st-key-auth_go_register"] button:hover {{
            color: {t["primary_dark"]} !important;
            transform: none !important;
            text-decoration: underline !important;
            text-underline-offset: 3px !important;
            box-shadow: none !important;
            background: transparent !important;
        }}
        [class*="st-key-auth_go_login"] button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {t["primary"]} !important;
            font-weight: 650 !important;
            font-size: 0.88rem !important;
            padding: 0.35rem 0 !important;
            min-height: 0 !important;
            justify-content: flex-start !important;
        }}
        .reg-wizard-nav button {{
            min-height: 2.45rem !important;
            border-radius: 12px !important;
        }}
        .reg-wizard-nav [data-testid="column"]:first-child button {{
            background: {t["surface_soft"]} !important;
            border: 1.5px solid rgba(14, 116, 144, 0.22) !important;
            color: {t["primary_deep"]} !important;
            font-weight: 600 !important;
        }}
        .reg-wizard-nav [data-testid="column"]:first-child button:hover {{
            border-color: {t["primary"]} !important;
            color: {t["primary"]} !important;
        }}
        @media (max-width: 768px) {{
            .block-container {{
                padding-top: 1.25rem;
                padding-bottom: 1.5rem;
            }}
            {split} {{
                gap: 1rem !important;
            }}
            {split_left} > div,
            {split_right} > div {{
                min-height: auto;
            }}
            {split_right} > div {{
                border-radius: 20px;
                padding: 1.25rem 1.2rem 1.5rem !important;
            }}
            .auth-illustration-wrap {{
                width: min(100%, 260px);
            }}
            .auth-greeting-sub {{
                font-size: 1.55rem;
            }}
            .auth-no-account {{
                text-align: left;
            }}
            .reg-wizard-track {{
                flex-wrap: wrap;
                gap: 0.35rem;
            }}
            .reg-wizard-label {{
                display: none;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
