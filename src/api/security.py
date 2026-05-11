"""Auth-примитивы: bcrypt-хеш паролей + HS256 JWT (access/refresh).

Refresh-токены идентифицируются по jti, в БД лежит только sha256-хеш самого
JWT — так logout/revoke не зависит от того, что именно мы положили в payload.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt

from api.config import settings

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(*, user_id: int, token_type: TokenType, ttl: timedelta, role: str) -> tuple[str, str, datetime]:
    """Возвращает (jwt_string, jti, expires_at)."""
    jti = uuid.uuid4().hex
    exp = _now() + ttl
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "role": role,
        "jti": jti,
        "iat": int(_now().timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, exp


def create_access_token(*, user_id: int, role: str = "user") -> tuple[str, datetime]:
    token, _jti, exp = _create_token(
        user_id=user_id,
        token_type="access",
        ttl=timedelta(minutes=settings.jwt_access_ttl_minutes),
        role=role,
    )
    return token, exp


def create_refresh_token(*, user_id: int, role: str = "user") -> tuple[str, str, datetime]:
    """Возвращает (jwt, token_hash_for_db, expires_at)."""
    token, _jti, exp = _create_token(
        user_id=user_id,
        token_type="refresh",
        ttl=timedelta(days=settings.jwt_refresh_ttl_days),
        role=role,
    )
    return token, hash_token(token), exp


def hash_token(token: str) -> str:
    """sha256(token) — детерминированный, помещается в char(64)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict:
    """Возвращает payload или поднимает jwt.PyJWTError.
    Если expected_type задан и не совпадает — ValueError.
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError(f"expected token type={expected_type}, got {payload.get('type')!r}")
    return payload


def generate_telegram_link_code() -> str:
    """Короткий человекочитаемый код для линковки бота к API-юзеру."""
    return secrets.token_urlsafe(8).upper().replace("_", "X").replace("-", "Y")[:12]
