"""Сброс онбординга: команда /reset и колбэки диалога подтверждения

В onb:reset:start заходят из «Настроек» (там кнопка «🔄 Пройти заново»),
команда /reset рендерит подтверждение сразу, минуя «Настройки».

«Отмена» кидает туда, откуда пришли — в «Настройки» если онбординг
закончен, иначе в resume/welcome (см. _initial_state_screen).
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.menu import reset_confirm_keyboard, settings_keyboard
from bot.keyboards.onboarding import welcome_keyboard
from bot.screens import initial_state_screen
from bot.services.users import get_or_create_user, wipe_onboarding
from bot.texts import reset_confirm_text, settings_text, welcome_text
from bot.utils.names import display_name

router = Router()
log = logging.getLogger("bot.handlers.reset")


@router.message(Command("reset"))
async def cmd_reset(
    message: Message,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    # просто гарантируем что строка в БД есть, стираем только на confirm
    async with db_session_factory() as session:
        await get_or_create_user(session, tg_user)

    name = display_name(tg_user)
    await message.answer(
        reset_confirm_text(name), reply_markup=reset_confirm_keyboard()
    )


@router.callback_query(F.data == "onb:reset:start")
async def onboarding_reset_start(callback: CallbackQuery) -> None:
    name = display_name(callback.from_user)
    await callback.message.edit_text(
        reset_confirm_text(name), reply_markup=reset_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "onb:reset:confirm")
async def onboarding_reset_confirm(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        await wipe_onboarding(session, user)
        log.info(
            "[bold yellow]🔄 Onboarding reset confirmed[/bold yellow] user=%s",
            tg_user.id,
        )

    await callback.message.edit_text(
        welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer("🔄 Прогресс сброшен")


@router.callback_query(F.data == "onb:reset:cancel")
async def onboarding_reset_cancel(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)

    # вернёмся туда, откуда логично пришли: настройки если онбординг
    # уже закончен, иначе на resume/welcome
    if user.onboarding_completed:
        text, kb = settings_text(user, name), settings_keyboard()
    else:
        text, kb = initial_state_screen(user, name)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("↩ Отменено")
