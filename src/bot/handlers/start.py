from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import User as TelegramUser
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import User
from bot.keyboards.onboarding import (
    MAX_SUBJECTS,
    SUBJECTS,
    WEEKLY_HOURS,
    about_back_keyboard,
    calibration_keyboard,
    grade_keyboard,
    hours_keyboard,
    main_menu_keyboard,
    reset_confirm_keyboard,
    resume_keyboard,
    settings_keyboard,
    subjects_keyboard,
    welcome_keyboard,
)

router = Router()
log = logging.getLogger("bot.handlers")

SUBJECT_KEYS = {key for key, _, _ in SUBJECTS}
SUBJECT_LABELS = {key: f"{emoji} {label}" for key, label, emoji in SUBJECTS}
SUBJECT_EMOJIS = {key: emoji for key, _, emoji in SUBJECTS}
WEEKLY_HOURS_SET = set(WEEKLY_HOURS)

GRADE_LABELS = {
    10: "📘 10 класс",
    11: "🎓 11 класс",
}

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
TOTAL_ONBOARDING_STEPS = 3

# Названия шагов для resume-экрана. Калибровка — формально опциональная,
# но с точки зрения юзера это ещё один экран онбординга, поэтому показываем.
STEP_LABELS = {
    "subjects": "📚 Предметы",
    "hours": "⏱ Время на подготовку",
    "calibration": "🎯 Пробник",
}

try:
    _MOSCOW_TZ: ZoneInfo | None = ZoneInfo("Europe/Moscow")
except ZoneInfoNotFoundError:  # pragma: no cover - tzdata missing
    _MOSCOW_TZ = None


def _safe_name(name: str | None, fallback: str = "друг") -> str:
    """Return an HTML-safe display name; fallback if Telegram didn't give one."""
    if not name:
        return fallback
    cleaned = name.strip()
    return escape(cleaned) if cleaned else fallback


def _display_name(tg_user: TelegramUser | None, fallback: str = "друг") -> str:
    if tg_user is None:
        return fallback
    return _safe_name(tg_user.first_name, fallback=fallback)


def _greeting(name: str) -> str:
    """Time-aware greeting in MSK; falls back to local time if tzdata is missing."""
    now = datetime.now(_MOSCOW_TZ) if _MOSCOW_TZ else datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        prefix = "☀️ Доброе утро"
    elif 12 <= hour < 17:
        prefix = "🌤 Добрый день"
    elif 17 <= hour < 23:
        prefix = "🌆 Добрый вечер"
    else:
        prefix = "🌙 Доброй ночи"
    return f"{prefix}, <b>{name}</b>!"


def _progress_bar(step: int, total: int = TOTAL_ONBOARDING_STEPS) -> str:
    step = max(0, min(step, total))
    return "▰" * step + "▱" * (total - step)


def _step_header(step: int, title: str, icon: str) -> str:
    return (
        f"{icon} <b>Шаг {step} из {TOTAL_ONBOARDING_STEPS} — {title}</b>  "
        f"{_progress_bar(step)}"
    )


def _onboarding_step_for(user: User) -> str:
    """Map persisted user state -> canonical onboarding step.

    Used both for resume logic and for the resume-screen label.
    Order matters: we forward the user to the most advanced step they reached.
    """
    if user.weekly_hours is not None:
        return "calibration"
    if len(user.subjects or []) >= 2:
        return "hours"
    if user.grade is not None:
        return "subjects"
    return "welcome"


def _welcome_text(name: str) -> str:
    return (
        f"👋 <b>Привет, {name}!</b>\n"
        f"Я — твой персональный помощник по подготовке к <b>ЕГЭ</b>.\n"
        f"<i>{DIVIDER}</i>\n\n"
        "Вот что я умею:\n"
        "• 🎯 <b>Тренировки</b> по реальным заданиям ФИПИ\n"
        "• 📊 <b>Статистика</b> и аналитика твоего прогресса\n"
        "• 🗓 <b>Персональный план</b> подготовки\n"
        "• 🔔 <b>Напоминания</b>, чтобы не забросить\n\n"
        "Сначала пройдём короткий <b>онбординг</b> — это займёт "
        "<i>меньше минуты</i> и поможет мне подобрать материалы именно "
        f"под тебя, {name}.\n\n"
        "Готов? 👇"
    )


