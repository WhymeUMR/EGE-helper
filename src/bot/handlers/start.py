from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import User
from bot.keyboards.onboarding import (
    SUBJECTS,
    about_back_keyboard,
    calibration_keyboard,
    grade_keyboard,
    hours_keyboard,
    main_menu_keyboard,
    subjects_keyboard,
    welcome_keyboard,
)

router = Router()
log = logging.getLogger("bot.handlers")

SUBJECT_KEYS = {key for key, _, _ in SUBJECTS}
SUBJECT_LABELS = {key: f"{emoji} {label}" for key, label, emoji in SUBJECTS}

GRADE_LABELS = {
    10: "📘 10 класс",
    11: "🎓 11 класс",
}

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


WELCOME_TEXT = (
    "👋 <b>Привет!</b> Я — твой персональный помощник по подготовке к <b>ЕГЭ</b>.\n"
    f"<i>{DIVIDER}</i>\n\n"
    "Вот что я умею:\n"
    "• 🎯 <b>Тренировки</b> по реальным заданиям ФИПИ\n"
    "• 📊 <b>Статистика</b> и аналитика твоего прогресса\n"
    "• 🗓 <b>Персональный план</b> подготовки\n"
    "• 🔔 <b>Напоминания</b>, чтобы не забросить\n\n"
    "Сначала пройдём короткий <b>онбординг</b> — это займёт <i>меньше минуты</i> "
    "и поможет мне подобрать материалы именно под тебя.\n\n"
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

GRADE_TEXT = (
    "🎓 <b>Шаг 1 из 3 — Класс</b>\n"
    f"<i>{DIVIDER}</i>\n\n"
    "В каком ты <b>сейчас классе</b>?\n"
    "Это нужно, чтобы я понимал, сколько у нас времени до экзамена "
    "и какие темы уже пройдены в школе. ⏳"
)

HOURS_TEXT = (
    "⏱ <b>Шаг 3 из 3 — Время на подготовку</b>\n"
    f"<i>{DIVIDER}</i>\n\n"
    "Сколько часов в неделю ты готов уделять подготовке?\n"
    "От этого зависит, сколько задач я буду давать в день "
    "(в среднем <b>~17 минут</b> на одну).\n\n"
    "Выбирай честно — лучше 20 часов и стабильно, чем 40 и сорваться. 💪"
)


def _calibration_text(subjects: list[str]) -> str:
    chosen = ", ".join(SUBJECT_LABELS.get(s, s) for s in subjects) or "—"
    return (
        "🎯 <b>Пробник — подбираем уровень</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"Твои предметы: {chosen}\n\n"
        "Если хочешь, можешь прямо сейчас написать <b>пробник</b> по "
        "одному из выбранных предметов. По его результатам я точнее настрою "
        "сложность задач и план подготовки.\n\n"
        "Если пропустишь — ничего страшного, я разберусь по ходу занятий, "
        "просто это займёт пару недель. ⏳\n\n"
        "<i>⚠️ Пока пробник в разработке — кнопки ниже зарезервированы, "
        "но дадут результат после ближайшего апдейта.</i>"
    )


def _subjects_text(user: User) -> str:
    selected = list(user.subjects or [])
    selected_count = len(selected)

    if selected:
        chosen = "\n".join(f"  • {SUBJECT_LABELS.get(s, s)}" for s in selected)
        chosen_block = f"\n<b>Выбрано:</b>\n{chosen}\n"
    else:
        chosen_block = "\n<i>Пока ничего не выбрано.</i>\n"

    if selected_count >= 2:
        hint = "✅ Можно нажать <b>«Готово»</b>, либо добавить ещё."
    else:
        need = 2 - selected_count
        hint = f"⚠️ Выбери ещё <b>{need}</b>, чтобы продолжить."

    return (
        "📚 <b>Шаг 2 из 3 — Предметы</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        "Отметь все предметы, которые <b>сдаёшь</b> "
        "(минимум <b>2</b>).\n"
        "Нажми ещё раз, чтобы снять отметку.\n"
        f"{chosen_block}\n"
        f"{hint}"
    )


def _main_menu_text(user: User) -> str:
    grade = GRADE_LABELS.get(user.grade or -1, "—")
    subjects = user.subjects or []
    subjects_str = (
        ", ".join(SUBJECT_LABELS.get(s, s) for s in subjects) if subjects else "—"
    )
    hours_str = f"{user.weekly_hours} ч/нед" if user.weekly_hours else "—"
    return (
        "🏠 <b>Главное меню</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"👤 <b>Класс:</b> {grade}\n"
        f"📚 <b>Предметы:</b> {subjects_str}\n"
        f"⏱ <b>Темп:</b> {hours_str}\n\n"
        "Выбери, что делаем дальше 👇"
    )


async def _get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(telegram_id=telegram_id, subjects=[])
    session.add(user)
    await session.commit()
    await session.refresh(user)
    log.info("[green]👤 New user created:[/green] [bold]%s[/bold]", telegram_id)
    return user


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    redis: Redis,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = message.from_user.id
    key = f"user:{user_id}:starts"

    # Track daily /start hits per user; reset every 24h.
    starts_count = await redis.incr(key)
    if starts_count == 1:
        await redis.expire(key, 60 * 60 * 24)

    log.info(
        "[cyan]/start[/cyan] from [bold]%s[/bold] (@%s) — starts today: %s",
        user_id,
        message.from_user.username or "—",
        starts_count,
    )

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, user_id)

    if user.onboarding_completed:
        await message.answer(_main_menu_text(user), reply_markup=main_menu_keyboard())
        return

    await message.answer(WELCOME_TEXT, reply_markup=welcome_keyboard())


