"""User CRUD + state-машина онбординга

Все хендлеры ходят сюда читать/писать юзера. Это единственное место,
где решается:
- как синкать имя и username из Telegram при заходе
- что считать «текущим шагом онбординга» по тому, что лежит в БД
"""

from __future__ import annotations

import logging

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog import MIN_SUBJECTS
from bot.db.models import User

log = logging.getLogger("bot.services.users")


async def get_or_create_user(
    session: AsyncSession,
    tg_user: TelegramUser,
) -> User:
    """достать юзера по telegram_id или создать; заодно синкнуть имя/username"""
    result = await session.execute(
        select(User).where(User.telegram_id == tg_user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=tg_user.id,
            first_name=tg_user.first_name,
            username=tg_user.username,
            subjects=[],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        log.info(
            "[green]👤 New user created:[/green] [bold]%s[/bold] (%s)",
            tg_user.id,
            tg_user.first_name or "—",
        )
        return user

    # юзер мог переименоваться или сменить @ник — подхватываем
    changed = False
    if user.first_name != tg_user.first_name:
        user.first_name = tg_user.first_name
        changed = True
    if user.username != tg_user.username:
        user.username = tg_user.username
        changed = True
    if changed:
        await session.commit()
        await session.refresh(user)
    return user


async def wipe_onboarding(session: AsyncSession, user: User) -> None:
    """стереть всё, что собрано в онбординге, и открыть его заново"""
    user.grade = None
    user.subjects = []
    user.weekly_hours = None
    user.onboarding_completed = False
    await session.commit()
    await session.refresh(user)


def onboarding_step_for(user: User) -> str:
    """сохранённое состояние юзера → канонический шаг онбординга

    используется в resume-логике и для лейбла на resume-экране.
    порядок проверок важен — форвардим на самый продвинутый шаг,
    до которого юзер успел дойти
    """
    if user.weekly_hours is not None:
        return "calibration"
    if len(user.subjects or []) >= MIN_SUBJECTS:
        return "hours"
    if user.grade is not None:
        return "subjects"
    return "welcome"
