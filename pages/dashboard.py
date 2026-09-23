"""Espace administrateur Streamlit — https://dowsonbost.streamlit.app/dashboard."""

from __future__ import annotations

import html
import time

import streamlit as st
import streamlit.components.v1 as components

from auth import authenticate_admin, init_db, user_is_admin
from config import get_secret
from database import DatabaseConfigError, configure_database
from services.admin import admin_delete_user, dashboard_html, platform_overview
from services.admin_events import (
    KIND_LABELS,
    list_admin_alerts,
    list_admin_events,
    mark_admin_events_read,
    unread_admin_alert_count,
)
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
                radial-gradient(ellipse 80% 50% at 8% 0%, rgba(74,111,140,.06), transparent 55%),
                radial-gradient(ellipse 50% 40% at 100% 0%, rgba(49,70,90,.05), transparent 50%),
                linear-gradient(180deg, #FFFFFF 0%, #F3F4F6 100%) !important;
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stSidebarNav"], footer { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 1.1rem !important; max-width: 1280px !important; }
        iframe { border: 0 !important; }
        .support-space-header {
            background: #fff;
            border: 1px solid rgba(74, 111, 140, 0.12);
            border-radius: 16px;
            padding: 0.85rem 1rem 0.95rem;
            margin-bottom: 0.7rem;
        }
        .support-space-header strong {
            display: block;
            font-size: 1.05rem;
            color: #31465A;
        }
        .support-space-header small {
            display: block;
            color: #5B6573;
            margin: 0.15rem 0 0.35rem;
        }
        .support-space-header span {
            display: block;
            font-size: 0.78rem;
            color: #4A6F8C;
            font-weight: 600;
        }
        [data-testid="stRadio"] p { white-space: pre-line; line-height: 1.25; }
        .admin-banner {
            background: #FEF2F2; border: 1px solid #FECACA; border-radius: 14px;
            padding: 0.85rem 1rem; margin: 0 0 0.85rem; color: #9F1239;
        }
        .admin-banner strong { display: block; font-size: 1rem; }
        .admin-banner span { display: block; font-size: 0.82rem; margin-top: 0.15rem; }
        .admin-event {
            background: #fff; border: 1px solid rgba(37,99,235,.12); border-radius: 14px;
            padding: 0.8rem 0.95rem; margin-bottom: 0.55rem;
            border-left: 4px solid #2563EB;
        }
        .admin-event.error { border-left-color: #EF4444; background: #FFF7F7; }
        .admin-event.warning { border-left-color: #F59E0B; background: #FFFBEB; }
        .admin-event .meta { color: #64748b; font-size: 0.78rem; margin-top: 0.2rem; }
        .admin-day {
            font-size: 0.78rem; font-weight: 700; color: #1E3A8A; letter-spacing: .04em;
            text-transform: uppercase; margin: 1rem 0 0.45rem;
        }
        .admin-row {
            display: grid; grid-template-columns: 88px 110px 1.1fr 1.4fr;
            gap: 0.6rem; padding: 0.65rem 0.75rem; border-bottom: 1px solid #EEF2F7;
            font-size: 0.88rem; align-items: start;
        }
        .admin-row header, .admin-row-head {
            color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em;
            font-weight: 700;
        }
        .admin-pill { display: inline-flex; border-radius: 999px; padding: .12rem .5rem; font-size: .7rem; font-weight: 700; }
        .admin-pill.error { background: #FEE2E2; color: #B91C1C; }
        .admin-pill.warning { background: #FEF3C7; color: #B45309; }
        .admin-pill.info { background: #EFF6FF; color: #1D4ED8; }
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
                    border:1px solid rgba(74,111,140,.14)">
          <p style="margin:0;font-size:.8rem;font-weight:700;color:#4A6F8C;letter-spacing:.04em">DOWSONBOST</p>
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


def _render_admin_support(admin: dict, unread: int | None = None) -> None:
    unread = admin_support_unread() if unread is None else int(unread)
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


def _format_event_when(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return text[:16].replace("T", " ")


def _event_who(item: dict) -> str:
    name = str(item.get("user_name") or "").strip()
    email = str(item.get("user_email") or "").strip()
    if name and email:
        return f"{name} · {email}"
    return name or email or "Compte inconnu"


_OVERVIEW_TTL_SEC = 20.0
_BADGE_TTL_SEC = 8.0


def _invalidate_admin_caches() -> None:
    st.session_state.pop("_admin_overview_pack", None)
    st.session_state.pop("_admin_badges", None)


def _badge_counts() -> tuple[int, int]:
    now = time.monotonic()
    cached = st.session_state.get("_admin_badges")
    if cached and now - float(cached.get("ts") or 0) < _BADGE_TTL_SEC:
        return int(cached.get("alerts") or 0), int(cached.get("support") or 0)
    alerts = unread_admin_alert_count()
    support = admin_support_unread()
    st.session_state._admin_badges = {"ts": now, "alerts": alerts, "support": support}
    return alerts, support


def _cached_overview(user: dict) -> dict:
    now = time.monotonic()
    pack = st.session_state.get("_admin_overview_pack")
    if pack and now - float(pack.get("ts") or 0) < _OVERVIEW_TTL_SEC and pack.get("data"):
        overview = dict(pack["data"])
    else:
        overview = platform_overview(include_support=False)
        st.session_state._admin_overview_pack = {"ts": now, "data": overview}
        overview = dict(overview)
    overview["viewer"] = {
        "id": int(user.get("id") or 0),
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or "",
    }
    return overview


def _render_admin_alerts(unread: int | None = None) -> None:
    unread = unread_admin_alert_count() if unread is None else int(unread)
    st.markdown("### Alertes incidents")
    st.caption(
        "Échecs d’analyse, blocages, limites IA / SerpAPI et candidatures en échec. "
        "Marquez une alerte comme lue une fois le problème pris en compte."
    )
    if unread:
        st.markdown(
            f'<div class="admin-banner"><strong>{unread} incident(s) non lu(s)</strong>'
            f"<span>Un candidat a rencontré un problème — traitez-les ici.</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Tout marquer comme lu", type="primary", key="admin_alerts_read_all"):
            mark_admin_events_read(all_unread=True)
            _invalidate_admin_caches()
            st.session_state.admin_stay_on_alerts = True
            st.rerun()
    alerts = list_admin_alerts(limit=80)
    if not alerts:
        st.info("Aucun incident pour le moment. Les erreurs d’analyse et quotas IA apparaîtront ici.")
        return
    cards: list[str] = []
    unread_items: list[dict] = []
    for item in alerts:
        severity = str(item.get("severity") or "info")
        unread_flag = bool(item.get("unread"))
        if unread_flag:
            unread_items.append(item)
        cards.append(
            f'<div class="admin-event {html.escape(severity)}">'
            f"<strong>{html.escape(item.get('title') or item.get('kind_label') or 'Incident')}</strong>"
            f'<div class="meta">{html.escape(_format_event_when(item.get("created_at") or ""))}'
            f" · {html.escape(_event_who(item))}"
            f" · {html.escape(item.get('kind_label') or item.get('kind') or '')}"
            f"{' · non lu' if unread_flag else ''}</div>"
            f"<p style='margin:.4rem 0 0'>{html.escape(item.get('message') or '')}</p>"
            f"</div>"
        )
    st.markdown("".join(cards), unsafe_allow_html=True)
    for item in unread_items[:12]:
        if st.button(
            f"Marquer comme lu · {item.get('title') or 'Incident'}",
            key=f"admin_alert_read_{item['id']}",
        ):
            mark_admin_events_read([int(item["id"])])
            _invalidate_admin_caches()
            st.session_state.admin_stay_on_alerts = True
            st.rerun()


def _render_admin_activity() -> None:
    st.markdown("### Journal d’activité")
    st.caption(
        "Tout ce que font les candidats : inscriptions, connexions, analyses, "
        "candidatures, messages support et incidents."
    )
    kind_options = [("all", "Tous les types")] + sorted(
        ((kind, label) for kind, label in KIND_LABELS.items()),
        key=lambda item: item[1],
    )
    with st.form("admin_activity_filters", border=False):
        filter_col, search_col, apply_col = st.columns([1, 1.4, 0.7])
        with filter_col:
            selected_kind = st.selectbox(
                "Filtrer par type",
                options=[item[0] for item in kind_options],
                format_func=lambda key: next(label for item, label in kind_options if item == key),
                key="admin_activity_kind",
            )
        with search_col:
            query = st.text_input(
                "Rechercher",
                placeholder="Nom, e-mail, message…",
                key="admin_activity_query",
            )
        with apply_col:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            st.form_submit_button("Filtrer", use_container_width=True)
    kinds = None if selected_kind == "all" else [selected_kind]
    events = list_admin_events(limit=120, kinds=kinds, query=query or "")
    if selected_kind == "all" and not (query or "").strip() and events:
        counts: dict[str, int] = {}
        for item in events:
            kind = str(item.get("kind") or "")
            counts[kind] = counts.get(kind, 0) + 1
        chips = " · ".join(
            f"{KIND_LABELS.get(kind, kind)} ({count})"
            for kind, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        )
        if chips:
            st.caption(chips)
    if not events:
        st.info("Aucune activité enregistrée pour ce filtre.")
        return
    rows = [
        '<div class="admin-row admin-row-head"><span>Heure</span><span>Type</span>'
        "<span>Candidat</span><span>Détail</span></div>"
    ]
    current_day = ""
    for item in events:
        day = str(item.get("created_at") or "")[:10]
        if day and day != current_day:
            current_day = day
            rows.append(f'<div class="admin-day">{html.escape(day)}</div>')
        severity = str(item.get("severity") or "info")
        when = _format_event_when(item.get("created_at") or "")
        time_part = when.split(" ")[-1] if " " in when else when
        rows.append(
            f'<div class="admin-row">'
            f"<span>{html.escape(time_part)}</span>"
            f'<span><span class="admin-pill {html.escape(severity)}">'
            f"{html.escape(item.get('kind_label') or item.get('kind') or '')}</span></span>"
            f"<span>{html.escape(_event_who(item))}</span>"
            f"<span><strong>{html.escape(item.get('title') or '')}</strong><br>"
            f"{html.escape(item.get('message') or '')}</span>"
            f"</div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_admin_footer(*, logout_key: str) -> None:
    logout_col, back_col = st.columns([1, 2])
    with logout_col:
        if st.button("Déconnexion admin", use_container_width=True, key=logout_key):
            st.session_state.pop("admin_user", None)
            st.rerun()
    with back_col:
        st.page_link("app.py", label="Retour à l'application candidate", icon="🎯")


def _section_label(key: str, *, alerts: int, support: int) -> str:
    if key == "alerts":
        return f"Alertes · {alerts} non lu(s)" if alerts else "Alertes"
    if key == "activity":
        return "Activité"
    if key == "support":
        return f"Support · {support} non lu(s)" if support else "Support"
    return "Vue d’ensemble"


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

    if st.session_state.pop("admin_stay_on_support", False):
        st.session_state.admin_main_section = "support"
    if st.session_state.pop("admin_stay_on_alerts", False):
        st.session_state.admin_main_section = "alerts"
    if st.session_state.pop("admin_stay_on_activity", False):
        st.session_state.admin_main_section = "activity"
    if st.session_state.pop("admin_clear_reply", False):
        st.session_state.admin_support_reply_body = ""

    alert_unread, support_unread = _badge_counts()
    if alert_unread and st.session_state.get("admin_main_section") not in {"alerts"}:
        st.markdown(
            f'<div class="admin-banner"><strong>{alert_unread} incident(s) à traiter</strong>'
            "<span>Un candidat a rencontré un problème (analyse, blocage ou limite IA).</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Ouvrir les alertes", key="admin_open_alerts"):
            st.session_state.admin_main_section = "alerts"
            st.rerun()

    admin_section = st.radio(
        "Espace admin",
        ("overview", "alerts", "activity", "support"),
        format_func=lambda key: _section_label(key, alerts=alert_unread, support=support_unread),
        horizontal=True,
        key="admin_main_section",
        label_visibility="collapsed",
    )
    if admin_section == "support":
        _render_admin_support(user, unread=support_unread)
        _render_admin_footer(logout_key="admin_logout_support")
        return
    if admin_section == "alerts":
        _render_admin_alerts(unread=alert_unread)
        _render_admin_footer(logout_key="admin_logout_alerts")
        return
    if admin_section == "activity":
        _render_admin_activity()
        _render_admin_footer(logout_key="admin_logout_activity")
        return

    overview = _cached_overview(user)
    accounts = list(overview.get("users") or [])
    actor_id = int(user.get("id") or 0)
    deletable = [item for item in accounts if int(item["id"]) != actor_id]

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
                _invalidate_admin_caches()
                if ok:
                    st.success(message)
                else:
                    st.error(message)
                st.rerun()
            if cancel_col.button("Annuler"):
                st.session_state.pop("admin_delete_target", None)
                st.rerun()

    action_left, action_right, refresh_col = st.columns([2.4, 0.9, 0.9])
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
    with refresh_col:
        st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if st.button("Actualiser", use_container_width=True, key="admin_refresh_overview"):
            _invalidate_admin_caches()
            st.rerun()

    components.html(dashboard_html(overview, embedded=True), height=1760, scrolling=True)

    st.markdown("---")
    if st.checkbox("Afficher les tests de configuration", key="admin_show_config_tests"):
        from app import render_config_tests_panel

        render_config_tests_panel(show_clear_cache=True, expanded=True)
    _render_admin_footer(logout_key="admin_logout_overview")


main()

