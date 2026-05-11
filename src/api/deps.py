"""DB-сессия и auth-зависимости для роутов."""

from __future__ import annotations

from typing import AsyncIterator

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.config import settings
from api.security import decode_token
from bot.db.models import User
from sqlalchemy import select

engine = create_async_engine(settings.postgres_dsn, echo=False, pool_size=10)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    token = _extract_bearer(authorization)
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
    except (jwt.PyJWTError, ValueError):
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or user.deleted_at is not None or user.is_banned:
        return None
    return user


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user
