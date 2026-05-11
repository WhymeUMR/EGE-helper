"""/me/* — профиль, настройки, soft-delete, привязка Telegram."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.deps import get_current_user, get_session
from api.security import generate_telegram_link_code
from bot.catalog import MAX_SUBJECTS, MIN_SUBJECTS, SUBJECT_KEYS, WEEKLY_HOURS_SET
from bot.db.models import RefreshToken, TelegramLinkCode, User

router = APIRouter(prefix="/api/v1/me", tags=["me"])


class MeOut(BaseModel):
    id: int
    email: str | None
    role: str
    telegram_id: int | None
    first_name: str | None
    username: str | None
    grade: int | None
    subjects: list[str]
    weekly_hours: int | None
    onboarding_completed: bool
    settings: dict
    created_at: datetime


def _user_to_out(u: User) -> MeOut:
    return MeOut(
        id=u.id,
        email=u.email,
        role=u.role,
        telegram_id=u.telegram_id,
        first_name=u.first_name,
        username=u.username,
        grade=u.grade,
        subjects=list(u.subjects or []),
        weekly_hours=u.weekly_hours,
        onboarding_completed=u.onboarding_completed,
        settings=dict(u.settings or {}),
        created_at=u.created_at,
    )


@router.get("", response_model=MeOut)
async def get_me(user: User = Depends(get_current_user)) -> MeOut:
    return _user_to_out(user)


# ───────────────────── профиль ─────────────────────


class ProfilePatch(BaseModel):
    first_name: str | None = Field(default=None, max_length=64)
    grade: int | None = Field(default=None)
    subjects: list[str] | None = None
    weekly_hours: int | None = None
    onboarding_completed: bool | None = None


@router.patch("/profile", response_model=MeOut)
async def patch_profile(
    body: ProfilePatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    if body.grade is not None and body.grade not in (10, 11):
        raise HTTPException(status_code=422, detail="grade must be 10 or 11")
    if body.subjects is not None:
        unknown = [s for s in body.subjects if s not in SUBJECT_KEYS]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown subjects: {unknown}")
        if not (MIN_SUBJECTS <= len(body.subjects) <= MAX_SUBJECTS):
            raise HTTPException(
                status_code=422,
                detail=f"subjects count must be between {MIN_SUBJECTS} and {MAX_SUBJECTS}",
            )
    if body.weekly_hours is not None and body.weekly_hours not in WEEKLY_HOURS_SET:
        raise HTTPException(
            status_code=422, detail=f"weekly_hours must be one of {sorted(WEEKLY_HOURS_SET)}"
        )

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(user, k, v)
    await session.commit()
    await session.refresh(user)
    return _user_to_out(user)


# ───────────────────── settings ─────────────────────


class SettingsPatch(BaseModel):
    """Свободная карта настроек. Мердж: ключи из body заменяют существующие,
    None-значение удаляет ключ. Незатронутые ключи сохраняются.
    """

    settings: dict


@router.patch("/settings", response_model=MeOut)
async def patch_settings(
    body: SettingsPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    merged = dict(user.settings or {})
    for k, v in body.settings.items():
        if v is None:
            merged.pop(k, None)
        else:
            merged[k] = v
    user.settings = merged
    await session.commit()
    await session.refresh(user)
    return _user_to_out(user)


# ───────────────────── delete ─────────────────────


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft-delete: проставляем deleted_at, ревокаем все refresh-токены,
    освобождаем email/telegram_id для возможной перерегистрации."""
    user.deleted_at = datetime.now(timezone.utc)
    # email и telegram_id — UNIQUE; затираем чтобы освободить
    if user.email:
        user.email = f"deleted-{user.id}+{user.email}"
    user.telegram_id = None
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return None


# ───────────────────── telegram link ─────────────────────


class TelegramLinkOut(BaseModel):
    code: str
    expires_at: datetime
    instructions: str = (
        "Отправь эту команду в @ege_helper_bot: /link <code>. "
        "Код одноразовый и действует ограниченное время."
    )


@router.post("/telegram/link", response_model=TelegramLinkOut, status_code=status.HTTP_201_CREATED)
async def create_telegram_link(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TelegramLinkOut:
    """Генерим одноразовый код, который пользователь скармливает боту."""
    if user.telegram_id is not None:
        raise HTTPException(status_code=409, detail="telegram already linked; unlink first")
    # инвалидируем предыдущие неиспользованные коды этого юзера
    await session.execute(
        update(TelegramLinkCode)
        .where(
            TelegramLinkCode.user_id == user.id,
            TelegramLinkCode.used_at.is_(None),
            TelegramLinkCode.expires_at > datetime.now(timezone.utc),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    code = generate_telegram_link_code()
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.telegram_link_ttl_minutes)
    session.add(TelegramLinkCode(user_id=user.id, code=code, expires_at=exp))
    await session.commit()
    return TelegramLinkOut(code=code, expires_at=exp)


@router.delete("/telegram/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    if user.telegram_id is None:
        raise HTTPException(status_code=404, detail="no telegram linked")
    user.telegram_id = None
    user.username = None
    await session.execute(
        delete(TelegramLinkCode).where(TelegramLinkCode.user_id == user.id)
    )
    await session.commit()
    return None