ABOUT_TEXT = (
    "ℹ️ <b>О боте</b>\n"
    f"<i>{DIVIDER}</i>\n\n"
    "Я помогаю готовиться к ЕГЭ системно и без выгорания:\n\n"
    "• 📐 <b>Адаптивные задания</b> — ловлю слабые темы и подкидываю их чаще\n"
    "• 📈 <b>Прогресс</b> — видишь, сколько баллов уже «в кармане»\n"
    "• 🧠 <b>Spaced repetition</b> — забываешь меньше, помнишь дольше\n"
    "• 🔒 <b>Приватность</b> — твои данные используются только для обучения\n\n"
    "<i>Версия:</i> <code>0.1.0</code>"
)


def _grade_text(name: str) -> str:
    return (
        f"{_step_header(1, 'Класс', '🎓')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, в каком ты <b>сейчас классе</b>?\n"
        "Это нужно, чтобы я понимал, сколько у нас времени до экзамена "
        "и какие темы уже пройдены в школе. ⏳"
    )


def _subjects_text(user: User, name: str) -> str:
    selected = list(user.subjects or [])
    selected_count = len(selected)

    if selected:
        chosen = "\n".join(f"  • {SUBJECT_LABELS.get(s, s)}" for s in selected)
        chosen_block = f"\n<b>Выбрано:</b>\n{chosen}\n"
    else:
        chosen_block = "\n<i>Пока ничего не выбрано.</i>\n"

    if selected_count >= MAX_SUBJECTS:
        hint = (
            f"⚡ Достигнут максимум <b>{MAX_SUBJECTS}</b> предметов. "
            "Чтобы поменять — сними отметку с другого."
        )
    elif selected_count >= 2:
        hint = "✅ Можно нажать <b>«Готово»</b>, либо добавить ещё."
    else:
        need = 2 - selected_count
        hint = f"⚠️ {name}, выбери ещё <b>{need}</b>, чтобы продолжить."

    return (
        f"{_step_header(2, 'Предметы', '📚')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        "Отметь все предметы, которые <b>сдаёшь</b> "
        f"(<b>2–{MAX_SUBJECTS}</b>).\n"
        "Нажми ещё раз, чтобы снять отметку.\n"
        f"{chosen_block}\n"
        f"{hint}"
    )


def _hours_text(name: str) -> str:
    return (
        f"{_step_header(3, 'Время на подготовку', '⏱')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, сколько часов в неделю ты готов уделять подготовке?\n"
        "От этого зависит, сколько задач я буду давать в день "
        "(в среднем <b>~17 минут</b> на одну).\n\n"
        "Выбирай честно — лучше 20 часов и стабильно, чем 40 и сорваться. 💪"
    )


def _calibration_text(subjects: list[str], name: str) -> str:
    chosen = ", ".join(SUBJECT_LABELS.get(s, s) for s in subjects) or "—"
    return (
        "🎯 <b>Пробник — подбираем уровень</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"<b>Твои предметы:</b> {chosen}\n\n"
        f"{name}, если хочешь, можешь прямо сейчас написать <b>пробник</b> "
        "по одному из выбранных предметов. По его результатам я точнее "
        "настрою сложность задач и план подготовки.\n\n"
        "Если пропустишь — ничего страшного, я разберусь по ходу занятий, "
        "просто это займёт пару недель. ⏳\n\n"
        "<i>⚠️ Пока пробник в разработке — кнопки ниже зарезервированы, "
        "но дадут результат после ближайшего апдейта.</i>"
    )


def _resume_text(user: User, name: str) -> str:
    step = _onboarding_step_for(user)
    label = STEP_LABELS.get(step, "—")
    return (
        f"👋 <b>С возвращением, {name}!</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"Ты остановился на шаге <b>{label}</b>.\n"
        "Продолжим с того же места — или начнём заново?"
    )


def _settings_text(user: User, name: str) -> str:
    grade = GRADE_LABELS.get(user.grade or -1, "—")
    subjects = user.subjects or []
    if subjects:
        subjects_str = ", ".join(SUBJECT_LABELS.get(s, s) for s in subjects)
    else:
        subjects_str = "—"
    hours_str = f"{user.weekly_hours} ч/нед" if user.weekly_hours else "—"
    return (
        "⚙️ <b>Настройки</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"<b>{name}</b>, твой текущий профиль:\n\n"
        f"👤 <b>Класс:</b> {grade}\n"
        f"📚 <b>Предметы:</b> {subjects_str}\n"
        f"⏱ <b>Темп:</b> {hours_str}\n\n"
        "<i>Пока единственный настраиваемый пункт — пройти онбординг "
        "заново, если хочешь поменять профиль целиком.</i>"
    )


