"""Candidate profile photo upload, storage, and display helpers."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from constants import PROFILE_PHOTO_MAX_UPLOAD_BYTES, PROFILE_PHOTO_SIZE_PX
from persistence import (
    delete_user_profile_photo,
    get_user_profile_photo,
    upsert_user_profile_photo,
    user_has_profile_photo,
)

ALLOWED_PHOTO_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_SESSION_URL_KEY = "_profile_photo_data_url"
_SESSION_USER_KEY = "_profile_photo_user_id"


def _center_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def normalize_profile_photo(raw: bytes, content_type: str = "") -> tuple[bool, str, bytes]:
    if not raw:
        return False, "empty", b""
    if len(raw) > PROFILE_PHOTO_MAX_UPLOAD_BYTES:
        return False, "too_large", b""
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime and mime not in ALLOWED_PHOTO_TYPES:
        return False, "invalid", b""
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return False, "invalid", b""
    image = _center_square(image.convert("RGB"))
    image = image.resize((PROFILE_PHOTO_SIZE_PX, PROFILE_PHOTO_SIZE_PX), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return True, "ok", buffer.getvalue()


def save_profile_photo(user_id: int, raw: bytes, content_type: str = "") -> tuple[bool, str]:
    ok, reason, payload = normalize_profile_photo(raw, content_type)
    if not ok:
        return False, reason
    upsert_user_profile_photo(int(user_id), "image/jpeg", payload)
    return True, "saved"


def remove_profile_photo(user_id: int) -> None:
    delete_user_profile_photo(int(user_id))


def profile_photo_data_url(user_id: int) -> str | None:
    record = get_user_profile_photo(int(user_id))
    if not record:
        return None
    encoded = base64.b64encode(record["image_data"]).decode("ascii")
    mime = record.get("mime_type") or "image/jpeg"
    return f"data:{mime};base64,{encoded}"


def cached_profile_photo_data_url(user_id: int, session: dict[str, Any] | None = None) -> str | None:
    store = session if session is not None else {}
    if store.get(_SESSION_USER_KEY) == int(user_id) and _SESSION_URL_KEY in store:
        value = store.get(_SESSION_URL_KEY)
        return str(value) if value else None
    url = profile_photo_data_url(int(user_id))
    store[_SESSION_USER_KEY] = int(user_id)
    store[_SESSION_URL_KEY] = url or ""
    return url


def clear_profile_photo_cache(session: dict[str, Any] | None = None) -> None:
    if session is None:
        return
    session.pop(_SESSION_URL_KEY, None)
    session.pop(_SESSION_USER_KEY, None)


def has_profile_photo(user_id: int) -> bool:
    return user_has_profile_photo(int(user_id))
