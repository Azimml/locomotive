from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from ..config import settings


def create_access_token(subject: str, login: str) -> str:
    expires_delta = _parse_expiration(settings.JWT_EXPIRES_IN)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode: dict[str, Any] = {"sub": str(subject), "login": login, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


def _parse_expiration(value: str) -> timedelta:
    # Supports "7d", "12h", "30m"; defaults to days if no suffix
    value = value.strip().lower()
    if value.endswith("d"):
        return timedelta(days=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    if value.endswith("m"):
        return timedelta(minutes=int(value[:-1]))
    return timedelta(days=int(value))