def _reset_confirm_text(name: str) -> str:
    return (
        "⚠️ <b>Подтверждение</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, точно хочешь пройти онбординг заново?\n"
        "Класс, предметы и темп будут <b>стёрты</b>, и мы начнём с чистого листа."
    )


def _main_menu_text(user: User, name: str) -> str:
    grade = GRADE_LABELS.get(user.grade or -1, "—")
    subjects = user.subjects or []
    if subjects:
        emojis = " ".join(SUBJECT_EMOJIS.get(s, "•") for s in subjects)
        subjects_str = f"{emojis}  <i>({len(subjects)})</i>"
    else:
        subjects_str = "—"
    hours_str = f"{user.weekly_hours} ч/нед" if user.weekly_hours else "—"

    return (
        f"{_greeting(name)}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"👤 <b>Класс:</b> {grade}\n"
        f"📚 <b>Предметы:</b> {subjects_str}\n"
        f"⏱ <b>Темп:</b> {hours_str}\n\n"
        "🎯 Что делаем дальше? 👇"
    )


def _step_screen(
    user: User, name: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Return (text, keyboard) for the current onboarding step.

    Used to forward the user to where they actually are (resume:continue).
    """
    step = _onboarding_step_for(user)
    if step == "subjects":
        return (
            _subjects_text(user, name),
            subjects_keyboard(set(user.subjects or [])),
        )
    if step == "hours":
        return _hours_text(name), hours_keyboard(selected=user.weekly_hours)
    if step == "calibration":
        subjects = list(user.subjects or [])
        return _calibration_text(subjects, name), calibration_keyboard(subjects)
    return _welcome_text(name), welcome_keyboard()


def _initial_state_screen(
    user: User, name: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Pick the right entry-point screen based on persisted user state."""
    if user.onboarding_completed:
        return _main_menu_text(user, name), main_menu_keyboard()
    if _onboarding_step_for(user) == "welcome":
        return _welcome_text(name), welcome_keyboard()
    return _resume_text(user, name), resume_keyboard()


async def _get_or_create_user(
    session: AsyncSession,
    tg_user: TelegramUser,
) -> User:
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

    # Refresh stale Telegram metadata so renames/usernames stay in sync.
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


async def _wipe_onboarding(session: AsyncSession, user: User) -> None:
    """Clear all onboarding-collected fields and re-open onboarding."""
    user.grade = None
    user.subjects = []
    user.weekly_hours = None
    user.onboarding_completed = False
    await session.commit()
    await session.refresh(user)


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

    # Track daily /start hits per user; reset every 24h.
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
        user = await _get_or_create_user(session, tg_user)

    name = _display_name(tg_user)
    text, kb = _initial_state_screen(user, name)
    await message.answer(text, reply_markup=kb)


@router.message(Command("reset"))
async def cmd_reset(
    message: Message,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    # Just to make sure the row exists; the actual wipe happens on confirm.
    async with db_session_factory() as session:
        await _get_or_create_user(session, tg_user)

    name = _display_name(tg_user)
    await message.answer(
        _reset_confirm_text(name), reply_markup=reset_confirm_keyboard()
    )


@router.callback_query(F.data == "onb:about")
async def onboarding_about(callback: CallbackQuery) -> None:
    await callback.message.edit_text(ABOUT_TEXT, reply_markup=about_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "onb:back_welcome")
async def onboarding_back_welcome(callback: CallbackQuery) -> None:
    name = _display_name(callback.from_user)
    await callback.message.edit_text(
        _welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "onb:continue")
async def onboarding_continue(callback: CallbackQuery) -> None:
    name = _display_name(callback.from_user)
    await callback.message.edit_text(_grade_text(name), reply_markup=grade_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("onb:grade:"))
async def onboarding_grade(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    grade = int(callback.data.split(":")[-1])
    tg_user = callback.from_user
    name = _display_name(tg_user)

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        user.grade = grade
        await session.commit()
        await session.refresh(user)

        await callback.message.edit_text(
            _subjects_text(user, name),
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
    name = _display_name(tg_user)

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
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
            _subjects_text(user, name),
            reply_markup=subjects_keyboard(set(user.subjects)),
        )

    await callback.answer(toast)


@router.callback_query(F.data == "onb:subjects:done")
async def onboarding_subjects_done(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        if len(set(user.subjects or [])) < 2:
            await callback.answer(
                "⚠️ Нужно выбрать минимум 2 предмета", show_alert=True
            )
            return
        current_hours = user.weekly_hours

    await callback.message.edit_text(
        _hours_text(name), reply_markup=hours_keyboard(selected=current_hours)
    )
    await callback.answer()


@router.callback_query(F.data == "onb:back_subjects")
async def onboarding_back_subjects(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        await callback.message.edit_text(
            _subjects_text(user, name),
            reply_markup=subjects_keyboard(set(user.subjects or [])),
        )
    await callback.answer()


@router.callback_query(F.data == "onb:back_hours")
async def onboarding_back_hours(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        current_hours = user.weekly_hours
    await callback.message.edit_text(
        _hours_text(name), reply_markup=hours_keyboard(selected=current_hours)
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
        # Защита на случай подмены callback_data — UI таких опций не даёт.
        await callback.answer("❌ Недопустимое значение часов", show_alert=True)
        return

    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        user.weekly_hours = hours
        await session.commit()
        await session.refresh(user)
        subjects = list(user.subjects or [])

    await callback.message.edit_text(
        _calibration_text(subjects, name),
        reply_markup=calibration_keyboard(subjects),
    )
    await callback.answer(f"⏱ {hours} ч/нед")


async def _finalize_onboarding(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        user.onboarding_completed = True
        await session.commit()
        await session.refresh(user)

    log.info(
        "[bold green]🎉 Onboarding finished[/bold green] for [bold]%s[/bold]",
        tg_user.id,
    )
    await callback.message.edit_text(
        _main_menu_text(user, name), reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data.startswith("onb:calib:start:"))
async def onboarding_calibration_start(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Пробник пока не реализован: подтверждаем выбор, но завершаем онбординг
    # без калибровки. После релиза пробника здесь будет переход к нему.
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


@router.callback_query(F.data == "onb:resume:continue")
async def onboarding_resume_continue(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)

    text, kb = _step_screen(user, name)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("▶️ Продолжаем")


@router.callback_query(F.data == "onb:resume:restart")
async def onboarding_resume_restart(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        await _wipe_onboarding(session, user)
        log.info(
            "[yellow]🔄 Onboarding restarted (mid-flow)[/yellow] user=%s",
            tg_user.id,
        )

    await callback.message.edit_text(
        _welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer("🔄 Начинаем заново")


@router.callback_query(F.data == "onb:reset:start")
async def onboarding_reset_start(callback: CallbackQuery) -> None:
    name = _display_name(callback.from_user)
    await callback.message.edit_text(
        _reset_confirm_text(name), reply_markup=reset_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "onb:reset:confirm")
async def onboarding_reset_confirm(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)
        await _wipe_onboarding(session, user)
        log.info(
            "[bold yellow]🔄 Onboarding reset confirmed[/bold yellow] user=%s",
            tg_user.id,
        )

    await callback.message.edit_text(
        _welcome_text(name), reply_markup=welcome_keyboard()
    )
    await callback.answer("🔄 Прогресс сброшен")


@router.callback_query(F.data == "onb:reset:cancel")
async def onboarding_reset_cancel(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)

    # Возврат туда, откуда логично пришёл: настройки если онбординг закончен,
    # иначе — в resume/welcome.
    if user.onboarding_completed:
        text, kb = _settings_text(user, name), settings_keyboard()
    else:
        text, kb = _initial_state_screen(user, name)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("↩ Отменено")


@router.callback_query(F.data == "menu:settings")
async def menu_settings(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)

    await callback.message.edit_text(
        _settings_text(user, name), reply_markup=settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:home")
async def menu_home(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = _display_name(tg_user)
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, tg_user)

    await callback.message.edit_text(
        _main_menu_text(user, name), reply_markup=main_menu_keyboard()
    )
    await callback.answer()


_MENU_STUBS: dict[str, tuple[str, str]] = {
    "train": (
        "🎯 Тренировка",
        "Скоро здесь будут адаптивные задачи по SM-2.",
    ),
    "stats": (
        "📊 Статистика",
        "Скоро увидишь свой прогресс, стрики и сильные/слабые темы.",
    ),
    "plan": (
        "🗓 Мой план",
        "Персональное расписание подготовки — уже скоро.",
    ),
    "help": (
        "❓ Помощь",
        "FAQ и связь с автором — в работе.",
    ),
}


@router.callback_query(F.data.startswith("menu:"))
async def main_menu_stub(callback: CallbackQuery) -> None:
    section = callback.data.split(":", 1)[1]
    stub = _MENU_STUBS.get(section)
    if stub is None:
        # menu:settings и menu:home обрабатываются выше; досюда не доходит.
        await callback.answer("В разработке 🚧", show_alert=False)
        return
    title, hint = stub
    await callback.answer(
        f"{title}\n\n{hint}\n\n🚧 В разработке", show_alert=True
    )
