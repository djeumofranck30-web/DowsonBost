"""Candidate job-board account linking."""

from __future__ import annotations

from auth import authenticate_user, delete_user_account, register_user
from job_providers import (
    CONNECTABLE_JOB_PROVIDERS,
    JOB_PROVIDER_INDEED,
    JOB_PROVIDER_LINKEDIN,
    job_board_display_name,
    provider_key_from_job_source,
)
import persistence
from persistence import (
    connect_all_job_accounts,
    connect_job_account,
    disconnect_job_account,
    get_connected_job_account,
    init_persistence_tables,
    list_connected_job_accounts,
)


def _reset_persistence() -> None:
    persistence._persistence_initialized_for = None


def _register_jane() -> int:
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok_login, _, user = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login and user is not None
    return int(user["id"])


def test_provider_key_from_job_source_maps_connectable_sites():
    assert provider_key_from_job_source("Indeed") == JOB_PROVIDER_INDEED
    assert provider_key_from_job_source("LinkedIn Jobs") == JOB_PROVIDER_LINKEDIN
    assert provider_key_from_job_source("Welcome to the Jungle") == "wttj"
    assert provider_key_from_job_source("Hello Work") == "hellowork"
    assert provider_key_from_job_source("Adzuna") is None
    assert provider_key_from_job_source("Google Jobs") is None
    assert provider_key_from_job_source("") is None


def test_job_board_display_name_uses_short_brand():
    assert job_board_display_name(JOB_PROVIDER_INDEED) == "Indeed"
    assert job_board_display_name(JOB_PROVIDER_LINKEDIN) == "LinkedIn"


def test_connect_and_disconnect_job_account(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()

    ok, msg = connect_job_account(user_id, "indeed", "Jane@Indeed.com")
    assert ok, msg
    account = get_connected_job_account(user_id, "indeed")
    assert account is not None
    assert account["provider"] == "indeed"
    assert account["account_email"] == "jane@indeed.com"

    ok, msg = connect_job_account(user_id, "indeed", "other@indeed.com")
    assert ok, msg
    updated = get_connected_job_account(user_id, "INDEED")
    assert updated is not None
    assert updated["account_email"] == "other@indeed.com"

    listed = list_connected_job_accounts(user_id)
    assert len(listed) == 1

    ok, msg = disconnect_job_account(user_id, "indeed")
    assert ok, msg
    assert get_connected_job_account(user_id, "indeed") is None
    assert list_connected_job_accounts(user_id) == []


def test_connect_rejects_invalid_email_and_unknown_provider(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()

    ok, msg = connect_job_account(user_id, "indeed", "not-an-email")
    assert not ok
    assert msg

    ok, msg = connect_job_account(user_id, "facebook", "jane@example.com")
    assert not ok
    assert msg

    ok, msg = connect_job_account(user_id, "adzuna", "jane@example.com")
    assert not ok


def test_connect_all_job_accounts_uses_candidate_email(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()

    ok, msg = connect_job_account(user_id, "linkedin", "pro@linkedin.com")
    assert ok, msg

    ok, msg, count = connect_all_job_accounts(user_id, "jane@example.com")
    assert ok, msg
    assert count == len(CONNECTABLE_JOB_PROVIDERS) - 1

    accounts = {row["provider"]: row["account_email"] for row in list_connected_job_accounts(user_id)}
    assert accounts["linkedin"] == "pro@linkedin.com"
    assert accounts["indeed"] == "jane@example.com"
    assert set(accounts) == set(CONNECTABLE_JOB_PROVIDERS)

    ok, msg, count = connect_all_job_accounts(user_id, "jane@example.com")
    assert ok, msg
    assert count == 0


def test_connect_all_rejects_invalid_email(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()
    ok, msg, count = connect_all_job_accounts(user_id, "bad")
    assert not ok
    assert count == 0
    assert list_connected_job_accounts(user_id) == []


def test_delete_account_removes_connected_job_accounts(sqlite_db):
    _reset_persistence()
    init_persistence_tables()
    user_id = _register_jane()
    assert connect_job_account(user_id, "indeed", "jane@example.com")[0]
    assert connect_job_account(user_id, "hellowork", "jane@example.com")[0]
    assert len(list_connected_job_accounts(user_id)) == 2

    ok, msg = delete_user_account(user_id)
    assert ok, msg
    assert list_connected_job_accounts(user_id) == []
