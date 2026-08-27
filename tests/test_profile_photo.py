"""Per-user profile photos stay private and display as a data URL."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from auth import authenticate_user, register_user
from persistence import get_user_profile_photo
from services.profile_photo import (
    profile_photo_data_url,
    remove_profile_photo,
    save_profile_photo,
)


def _register(email: str, name: str) -> dict:
    ok, msg = register_user(
        name,
        email,
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
    ok_login, _, user = authenticate_user(email, "Secret123!")
    assert ok_login and user is not None
    return user


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (40, 24), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_profile_photo_is_private_per_user(sqlite_db):
    jane = _register("jane@example.com", "Jane Doe")
    ali = _register("ali@example.com", "Ali Martin")
    jane_id = int(jane["id"])
    ali_id = int(ali["id"])

    ok, reason = save_profile_photo(jane_id, _png_bytes((14, 116, 144)), "image/png")
    assert ok, reason
    assert get_user_profile_photo(ali_id) is None
    jane_url = profile_photo_data_url(jane_id)
    assert jane_url and jane_url.startswith("data:image/jpeg;base64,")
    assert profile_photo_data_url(ali_id) is None

    save_profile_photo(ali_id, _png_bytes((232, 185, 35)), "image/png")
    ali_url = profile_photo_data_url(ali_id)
    assert ali_url
    assert ali_url != jane_url

    remove_profile_photo(jane_id)
    assert profile_photo_data_url(jane_id) is None
    assert profile_photo_data_url(ali_id)


def test_invalid_profile_photo_is_rejected(sqlite_db):
    jane = _register("jane@example.com", "Jane Doe")
    ok, reason = save_profile_photo(int(jane["id"]), b"not-an-image", "image/png")
    assert not ok
    assert reason == "invalid"
    assert get_user_profile_photo(int(jane["id"])) is None