@router.callback_query(F.data == "onb:about")
async def onboarding_about(callback: CallbackQuery) -> None:
    await callback.message.edit_text(ABOUT_TEXT, reply_markup=about_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "onb:back_welcome")
async def onboarding_back_welcome(callback: CallbackQuery) -> None:
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=welcome_keyboard())
    await callback.answer()


@router.callback_query(F.data == "onb:continue")
async def onboarding_continue(callback: CallbackQuery) -> None:
    await callback.message.edit_text(GRADE_TEXT, reply_markup=grade_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("onb:grade:"))
async def onboarding_grade(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    grade = int(callback.data.split(":")[-1])
    telegram_id = callback.from_user.id

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, telegram_id)
        user.grade = grade
        await session.commit()
        await session.refresh(user)

        await callback.message.edit_text(
            _subjects_text(user),
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

    telegram_id = callback.from_user.id

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, telegram_id)
        selected = set(user.subjects or [])

        if subject in selected:
            selected.remove(subject)
            toast = f"➖ {SUBJECT_LABELS[subject]}"
        else:
            selected.add(subject)
            toast = f"➕ {SUBJECT_LABELS[subject]}"

        user.subjects = sorted(selected)
        await session.commit()

        await callback.message.edit_text(
            _subjects_text(user),
            reply_markup=subjects_keyboard(set(user.subjects)),
        )

    await callback.answer(toast)


@router.callback_query(F.data == "onb:subjects:done")
async def onboarding_subjects_done(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    telegram_id = callback.from_user.id

    async with db_session_factory() as session:
        user = await _get_or_create_user(session, telegram_id)
        if len(set(user.subjects or [])) < 2:
            await callback.answer(
                "⚠️ Нужно выбрать минимум 2 предмета", show_alert=True
            )
            return

    await callback.message.edit_text(HOURS_TEXT, reply_markup=hours_keyboard())
    await callback.answer()


@router.callback_query(F.data == "onb:back_subjects")
async def onboarding_back_subjects(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, callback.from_user.id)
        await callback.message.edit_text(
            _subjects_text(user),
            reply_markup=subjects_keyboard(set(user.subjects or [])),
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

    telegram_id = callback.from_user.id
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, telegram_id)
        user.weekly_hours = hours
        await session.commit()
        await session.refresh(user)
        subjects = list(user.subjects or [])

    await callback.message.edit_text(
        _calibration_text(subjects),
        reply_markup=calibration_keyboard(subjects),
    )
    await callback.answer(f"⏱ {hours} ч/нед")


async def _finalize_onboarding(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    telegram_id = callback.from_user.id
    async with db_session_factory() as session:
        user = await _get_or_create_user(session, telegram_id)
        user.onboarding_completed = True
        await session.commit()
        await session.refresh(user)

    log.info(
        "[bold green]🎉 Onboarding finished[/bold green] for [bold]%s[/bold]",
        telegram_id,
    )
    await callback.message.edit_text(
        _main_menu_text(user), reply_markup=main_menu_keyboard()
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


@router.callback_query(F.data.startswith("menu:"))
async def main_menu_stub(callback: CallbackQuery) -> None:
    section = callback.data.split(":", 1)[1]
    titles = {
        "train": "🎯 Тренировка",
        "stats": "📊 Статистика",
        "plan": "🗓 Мой план",
        "settings": "⚙️ Настройки",
        "help": "❓ Помощь",
    }
    title = titles.get(section, section)
    await callback.answer(f"{title} — скоро 🚧", show_alert=False)
