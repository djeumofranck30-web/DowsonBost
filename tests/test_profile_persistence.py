"""Saved profile values must survive reruns until the user changes them."""

from __future__ import annotations

from auth import get_user_by_id, register_user, update_user_profile
from profile_session import (
    clear_profile_widget_keys,
    retain_multiselect_session,
    seed_session_value,
)


def test_first_profile_load_keeps_saved_departments() -> None:
    """A missing region signature must not wipe seeded departments."""
    state: dict = {}
    values = retain_multiselect_session(
        state,
        values_key="depts",
        signature_key="last_regions",
        current_signature=("Île-de-France",),
        seed_values=["75 — Paris"],
        allowed=["75 — Paris", "92 — Hauts-de-Seine"],
    )
    assert values == ["75 — Paris"]
    assert state["depts"] == ["75 — Paris"]
    again = retain_multiselect_session(
        state,
        values_key="depts",
        signature_key="last_regions",
        current_signature=("Île-de-France",),
        seed_values=["75 — Paris"],
        allowed=["75 — Paris", "92 — Hauts-de-Seine"],
    )
    assert again == ["75 — Paris"]


def test_parent_filter_change_drops_invalid_children_only() -> None:
    state = {
        "depts": ["75 — Paris", "69 — Rhône"],
        "last_regions": ("Île-de-France", "Auvergne-Rhône-Alpes"),
    }
    values = retain_multiselect_session(
        state,
        values_key="depts",
        signature_key="last_regions",
        current_signature=("Île-de-France",),
        seed_values=["75 — Paris"],
        allowed=["75 — Paris", "92 — Hauts-de-Seine"],
    )
    assert values == ["75 — Paris"]


def test_seed_session_value_does_not_overwrite_edits() -> None:
    state = {"job": "Data analyst"}
    seed_session_value(state, "job", "Developer")
    assert state["job"] == "Data analyst"
    empty: dict = {}
    seed_session_value(empty, "job", "Developer")
    assert empty["job"] == "Developer"


def test_clear_profile_widget_keys_drops_prefix_and_legacy() -> None:
    state = {
        "profile_12_target_job": "Dev",
        "profile_12_selected_countries": ["Canada"],
        "profile_first_name_12": "Jane",
        "profile_13_target_job": "Keep",
        "analysis": True,
    }
    clear_profile_widget_keys(state, 12)
    assert "profile_12_target_job" not in state
    assert "profile_12_selected_countries" not in state
    assert "profile_first_name_12" not in state
    assert state["profile_13_target_job"] == "Keep"
    assert state["analysis"] is True


def test_update_user_profile_roundtrip_until_next_change(sqlite_db) -> None:
    ok, msg = register_user(
        "Jane Doe",
        "jane.persist@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["Canada"],
        geo_by_country={
            "Canada": {
                "level1": ["Ontario"],
                "level2": [],
                "cities": ["Toronto"],
                "all_cities": False,
            }
        },
        phone="0600000000",
        job_max_age_days=14,
    )
    assert ok, msg
    from auth import authenticate_user

    logged_ok, _, user = authenticate_user("jane.persist@example.com", "Secret123!")
    assert logged_ok and user is not None
    user_id = int(user["id"])
    assert user["target_job_title"] == "Developer"
    assert user["selected_countries"] == ["Canada"]

    ok, message, updated = update_user_profile(
        user_id,
        "Jane Doe",
        "",
        "",
        [],
        [],
        [],
        False,
        "Canada",
        "CDI",
        "departement",
        20,
        "confirme",
        ["Informatique"],
        "Ingénieure Python",
        30,
        selected_countries=["Canada"],
        geo_by_country={
            "Canada": {
                "level1": ["Quebec"],
                "level2": [],
                "cities": ["Montréal"],
                "all_cities": False,
            }
        },
        phone="0611223344",
        work_mode="hybrid",
        salary_min=60000,
        skills_text="Python, FastAPI",
        diplomas_text=user.get("diplomas_text") or "",
        experiences_text=user.get("experiences_text") or "",
        daily_rate=0,
        portfolio_url="",
    )
    assert ok, message
    stored = get_user_by_id(user_id)
    assert stored is not None
    assert stored["target_job_title"] == "Ingénieure Python"
    assert stored["selected_countries"] == ["Canada"]
    assert stored["phone"] == "0611223344"
    assert stored["work_mode"] == "hybrid"
    assert stored["salary_min"] == 60000
    assert "FastAPI" in stored["skills_text"]
    assert stored["job_max_age_days"] == 30
    canada = (stored.get("geo_by_country") or {}).get("Canada") or {}
    assert "Quebec" in (canada.get("level1") or [])
    assert "Montréal" in (canada.get("cities") or [])

    again = get_user_by_id(user_id)
    assert again["target_job_title"] == stored["target_job_title"]
    assert again["selected_countries"] == stored["selected_countries"]
    assert again["geo_by_country"] == stored["geo_by_country"]
