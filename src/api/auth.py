"""Опциональный Bearer: пустой API_TOKEN — пропускаем всех."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from api.config import settings


async def require_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
