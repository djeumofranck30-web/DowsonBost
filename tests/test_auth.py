"""Auth backend tests."""

from __future__ import annotations

from unittest.mock import patch

from auth import (
    authenticate_user,
    create_password_reset_token,
    register_user,
    reset_password_with_token,
)


def test_register_and_login(sqlite_db):
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

    ok_login, _, logged_in = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login
    assert logged_in["email"] == "jane@example.com"


def test_password_reset_token_flow(sqlite_db):
    ok, msg = register_user(
        "John Doe",
        "john@example.com",
        "Secret123!",
        target_job_title="Analyst",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok, _, token = create_password_reset_token("john@example.com")
    assert ok
    assert token

    ok_reset, msg = reset_password_with_token(token, "NewSecret456!")
    assert ok_reset, msg

    ok_old, _, _ = authenticate_user("john@example.com", "Secret123!")
    assert not ok_old

    ok_new, _, _ = authenticate_user("john@example.com", "NewSecret456!")
    assert ok_new


def test_register_sends_welcome_email(sqlite_db):
    with patch("email_service.send_welcome_email", return_value=(True, "sent")) as mock_send:
        ok, msg = register_user(
            "Alice Doe",
            "alice@example.com",
            "Secret123!",
            target_job_title="Developer",
            contract_type="CDI",
            experience_level="confirme",
            selected_countries=["France"],
            admin_regions=["Île-de-France"],
            selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
            selected_cities=["Paris"],
            preferred_language="fr",
        )
    assert ok, msg
    mock_send.assert_called_once()
    assert mock_send.call_args.args[0] == "alice@example.com"
    assert mock_send.call_args.args[1] == "Alice Doe"
    assert "success_email_sent" in msg or "confirmation" in msg.lower()
