"""JWT helpers for the REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from config import get_jwt_secret

JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 12


def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
