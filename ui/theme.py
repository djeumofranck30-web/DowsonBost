"""Modern design system — CSS injection for Streamlit."""

from __future__ import annotations

import streamlit as st

# Design tokens (purple SaaS — DowsonBost)
THEME = {
    "bg_gradient": "linear-gradient(145deg, #ede9fe 0%, #ddd6fe 35%, #c4b5fd 70%, #a78bfa 100%)",
    "bg_mesh": (
        "radial-gradient(ellipse 80% 60% at 10% 20%, rgba(124,58,237,0.18), transparent 50%), "
        "radial-gradient(ellipse 60% 50% at 90% 80%, rgba(99,102,241,0.15), transparent 45%)"
    ),
    "primary": "#7c3aed",
    "primary_dark": "#6d28d9",
    "primary_deep": "#1e1b4b",
    "surface": "#ffffff",
    "surface_soft": "#f8fafc",
    "surface_glass": "rgba(255, 255, 255, 0.72)",
    "muted": "#64748b",
    "accent": "#6366f1",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "radius_sm": "10px",
    "radius_md": "14px",
    "radius_lg": "20px",
    "radius_xl": "24px",
    "shadow_sm": "0 2px 8px rgba(30, 27, 75, 0.06)",
    "shadow_md": "0 12px 32px rgba(76, 29, 149, 0.12)",
    "shadow_lg": "0 24px 48px rgba(76, 29, 149, 0.16)",
    "font": '"Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", sans-serif',
}

NAV_ICONS: dict[str, str] = {
    "analysis": "🎯",
    "dashboard": "📊",
    "history": "🕘",
    "profile": "👤",
}


def nav_label_with_icon(page_key: str, label: str) -> str:
    icon = NAV_ICONS.get(page_key, "•")
    return f"{icon}  {label}"


def _font_import() -> str:
    return (
        "@import url('https://fonts.googleapis.com/css2?"
        "family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');"
    )


