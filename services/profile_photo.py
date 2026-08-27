"""Candidate profile photo upload, storage, and display helpers."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from constants import (
    PROFILE_PHOTO_MAX_UPLOAD_BYTES,
    PROFILE_PHOTO_SIDEBAR_PX,
    PROFILE_PHOTO_SIZE_PX,
)
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


def _jpeg_data_url(image_bytes: bytes, mime: str, size_px: int | None = None) -> str:
    payload = image_bytes
    out_mime = mime or "image/jpeg"
    if size_px and size_px < PROFILE_PHOTO_SIZE_PX:
        image = Image.open(BytesIO(image_bytes))
        image = image.convert("RGB")
        image.thumbnail((size_px, size_px), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=70, optimize=True)
        payload = buffer.getvalue()
        out_mime = "image/jpeg"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{out_mime};base64,{encoded}"


def profile_photo_data_url(user_id: int, *, size_px: int | None = None) -> str | None:
    record = get_user_profile_photo(int(user_id))
    if not record:
        return None
    mime = record.get("mime_type") or "image/jpeg"
    return _jpeg_data_url(record["image_data"], mime, size_px=size_px)


def _photo_cache_key(size_px: int | None) -> str:
    if size_px:
        return f"{_SESSION_URL_KEY}_{int(size_px)}"
    return _SESSION_URL_KEY


def cached_profile_photo_data_url(
    user_id: int,
    session: dict[str, Any] | None = None,
    *,
    size_px: int | None = None,
) -> str | None:
    store = session if session is not None else {}
    cache_key = _photo_cache_key(size_px)
    if store.get(_SESSION_USER_KEY) == int(user_id) and cache_key in store:
        value = store.get(cache_key)
        return str(value) if value else None
    url = profile_photo_data_url(int(user_id), size_px=size_px)
    store[_SESSION_USER_KEY] = int(user_id)
    store[cache_key] = url or ""
    return url


def cached_sidebar_photo_data_url(
    user_id: int,
    session: dict[str, Any] | None = None,
) -> str | None:
    return cached_profile_photo_data_url(
        user_id,
        session,
        size_px=PROFILE_PHOTO_SIDEBAR_PX,
    )


def clear_profile_photo_cache(session: dict[str, Any] | None = None) -> None:
    if session is None:
        return
    for key in list(session.keys()):
        if key == _SESSION_URL_KEY or str(key).startswith(f"{_SESSION_URL_KEY}_"):
            session.pop(key, None)
    session.pop(_SESSION_USER_KEY, None)


def has_profile_photo(user_id: int) -> bool:
    return user_has_profile_photo(int(user_id))
