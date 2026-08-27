"""Espace administrateur Streamlit — https://dowsonbost.streamlit.app/dashboard."""

from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from auth import authenticate_admin, init_db, user_is_admin
from config import get_secret
from database import DatabaseConfigError, configure_database
from services.admin import admin_delete_user, dashboard_html, list_registered_users, platform_overview, public_user_record
from services.support import (
    admin_support_conversations,
    admin_support_thread,
    admin_support_unread,
    mark_admin_support_read,
    render_support_thread_html,
    send_admin_support_reply,
)
from ui.theme import THEME, _shared_components_css

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
        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(ellipse 80% 50% at 8% 0%, rgba(14,116,144,.16), transparent 55%),
                radial-gradient(ellipse 50% 40% at 100% 0%, rgba(232,185,35,.16), transparent 50%),
                linear-gradient(160deg, #F4F1EA 0%, #E7F1EE 55%, #DCE8F2 100%) !important;
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stSidebarNav"], footer { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 1.1rem !important; max-width: 1280px !important; }
        iframe { border: 0 !important; }
        """
        + _shared_components_css(THEME)
        + """
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
    admin = st.session_state.get("admin_user")
    if admin and user_is_admin(admin):
        return admin
    return None


def _render_login() -> None:
    st.markdown(
        """
        <div style="max-width:420px;margin:8vh auto 0;background:#fff;border-radius:24px;
                    padding:1.6rem 1.4rem;box-shadow:0 18px 40px rgba(11,18,32,.10);
                    border:1px solid rgba(14,116,144,.14)">
          <p style="margin:0;font-size:.8rem;font-weight:700;color:#0E7490;letter-spacing:.04em">DOWSONBOST</p>
          <h1 style="margin:.2rem 0 .4rem;font-size:1.6rem">Espace administrateur</h1>
          <p style="margin:0 0 1rem;color:#64748b">Accès réservé. Utilisez l’e-mail et le mot de passe ajoutés dans les secrets Streamlit (<code>ADMIN_EMAIL</code> + <code>ADMIN_PASSWORD</code>).</p>
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
    ok, message, user = authenticate_admin(email, password)
    if not ok or not user:
        st.error(message)
        return
    st.session_state.admin_user = user
    st.rerun()


def _user_label(user: dict) -> str:
    tokens = int(user.get("tokens_consumed") or 0)
    return f"{user.get('full_name') or 'Sans nom'} — {user.get('email')} ({tokens} tokens)"


def _conversation_label(item: dict) -> str:
    unread = int(item.get("unread") or 0)
    base = f"{item.get('full_name') or 'Sans nom'} — {item.get('email')}"
    if unread:
        return f"{base}  · {unread} non lu(s)"
    return base


def _render_admin_support(admin: dict) -> None:
    unread = admin_support_unread()
    st.markdown(
        f"### Support candidats{' · ' + str(unread) + ' message(s) non lu(s)' if unread else ''}"
    )
    st.caption(
        "Chaque conversation est privée : vous voyez quel candidat a écrit, "
        "et votre réponse n’est visible que par ce candidat."
    )
    conversations = admin_support_conversations()
    accounts = [public_user_record(item) for item in list_registered_users()]
    account_by_id = {int(item["id"]): item for item in accounts}
    conv_by_id = {int(item["user_id"]): item for item in conversations}

    option_ids = [int(item["user_id"]) for item in conversations]
    pending_id = st.session_state.get("admin_support_open_user")
    if pending_id and int(pending_id) not in option_ids and int(pending_id) in account_by_id:
        option_ids = [int(pending_id)] + option_ids

    def _label_for(uid: int) -> str:
        if uid in conv_by_id:
            return _conversation_label(conv_by_id[uid])
        person = account_by_id.get(uid) or {}
        return f"{person.get('full_name') or 'Sans nom'} — {person.get('email')}"

    selected_id = None
    if option_ids:
        selected_id = st.selectbox(
            "Conversations",
            options=option_ids,
            format_func=_label_for,
            key="admin_support_conversation",
        )
    else:
        st.info("Aucun message pour le moment. Vous pouvez écrire à un candidat ci-dessous.")

    other_ids = [
        int(item["id"])
        for item in accounts
        if selected_id is None or int(item["id"]) != int(selected_id)
    ]
    if other_ids:
        with st.expander("Écrire à un autre candidat", expanded=not option_ids):
            pick_id = st.selectbox(
                "Candidat",
                options=other_ids,
                format_func=_label_for,
                key="admin_support_pick_user",
            )
            if st.button("Ouvrir cette conversation", use_container_width=True):
                st.session_state.admin_support_open_user = int(pick_id)
                st.session_state.admin_support_conversation = int(pick_id)
                st.rerun()

    if not selected_id:
        return

    target = account_by_id.get(int(selected_id))
    mark_admin_support_read(int(selected_id))
    thread = admin_support_thread(int(selected_id))
    name = (target or {}).get("full_name") or "Candidat"
    email = (target or {}).get("email") or ""
    st.markdown(f"**{name}**  \n{email}")
    st.markdown(
        render_support_thread_html(
            thread,
            user_label=name,
            admin_label="Vous (admin)",
            empty_text="Aucun message dans cette conversation.",
        ),
        unsafe_allow_html=True,
    )
    with st.form("admin_support_reply", clear_on_submit=True):
        body = st.text_area(
            "Réponse",
            height=110,
            max_chars=4000,
            placeholder="Votre réponse à ce candidat…",
        )
        sent = st.form_submit_button("Envoyer la réponse", type="primary", use_container_width=True)
    if sent:
        ok, message, _saved = send_admin_support_reply(
            int(selected_id),
            body,
            admin_id=int(admin.get("id") or 0) or None,
            admin_email=str(admin.get("email") or ""),
        )
        if ok:
            st.success("Réponse envoyée — seul ce candidat la verra.")
            st.rerun()
        st.error(message)


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
    actor_id = int(user.get("id") or 0)
    deletable = [item for item in accounts if int(item["id"]) != actor_id]

    support_unread = admin_support_unread()
    admin_section = st.radio(
        "Espace admin",
        ("overview", "support"),
        format_func=lambda key: (
            f"Support · {support_unread} non lu(s)"
            if key == "support" and support_unread
            else "Support"
            if key == "support"
            else "Vue d’ensemble"
        ),
        horizontal=True,
        key="admin_main_section",
        label_visibility="collapsed",
    )
    if admin_section == "support":
        _render_admin_support(user)
        logout_col, back_col = st.columns([1, 2])
        with logout_col:
            if st.button("Déconnexion admin", use_container_width=True, key="admin_logout_support"):
                st.session_state.pop("admin_user", None)
                st.rerun()
        with back_col:
            st.page_link("app.py", label="Retour à l'application candidate", icon="🎯")
        return

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
                ok, message = admin_delete_user(user, int(target["id"]))
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

    st.markdown("---")
    from app import render_config_tests_panel

    render_config_tests_panel(show_clear_cache=True, expanded=False)

    logout_col, back_col = st.columns([1, 2])
    with logout_col:
        if st.button("Déconnexion admin", use_container_width=True):
            st.session_state.pop("admin_user", None)
            st.rerun()
    with back_col:
        st.page_link("app.py", label="Retour à l'application candidate", icon="🎯")


main()
