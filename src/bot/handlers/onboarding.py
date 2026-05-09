"""Поток онбординга: /start → welcome → класс → предметы → часы → калибровка

Тут все колбэки onb:*, кроме resume и reset — те живут отдельно
в handlers.resume и handlers.reset.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.catalog import (
    GRADE_LABELS,
    MAX_SUBJECTS,
    MIN_SUBJECTS,
    SUBJECT_KEYS,
    SUBJECT_LABELS,
    WEEKLY_HOURS_SET,
)
from bot.keyboards.menu import main_menu_keyboard
from bot.keyboards.onboarding import (
    about_back_keyboard,
    calibration_keyboard,
    grade_keyboard,
    hours_keyboard,
    subjects_keyboard,
    welcome_keyboard,
)
from bot.screens import initial_state_screen
from bot.services.users import get_or_create_user
from bot.texts import (
    ABOUT_TEXT,
    calibration_text,
    grade_text,
    hours_text,
    main_menu_text,
    subjects_text,
    welcome_text,
)
from bot.utils.names import display_name

router = Router()
log = logging.getLogger("bot.handlers.onboarding")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    redis: Redis,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user_id = tg_user.id
    key = f"user:{user_id}:starts"

    # счётчик /start за сутки на юзера, TTL 24ч
    starts_count = await redis.incr(key)
    if starts_count == 1:
        await redis.expire(key, 60 * 60 * 24)

    log.info(
        "[cyan]/start[/cyan] from [bold]%s[/bold] (@%s) — starts today: %s",
        user_id,
        tg_user.username or "—",
        starts_count,
    )

    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)

    name = display_name(tg_user)
    text, kb = initial_state_screen(user, name)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "onb:about")
async def onboarding_about(callback: CallbackQuery) -> None:
    await callback.message.edit_text(ABOUT_TEXT, reply_markup=about_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "onb:back_welcome")
async def onboarding_back_welcome(callback: CallbackQuery) -> None:
    name = display_name(callback.from_user)
    await callback.message.edit_text(
        welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "onb:continue")
async def onboarding_continue(callback: CallbackQuery) -> None:
    name = display_name(callback.from_user)
    await callback.message.edit_text(grade_text(name), reply_markup=grade_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("onb:grade:"))
async def onboarding_grade(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    grade = int(callback.data.split(":")[-1])
    tg_user = callback.from_user
    name = display_name(tg_user)

    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        user.grade = grade
        await session.commit()
        await session.refresh(user)

        await callback.message.edit_text(
            subjects_text(user, name),
            reply_markup=subjects_keyboard(set(user.subjects or [])),
        )

    await callback.answer(f"✅ {GRADE_LABELS.get(grade, str(grade))}")


@router.callback_query(F.data.startswith("onb:subject:"))
async def onboarding_toggle_subject(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    subject = callback.data.split(":")[-1]
    if subject not in SUBJECT_KEYS:
        await callback.answer("❌ Неизвестный предмет", show_alert=True)
        return

    tg_user = callback.from_user
    name = display_name(tg_user)

    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        selected = set(user.subjects or [])

        if subject in selected:
            selected.remove(subject)
            toast = f"➖ {SUBJECT_LABELS[subject]}"
        else:
            if len(selected) >= MAX_SUBJECTS:
                await callback.answer(
                    f"🔒 Максимум {MAX_SUBJECTS} предметов.\n"
                    "Сначала сними отметку с другого.",
                    show_alert=True,
                )
                return
            selected.add(subject)
            toast = f"➕ {SUBJECT_LABELS[subject]}"

        user.subjects = sorted(selected)
        await session.commit()

        await callback.message.edit_text(
            subjects_text(user, name),
            reply_markup=subjects_keyboard(set(user.subjects)),
        )

    await callback.answer(toast)


@router.callback_query(F.data == "onb:subjects:done")
async def onboarding_subjects_done(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)

    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        if len(set(user.subjects or [])) < MIN_SUBJECTS:
            await callback.answer(
                f"⚠️ Нужно выбрать минимум {MIN_SUBJECTS} предмета",
                show_alert=True,
            )
            return
        current_hours = user.weekly_hours

    await callback.message.edit_text(
        hours_text(name), reply_markup=hours_keyboard(selected=current_hours)
    )
    await callback.answer()


@router.callback_query(F.data == "onb:back_subjects")
async def onboarding_back_subjects(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        await callback.message.edit_text(
            subjects_text(user, name),
            reply_markup=subjects_keyboard(set(user.subjects or [])),
        )
    await callback.answer()


@router.callback_query(F.data == "onb:back_hours")
async def onboarding_back_hours(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        current_hours = user.weekly_hours
    await callback.message.edit_text(
        hours_text(name), reply_markup=hours_keyboard(selected=current_hours)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onb:hours:"))
async def onboarding_hours(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        hours = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ Неверное значение", show_alert=True)
        return

    if hours not in WEEKLY_HOURS_SET:
        # защита от подмены callback_data — UI таких вариантов не даёт
        await callback.answer("❌ Недопустимое значение часов", show_alert=True)
        return

    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        user.weekly_hours = hours
        await session.commit()
        await session.refresh(user)
        subjects = list(user.subjects or [])

    await callback.message.edit_text(
        calibration_text(subjects, name),
        reply_markup=calibration_keyboard(subjects),
    )
    await callback.answer(f"⏱ {hours} ч/нед")


async def _finalize_onboarding(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ставим onboarding_completed=True и кидаем юзера в главное меню"""
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)
        user.onboarding_completed = True
        await session.commit()
        await session.refresh(user)

    log.info(
        "[bold green]🎉 Onboarding finished[/bold green] for [bold]%s[/bold]",
        tg_user.id,
    )
    await callback.message.edit_text(
        main_menu_text(user, name), reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data.startswith("onb:calib:start:"))
async def onboarding_calibration_start(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # пробник пока не реализован — ловим выбор предмета в логи и сразу
    # завершаем онбординг без калибровки. когда подключим SM-2 и парсинг
    # задач, отсюда будет ветка в реальный пробник
    subject = callback.data.rsplit(":", 1)[-1]
    log.info(
        "[yellow]📝 Calibration requested[/yellow] subject=%s user=%s "
        "(not implemented yet)",
        subject,
        callback.from_user.id,
    )
    await callback.answer(
        "📝 Пробник скоро появится — пока завершаю онбординг без него.",
        show_alert=True,
    )
    await _finalize_onboarding(callback, db_session_factory)


@router.callback_query(F.data == "onb:calib:skip")
async def onboarding_calibration_skip(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await callback.answer("⏭ Пропускаем")
    await _finalize_onboarding(callback, db_session_factory)
