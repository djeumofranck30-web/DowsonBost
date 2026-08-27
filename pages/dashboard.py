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
    start_admin_support_conversation,
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
        .support-space-header {
            background: #fff;
            border: 1px solid rgba(14, 116, 144, 0.12);
            border-radius: 16px;
            padding: 0.85rem 1rem 0.95rem;
            margin-bottom: 0.7rem;
        }
        .support-space-header strong {
            display: block;
            font-size: 1.05rem;
            color: #0B1220;
        }
        .support-space-header small {
            display: block;
            color: #5B6573;
            margin: 0.15rem 0 0.35rem;
        }
        .support-space-header span {
            display: block;
            font-size: 0.78rem;
            color: #0E7490;
            font-weight: 600;
        }
        [data-testid="stRadio"] p { white-space: pre-line; line-height: 1.25; }
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


def _space_key(item: dict) -> str:
    if item.get("id") is not None:
        return f"c:{int(item['id'])}"
    return f"u:{int(item['user_id'])}"


def _parse_space_key(key: str) -> tuple[int | None, int | None]:
    raw = str(key or "")
    if raw.startswith("c:"):
        try:
            return int(raw[2:]), None
        except ValueError:
            return None, None
    if raw.startswith("u:"):
        try:
            return None, int(raw[2:])
        except ValueError:
            return None, None
    return None, None


def _space_label(item: dict) -> str:
    unread = int(item.get("unread") or 0)
    name = item.get("full_name") or "Sans nom"
    email = item.get("email") or ""
    preview = str(item.get("last_body") or "").strip().replace("\n", " ")
    if not preview:
        preview = "Nouvelle conversation" if item.get("id") is not None else "vide"
    elif len(preview) > 60:
        preview = preview[:57] + "…"
    badge = f"  · {unread} non lu(s)" if unread else ""
    return f"{name}{badge}\n{email}\n{preview}"


def _render_admin_support(admin: dict) -> None:
    unread = admin_support_unread()
    st.markdown(
        f"### Espaces chat{' · ' + str(unread) + ' message(s) non lu(s)' if unread else ''}"
    )
    st.caption(
        "Chaque conversation est privée. « Nouvelle conversation » ouvre un fil vierge "
        "avec le candidat sélectionné — seul ce candidat le verra."
    )
    if st.session_state.pop("admin_reply_sent", False):
        st.success("Réponse envoyée — seul ce candidat la verra.")

    spaces = admin_support_conversations()
    if not spaces:
        st.info("Aucun candidat inscrit pour le moment.")
        return

    by_key = {_space_key(item): item for item in spaces}
    pending_key = st.session_state.get("admin_support_open_space")
    if pending_key and pending_key in by_key:
        st.session_state.admin_support_space = pending_key
        st.session_state.pop("admin_support_open_space", None)
    if st.session_state.get("admin_support_space") not in by_key:
        preferred = next((item for item in spaces if int(item.get("unread") or 0)), spaces[0])
        st.session_state.admin_support_space = _space_key(preferred)

    list_col, chat_col = st.columns([0.4, 0.6], gap="large")
    with list_col:
        st.markdown("#### Conversations")
        if st.button("+ Nouvelle conversation", use_container_width=True, key="admin_support_new"):
            current = by_key.get(str(st.session_state.get("admin_support_space") or ""))
            target_uid = int(current["user_id"]) if current else None
            if not target_uid:
                st.warning("Sélectionnez d’abord un candidat.")
            else:
                created = start_admin_support_conversation(target_uid)
                if created:
                    st.session_state.admin_support_space = f"c:{int(created['id'])}"
                    st.session_state.admin_stay_on_support = True
                    st.rerun()
        query = (st.text_input(
            "Rechercher un candidat",
            placeholder="Nom ou e-mail…",
            key="admin_support_search",
            label_visibility="collapsed",
        ) or "").strip().lower()
        filtered = []
        for item in spaces:
            haystack = f"{item.get('full_name') or ''} {item.get('email') or ''}".lower()
            if not query or query in haystack:
                filtered.append(item)
        selected_now = st.session_state.get("admin_support_space")
        if selected_now in by_key and all(_space_key(item) != selected_now for item in filtered):
            filtered = [by_key[selected_now]] + filtered
        if not filtered:
            st.info("Aucun candidat ne correspond à la recherche.")
            option_keys = [str(st.session_state.admin_support_space)]
        else:
            option_keys = [_space_key(item) for item in filtered]
        selected_key = st.radio(
            "Espace du candidat",
            options=option_keys,
            format_func=lambda key: _space_label(by_key.get(str(key)) or {}),
            key="admin_support_space",
        )

    selected_key = str(selected_key)
    conversation_id, placeholder_uid = _parse_space_key(selected_key)
    target = by_key.get(selected_key) or {}
    selected_uid = int(target.get("user_id") or placeholder_uid or 0)
    if st.session_state.get("admin_support_last_space") != selected_key:
        st.session_state.admin_support_last_space = selected_key
        st.session_state.admin_support_reply_body = ""

    if selected_uid:
        mark_admin_support_read(selected_uid, conversation_id=conversation_id)
    thread = (
        admin_support_thread(selected_uid, conversation_id=conversation_id)
        if selected_uid
        else []
    )
    name = target.get("full_name") or "Candidat"
    email = target.get("email") or ""
    empty_label = (
        "Conversation vierge. Écrivez le premier message — seul ce candidat le verra."
        if conversation_id
        else "Aucun message dans cet espace. Vous pouvez écrire en premier."
    )

    with chat_col:
        st.markdown(
            f'<div class="support-space-header">'
            f"<strong>Espace de {html.escape(name)}</strong>"
            f"<small>{html.escape(email)}</small>"
            f"<span>Fil privé — seul ce candidat voit vos messages.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            render_support_thread_html(
                thread,
                user_label=name,
                admin_label="Vous (admin)",
                empty_text=empty_label,
            ),
            unsafe_allow_html=True,
        )
        body = st.text_area(
            "Réponse",
            height=110,
            max_chars=4000,
            placeholder=f"Votre message à {name} uniquement…",
            key="admin_support_reply_body",
        )
        if st.button("Envoyer dans cet espace", type="primary", use_container_width=True, key="admin_support_send"):
            if not selected_uid:
                st.error("Candidat introuvable.")
            else:
                ok, message, _saved = send_admin_support_reply(
                    selected_uid,
                    body,
                    admin_id=int(admin.get("id") or 0) or None,
                    admin_email=str(admin.get("email") or ""),
                    conversation_id=conversation_id,
                )
                if ok:
                    st.session_state.admin_stay_on_support = True
                    saved_key = selected_key
                    if _saved and _saved.get("conversation_id") is not None:
                        saved_key = f"c:{int(_saved['conversation_id'])}"
                    st.session_state.admin_support_open_space = saved_key
                    st.session_state.admin_clear_reply = True
                    st.session_state.admin_reply_sent = True
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
    if st.session_state.pop("admin_stay_on_support", False):
        st.session_state.admin_main_section = "support"
    if st.session_state.pop("admin_clear_reply", False):
        st.session_state.admin_support_reply_body = ""
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
