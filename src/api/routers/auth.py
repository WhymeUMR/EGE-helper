"""Auth: register / login / refresh / logout.

Refresh-токены — rotating: при /refresh старый ревокается, выдаётся новая пара.
В БД лежит только sha256(token), сам JWT клиент видит один раз.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.deps import get_session
from api.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
import jwt
from bot.db.models import RefreshToken, User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = Field(default=None, max_length=64)

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, v: str) -> str:
        # минимально: есть буква и цифра. Без UPPER требований чтобы не бесить.
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


async def _issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    access, access_exp = create_access_token(user_id=user.id, role=user.role)
    refresh, refresh_hash, refresh_exp = create_refresh_token(user_id=user.id, role=user.role)
    session.add(
        RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_exp)
    )
    await session.flush()
    return TokenPair(access_token=access, refresh_token=refresh, expires_at=access_exp)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    if not settings.registration_open:
        raise HTTPException(status_code=403, detail="registration is closed")
    existing = await session.scalar(select(User).where(User.email == body.email.lower()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        first_name=body.first_name,
    )
    session.add(user)
    await session.flush()
    pair = await _issue_token_pair(session, user)
    await session.commit()
    return pair


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        # одно и то же сообщение чтобы не палить какие email есть в базе
        raise HTTPException(status_code=401, detail="invalid email or password")
    if user.is_banned or user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="account disabled")
    pair = await _issue_token_pair(session, user)
    await session.commit()
    return pair


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="invalid refresh token")
    token_hash = hash_token(body.refresh_token)
    rt = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if rt is None or rt.revoked_at is not None:
        raise HTTPException(status_code=401, detail="refresh token revoked")
    if rt.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="refresh token expired")
    user = await session.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None or user.deleted_at is not None or user.is_banned:
        raise HTTPException(status_code=401, detail="user inactive")
    # rotation: ревокаем использованный refresh
    rt.revoked_at = datetime.now(timezone.utc)
    pair = await _issue_token_pair(session, user)
    await session.commit()
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest, session: AsyncSession = Depends(get_session)
) -> None:
    token_hash = hash_token(body.refresh_token)
    rt = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)
        await session.commit()
    return None
