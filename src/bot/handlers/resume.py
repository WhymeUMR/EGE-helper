"""Колбэки resume-экрана: «Продолжить» с того же шага или «Начать заново»

Сам экран показывает cmd_start (handlers.onboarding) когда у юзера
есть прогресс, но онбординг ещё не закончен.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.onboarding import welcome_keyboard
from bot.screens import step_screen
from bot.services.users import get_or_create_user, wipe_onboarding
from bot.texts import welcome_text
from bot.utils.names import display_name

router = Router()
log = logging.getLogger("bot.handlers.resume")


@router.callback_query(F.data == "onb:resume:continue")
async def onboarding_resume_continue(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)

    text, kb = step_screen(user, name)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("▶️ Продолжаем")


@router.callback_query(F.data == "onb:resume:restart")
async def onboarding_resume_restart(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        await wipe_onboarding(session, user)
        log.info(
            "[yellow]🔄 Onboarding restarted (mid-flow)[/yellow] user=%s",
            tg_user.id,
        )

    await callback.message.edit_text(
        welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer("🔄 Начинаем заново")
