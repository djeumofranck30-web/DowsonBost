"""Espace administrateur Streamlit — https://dowsonbost.streamlit.app/dashboard."""

from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from auth import authenticate_user, init_db, user_is_admin
from config import get_secret
from database import DatabaseConfigError, configure_database
from services.admin import admin_delete_user, dashboard_html, list_registered_users, platform_overview, public_user_record

st.set_page_config(
    page_title="Admin · DowsonBost",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _inject_admin_chrome() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(ellipse 80% 50% at 8% 0%, rgba(124,58,237,.16), transparent 55%),
                linear-gradient(160deg, #f5f3ff 0%, #eef2ff 55%, #f8fafc 100%) !important;
            font-family: "Plus Jakarta Sans", system-ui, sans-serif;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stSidebarNav"], footer { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 1.1rem !important; max-width: 1280px !important; }
        iframe { border: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _boot_database() -> bool:
    try:
        configure_database(
            get_secret("DATABASE_URL"),
            password=get_secret("DATABASE_PASSWORD"),
        )
        init_db()
        return True
    except DatabaseConfigError as exc:
        st.error("Configuration base de données incorrecte.")
        st.code(str(exc))
        return False
    except Exception as exc:  # noqa: BLE001
        st.error("Impossible de se connecter à la base de données.")
        st.code(str(exc))
        return False


def _current_user() -> dict | None:
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return st.session_state.user
    if st.session_state.get("admin_user"):
        return st.session_state.admin_user
    return None


def _render_login() -> None:
    st.markdown(
        """
        <div style="max-width:420px;margin:8vh auto 0;background:#fff;border-radius:24px;
                    padding:1.6rem 1.4rem;box-shadow:0 18px 40px rgba(76,29,149,.12);
                    border:1px solid rgba(124,58,237,.14)">
          <p style="margin:0;font-size:.8rem;font-weight:700;color:#7c3aed;letter-spacing:.04em">DOWSONBOST</p>
          <h1 style="margin:.2rem 0 .4rem;font-size:1.6rem">Espace administrateur</h1>
          <p style="margin:0 0 1rem;color:#64748b">Accès réservé. Ajoutez votre e-mail dans le secret <code>ADMIN_EMAILS</code>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("admin_login"):
        email = st.text_input("E-mail")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
    if not submitted:
        return
    ok, message, user = authenticate_user(email, password)
    if not ok or not user:
        st.error(message)
        return
    if not user_is_admin(user):
        st.error("Ce compte n'est pas administrateur. Définissez ADMIN_EMAILS dans les secrets Streamlit.")
        return
    st.session_state.authenticated = True
    st.session_state.user = user
    st.session_state.admin_user = user
    st.rerun()


def _user_label(user: dict) -> str:
    tokens = int(user.get("tokens_consumed") or 0)
    return f"{user.get('full_name') or 'Sans nom'} — {user.get('email')} ({tokens} tokens)"


def main() -> None:
    _inject_admin_chrome()
    if not _boot_database():
        return

    user = _current_user()
    if not user:
        _render_login()
        return
    if not user_is_admin(user):
        st.error("Accès réservé aux administrateurs.")
        st.page_link("app.py", label="Retour à l'application", icon="🎯")
        return

    overview = platform_overview()
    overview["viewer"] = {
        "id": int(user["id"]),
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or "",
    }
    accounts = [public_user_record(item) for item in list_registered_users()]
    deletable = [item for item in accounts if int(item["id"]) != int(user["id"])]

    pending = st.session_state.get("admin_delete_target")
    if pending:
        target = next((item for item in accounts if int(item["id"]) == int(pending)), None)
        if not target:
            st.session_state.pop("admin_delete_target", None)
        else:
            st.warning(
                f"Supprimer définitivement **{html.escape(target['full_name'])}** "
                f"({html.escape(target['email'])}) et toutes ses données ?"
            )
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button("Confirmer la suppression", type="primary"):
                ok, message = admin_delete_user(int(user["id"]), int(target["id"]))
                st.session_state.pop("admin_delete_target", None)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
                st.rerun()
            if cancel_col.button("Annuler"):
                st.session_state.pop("admin_delete_target", None)
                st.rerun()

    action_left, action_right = st.columns([3, 1])
    with action_left:
        options = {item["id"]: _user_label(item) for item in deletable}
        selected_id = st.selectbox(
            "Supprimer un compte inscrit",
            options=list(options.keys()) or [0],
            format_func=lambda uid: options.get(uid, "Aucun compte à supprimer"),
            disabled=not options,
        )
    with action_right:
        st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if st.button("Supprimer", type="primary", disabled=not options, use_container_width=True):
            st.session_state.admin_delete_target = int(selected_id)
            st.rerun()

    components.html(dashboard_html(overview, embedded=True), height=1080, scrolling=True)
    st.page_link("app.py", label="Retour à l'application candidate", icon="🎯")


main()