def _shared_components_css(t: dict[str, str]) -> str:
    return f"""
        /* —— Buttons (modern pill + lift) —— */
        .stButton > button,
        div[data-testid="stFormSubmitButton"] button,
        .stDownloadButton > button {{
            font-family: {t["font"]} !important;
            font-weight: 600 !important;
            border-radius: 12px !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
        }}
        .stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button,
        .stDownloadButton > button {{
            background: linear-gradient(135deg, {t["primary"]} 0%, {t["primary_dark"]} 100%) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35) !important;
        }}
        .stButton > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button:hover,
        .stDownloadButton > button:hover {{
            transform: translateY(-1px) !important;
            box-shadow: 0 8px 22px rgba(124, 58, 237, 0.42) !important;
            background: linear-gradient(135deg, {t["primary_dark"]} 0%, #5b21b6 100%) !important;
            color: #fff !important;
        }}
        .stButton > button[kind="secondary"] {{
            background: {t["surface"]} !important;
            border: 1.5px solid rgba(124, 58, 237, 0.22) !important;
            color: {t["primary"]} !important;
        }}
        .stButton > button[kind="secondary"]:hover {{
            background: {t["surface_soft"]} !important;
            border-color: {t["primary"]} !important;
            transform: translateY(-1px) !important;
        }}

        /* —— Inputs —— */
        div[data-testid="stTextInput"] input,
       div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
            border-radius: {t["radius_sm"]} !important;
            border-color: rgba(124, 58, 237, 0.15) !important;
            font-family: {t["font"]} !important;
        }}
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {{
            border-color: {t["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12) !important;
        }}

        /* —— Select / multiselect labels —— */
        label[data-testid="stWidgetLabel"] {{
            font-weight: 600 !important;
            color: {t["primary_deep"]} !important;
            font-size: 0.88rem !important;
        }}

        /* —— Metrics —— */
        [data-testid="stMetric"] {{
            background: linear-gradient(145deg, {t["surface"]} 0%, {t["surface_soft"]} 100%);
            border: 1px solid rgba(124, 58, 237, 0.08);
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
            border: 1px solid rgba(124, 58, 237, 0.08);
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

        /* —— Sidebar (glass) —— */
        [data-testid="stSidebar"] {{
            background: {t["surface_glass"]} !important;
            backdrop-filter: blur(16px) saturate(1.2);
            -webkit-backdrop-filter: blur(16px) saturate(1.2);
            border-right: 1px solid rgba(255, 255, 255, 0.6);
            box-shadow: 4px 0 32px rgba(76, 29, 149, 0.08);
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1.25rem;
        }}
        [data-testid="stSidebar"] .sidebar-brand {{
            text-align: center;
            padding: 0.75rem 0.5rem 1.25rem;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid rgba(124, 58, 237, 0.08);
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
            box-shadow: 0 8px 20px rgba(124, 58, 237, 0.35);
        }}
        [data-testid="stSidebar"] .sidebar-brand-name {{
            font-size: 1.25rem;
            font-weight: 800;
            color: {t["primary_deep"]};
            margin: 0;
            letter-spacing: -0.02em;
        }}
        [data-testid="stSidebar"] .sidebar-brand-name span {{
            background: linear-gradient(135deg, {t["primary"]}, {t["accent"]});
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        [data-testid="stSidebar"] .sidebar-user {{
            font-size: 0.78rem;
            color: {t["muted"]};
            margin: 0.35rem 0 0;
            font-weight: 500;
        }}
        [data-testid="stSidebar"] .sidebar-nav-label {{
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {t["muted"]};
            margin: 0.5rem 0 0.35rem 0.15rem;
        }}

        /* Nav radio — icon pills */
        [data-testid="stSidebar"] div[data-testid="stRadio"] > div {{
            gap: 0.4rem;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label {{
            background: rgba(255, 255, 255, 0.65);
            border: 1px solid rgba(124, 58, 237, 0.1);
            border-radius: 12px !important;
            padding: 0.65rem 0.9rem !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            color: {t["primary_deep"]} !important;
            transition: all 0.15s ease !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {{
            border-color: rgba(124, 58, 237, 0.25);
            background: rgba(255, 255, 255, 0.9);
        }}
        [data-testid="stSidebar"] div[data-testid="stRadio"] label[data-checked="true"],
        [data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {{
            background: linear-gradient(135deg, {t["primary"]}, {t["primary_dark"]}) !important;
            color: #fff !important;
            border-color: transparent !important;
            box-shadow: 0 6px 16px rgba(124, 58, 237, 0.35);
        }}

        /* —— Main —— */
        .main .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1100px;
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
        }}
        .app-page-hero::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, {t["primary"]}, {t["accent"]}, #a855f7);
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
            background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(99,102,241,0.08));
            color: {t["primary"]};
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(124, 58, 237, 0.12);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {t["surface"]} !important;
            border-radius: {t["radius_lg"]} !important;
            border: 1px solid rgba(124, 58, 237, 0.06) !important;
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
            border: 1px solid rgba(124, 58, 237, 0.08);
            box-shadow: {t["shadow_sm"]};
            border-left: 4px solid {t["primary"]};
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }}
        .job-match-card:hover {{
            box-shadow: {t["shadow_md"]};
            transform: translateY(-2px);
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
            border: 1px solid rgba(124, 58, 237, 0.08);
            box-shadow: {t["shadow_md"]};
        }}
        .profile-avatar {{
            width: 68px;
            height: 68px;
            border-radius: 18px;
            background: linear-gradient(135deg, {t["primary"]}, {t["accent"]});
            color: #fff;
            font-size: 1.4rem;
            font-weight: 800;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            box-shadow: 0 8px 20px rgba(124, 58, 237, 0.3);
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
            background: rgba(124, 58, 237, 0.08);
            color: {t["primary_dark"]};
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .profile-section-hint {{
            color: {t["muted"]};
            font-size: 0.88rem;
            margin: 0 0 0.85rem 0;
        }}

        /* —— Delete zone —— */
        .delete-account-zone {{
            margin-top: 0.5rem;
            padding: 1.35rem 1.6rem;
            border-radius: {t["radius_md"]};
            border: 1.5px dashed rgba(239, 68, 68, 0.35);
            background: linear-gradient(145deg, #fffafa, #fef2f2);
        }}
        .delete-account-zone .delete-account-title {{
            color: #991b1b;
            font-weight: 700;
            font-size: 1.05rem;
            margin: 0 0 0.35rem;
        }}
        .delete-account-zone .delete-account-text {{
            color: #7f1d1d;
            font-size: 0.92rem;
            margin: 0 0 1rem;
        }}
        .delete-account-zone .delete-account-trigger + div[data-testid="stButton"] button {{
            background: linear-gradient(135deg, #ef4444, #dc2626) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 6px 16px rgba(220, 38, 38, 0.28) !important;
        }}

        /* —— File uploader —— */
        [data-testid="stFileUploader"] section {{
            background: {t["surface_soft"]};
            border: 2px dashed rgba(124, 58, 237, 0.2);
            border-radius: {t["radius_lg"]};
            padding: 0.75rem;
            transition: border-color 0.2s ease;
        }}
        [data-testid="stFileUploader"] section:hover {{
            border-color: {t["primary"]};
        }}

        {_shared_components_css(t)}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_styles() -> None:
    """Split-screen login / register styles."""
    t = THEME
    st.markdown(
        f"""
        <style>
        {_font_import()}

        [data-testid="stAppViewContainer"] {{
            background: {t["bg_gradient"]};
            font-family: {t["font"]};
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"], footer {{
            visibility: hidden;
            height: 0;
        }}
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 960px;
        }}
        .auth-lang-hint-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.32rem 0.7rem;
            margin: 0 0 0.35rem 0;
            max-width: 14rem;
            border-radius: 999px;
            background: rgba(124, 58, 237, 0.1);
            border: 1px solid rgba(124, 58, 237, 0.28);
            color: {t["primary_dark"]};
            font-size: 0.76rem;
            font-weight: 700;
            animation: auth-lang-pulse 2.2s ease-in-out infinite;
        }}
        .auth-lang-hint-icon {{
            font-size: 0.95rem;
            line-height: 1;
        }}
        .auth-lang-arrow {{
            display: inline-block;
            animation: auth-lang-nudge 1.3s ease-in-out infinite;
        }}
        @keyframes auth-lang-pulse {{
            0%, 100% {{
                box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.35);
                transform: scale(1);
            }}
            50% {{
                box-shadow: 0 0 0 7px rgba(124, 58, 237, 0);
                transform: scale(1.02);
            }}
        }}
        @keyframes auth-lang-nudge {{
            0%, 100% {{ transform: translateX(0); opacity: 0.85; }}
            50% {{ transform: translateX(4px); opacity: 1; }}
        }}
        .auth-card-row {{
            position: relative;
            padding-bottom: 3.25rem;
        }}
        .auth-card-row [data-testid="column"] {{
            padding: 0 !important;
        }}
        .auth-card-row [data-testid="column"]:first-child > div {{
            background: linear-gradient(160deg, {t["primary"]} 0%, {t["primary_dark"]} 55%, #5b21b6 100%);
            border-radius: {t["radius_xl"]} 0 0 {t["radius_xl"]};
            min-height: 580px;
            box-shadow: {t["shadow_lg"]};
        }}
        .auth-card-row [data-testid="column"]:last-child > div {{
            background: {t["surface"]};
            border-radius: 0 {t["radius_xl"]} {t["radius_xl"]} 0;
            min-height: 580px;
            box-shadow: {t["shadow_lg"]};
            padding: 2.25rem 2.5rem 1.75rem !important;
            display: flex;
            flex-direction: column;
        }}
        .auth-panel-right-inner {{
            display: flex;
            flex-direction: column;
            flex: 1;
            min-height: 100%;
        }}
        .auth-login-actions {{
            margin-top: 0.35rem;
        }}
        .auth-login-actions [data-testid="column"] {{
            display: flex;
            align-items: stretch;
        }}
        .auth-login-forgot {{
            display: flex;
            align-items: center;
            height: 100%;
            justify-content: flex-end;
        }}
        .auth-login-forgot button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {t["accent"]} !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            white-space: nowrap;
            padding: 0.65rem 0.25rem !important;
        }}
        .auth-login-forgot button:hover {{
            color: {t["primary"]} !important;
            text-decoration: underline;
        }}
        .auth-create-between {{
            margin-top: -2.75rem;
            position: relative;
            z-index: 6;
            pointer-events: none;
        }}
        .auth-create-between [data-testid="column"] {{
            pointer-events: auto;
        }}
        .auth-create-between button {{
            background: {t["surface"]} !important;
            border: 2px solid rgba(124, 58, 237, 0.28) !important;
            color: {t["primary_deep"]} !important;
            font-weight: 700 !important;
            font-size: 0.92rem !important;
            border-radius: 999px !important;
            padding: 0.65rem 1.25rem !important;
            box-shadow: 0 10px 28px rgba(76, 29, 149, 0.18) !important;
        }}
        .auth-create-between button:hover {{
            border-color: {t["primary"]} !important;
            color: {t["primary"]} !important;
            transform: translateY(-1px);
        }}
        .auth-left-panel {{
            color: #fff;
            text-align: center;
            padding: 2.5rem 2rem;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .auth-illustration {{
            width: min(100%, 260px);
            margin-bottom: 1.5rem;
            filter: drop-shadow(0 12px 24px rgba(0,0,0,0.15));
        }}
        .auth-left-title {{
            font-size: 1.1rem;
            line-height: 1.55;
            font-weight: 600;
            margin: 0 0 0.65rem;
            color: rgba(255,255,255,0.98);
        }}
        .auth-left-tip {{
            font-size: 0.84rem;
            line-height: 1.5;
            color: rgba(255,255,255,0.75);
        }}
        .auth-greeting-main {{
            font-size: 2rem;
            font-weight: 800;
            color: {t["primary_deep"]};
            margin: 0 0 0.1rem;
            letter-spacing: -0.03em;
        }}
        .auth-greeting-sub {{
            font-size: 1.45rem;
            font-weight: 700;
            color: {t["primary_deep"]};
            margin: 0 0 1.25rem;
        }}
        .auth-form-title {{
            font-size: 0.92rem;
            color: {t["muted"]};
            margin: 0 0 1.25rem;
        }}
        .auth-card-row div[data-testid="stTextInput"] input {{
            background: {t["surface_soft"]} !important;
            border: 1.5px solid rgba(124, 58, 237, 0.12) !important;
            border-radius: 12px !important;
            padding: 0.65rem 0.85rem !important;
            color: {t["primary_deep"]} !important;
        }}
        .auth-card-row div[data-testid="stTextInput"] input:focus {{
            border-color: {t["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12) !important;
        }}
        .auth-card-row div[data-testid="stFormSubmitButton"] button {{
            width: 100%;
            padding: 0.78rem 1.5rem !important;
            margin-top: 0.35rem;
        }}
        .auth-link-row button,
        .auth-footer-link button,
        .auth-back-link button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        .auth-link-row button {{
            color: {t["accent"]} !important;
            font-size: 0.82rem !important;
        }}
        .auth-footer-link button {{
            color: {t["muted"]} !important;
        }}
        .auth-footer-link button:hover {{
            color: {t["primary"]} !important;
        }}
        .auth-back-link button {{
            color: {t["primary"]} !important;
            font-weight: 600 !important;
            font-size: 0.84rem !important;
            padding-left: 0 !important;
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
            background: #c4b5fd;
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
            margin-top: 1.25rem;
        }}
        .reg-wizard-nav button {{
            min-height: 2.65rem;
        }}
        .reg-wizard-nav [data-testid="column"]:first-child button {{
            background: {t["surface_soft"]} !important;
            border: 1.5px solid rgba(124, 58, 237, 0.22) !important;
            color: {t["primary_deep"]} !important;
            font-weight: 600 !important;
        }}
        .reg-wizard-nav [data-testid="column"]:first-child button:hover {{
            border-color: {t["primary"]} !important;
            color: {t["primary"]} !important;
        }}
        {_shared_components_css(t)}
        @media (max-width: 768px) {{
            .auth-card-row [data-testid="column"]:first-child > div {{
                border-radius: {t["radius_xl"]} {t["radius_xl"]} 0 0;
                min-height: 260px;
            }}
            .auth-card-row [data-testid="column"]:last-child > div {{
                border-radius: 0 0 {t["radius_xl"]} {t["radius_xl"]};
                min-height: auto;
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
