"""Сборка текстов сообщений в HTML

Чистые функции: на вход примитивы, User или имя; на выход — готовый HTML
для отправки через aiogram с ParseMode=HTML. Никаких сайд-эффектов и
походов в БД. Если в текст подставляется что-то от юзера — оно должно
быть уже прогнано через safe_name (см. bot.utils.names), иначе разметка
рискует сломаться.
"""

from __future__ import annotations

from bot.catalog import (
    GRADE_LABELS,
    MAX_SUBJECTS,
    MIN_SUBJECTS,
    SUBJECT_EMOJIS,
    SUBJECT_LABELS,
)
from bot.db.models import User
from bot.utils.dates import days_to_ege, decline_days, greeting
from bot.utils.progress import step_header

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

# лейблы шагов онбординга — показываем на resume-экране
STEP_LABELS: dict[str, str] = {
    "subjects": "📚 Предметы",
    "hours": "⏱ Время на подготовку",
    "calibration": "🎯 Пробник",
}


ABOUT_TEXT = (
    "ℹ️ <b>О боте</b>\n"
    f"<i>{DIVIDER}</i>\n\n"
    "<b>EGE Helper</b> — open-source бот для подготовки к ЕГЭ "
    "на основе spaced repetition (<b>SM-2</b>, как в Anki).\n\n"
    "✅ <b>Что уже работает:</b>\n"
    "• 🚀 Онбординг: класс, предметы (3–5), темп\n"
    "• 👤 Профиль с обратным отсчётом до ЕГЭ\n"
    "• ⚙️ Настройки и сброс прогресса (<code>/reset</code>)\n\n"
    "🔧 <b>В разработке:</b>\n"
    "• 🎯 Адаптивные задачи (SM-2)\n"
    "• 📊 Статистика, стрики, слабые темы\n"
    "• 📚 Материалы и шпаргалки\n"
    "• 📝 Полные пробные варианты ЕГЭ\n\n"
    "🔒 <b>Приватность:</b> данные используются только для подбора задач.\n\n"
    "<i>Версия:</i> <code>0.1.0</code>"
)


def welcome_text(name: str) -> str:
    return (
        f"👋 <b>Привет, {name}!</b>\n"
        "Я — твой помощник по подготовке к <b>ЕГЭ</b>.\n"
        f"<i>{DIVIDER}</i>\n\n"
        "Идея простая — учить не «всё подряд», а слабые темы по "
        "алгоритму <b>SM-2</b> (как в Anki).\n\n"
        "Что я буду делать:\n"
        "• 🎯 давать адаптивные задачи под твой уровень\n"
        "• 📊 показывать прогресс по каждой теме\n"
        "• 📅 считать дни до ЕГЭ и держать темп\n"
        "• 🔔 напоминать, чтобы не забросить\n\n"
        f"Сначала соберём профиль — <i>меньше минуты</i>, {name}.\n\n"
        "Готов? 👇"
    )


def grade_text(name: str) -> str:
    return (
        f"{step_header(1, 'Класс', '🎓')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, в каком ты <b>сейчас классе</b>?\n"
        "Это нужно, чтобы я понимал, сколько у нас времени до экзамена "
        "и какие темы уже пройдены в школе. ⏳"
    )


def subjects_text(user: User, name: str) -> str:
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
    elif selected_count >= MIN_SUBJECTS:
        hint = "✅ Можно нажать <b>«Готово»</b>, либо добавить ещё."
    else:
        need = MIN_SUBJECTS - selected_count
        hint = f"⚠️ {name}, выбери ещё <b>{need}</b>, чтобы продолжить."

    return (
        f"{step_header(2, 'Предметы', '📚')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        "Отметь все предметы, которые <b>сдаёшь</b> "
        f"(<b>{MIN_SUBJECTS}–{MAX_SUBJECTS}</b>).\n"
        "Нажми ещё раз, чтобы снять отметку.\n"
        f"{chosen_block}\n"
        f"{hint}"
    )


def hours_text(name: str) -> str:
    return (
        f"{step_header(3, 'Время на подготовку', '⏱')}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, сколько часов в неделю ты готов уделять подготовке?\n"
        "От этого зависит, сколько задач я буду давать в день "
        "(в среднем <b>~17 минут</b> на одну).\n\n"
        "Выбирай честно — лучше 20 часов и стабильно, чем 40 и сорваться. 💪"
    )


def calibration_text(subjects: list[str], name: str) -> str:
    chosen = ", ".join(SUBJECT_LABELS.get(s, s) for s in subjects) or "—"
    return (
        "🎯 <b>Пробник — подбираем уровень</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"<b>Твои предметы:</b> {chosen}\n\n"
        f"{name}, если хочешь, можешь прямо сейчас написать <b>пробник</b> "
        "по одному из выбранных предметов. По его результатам я точнее "
        "настрою сложность задач и план подготовки.\n\n"
        "Если пропустишь — ничего страшного, я разберусь по ходу занятий, "
        "просто это займёт пару недель. ⏳"
    )


def resume_text(step: str, name: str) -> str:
    label = STEP_LABELS.get(step, "—")
    return (
        f"👋 <b>С возвращением, {name}!</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"Ты остановился на шаге <b>{label}</b>.\n"
        "Продолжим с того же места — или начнём заново?"
    )


def settings_text(user: User, name: str) -> str:
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
        f"⏱ <b>Темп:</b> {hours_str}"
    )


def reset_confirm_text(name: str) -> str:
    return (
        "⚠️ <b>Подтверждение</b>\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"{name}, точно хочешь пройти онбординг заново?\n"
        "Класс, предметы и темп будут <b>стёрты</b>, и мы начнём с чистого листа."
    )


def main_menu_text(user: User, name: str) -> str:
    grade = GRADE_LABELS.get(user.grade or -1, "—")
    subjects = user.subjects or []
    if subjects:
        emojis = " ".join(SUBJECT_EMOJIS.get(s, "•") for s in subjects)
        subjects_str = f"{emojis}  <i>({len(subjects)})</i>"
    else:
        subjects_str = "—"
    hours_str = f"{user.weekly_hours} ч/нед" if user.weekly_hours else "—"

    # серия и дневная цель завязаны на трекер тренировок, которого пока нет
    # показываем «—» вместо мок-данных, заполним когда прикрутим SM-2
    streak_str = "—"
    daily_goal_str = "—"

    if user.grade is None:
        days_left_str = "—"
    else:
        days_left = days_to_ege(user.grade)
        days_left_str = f"{days_left} {decline_days(days_left)}"

    return (
        f"{greeting(name)}\n"
        f"<i>{DIVIDER}</i>\n\n"
        f"👤 <b>Класс:</b> {grade}\n"
        f"📚 <b>Предметы:</b> {subjects_str}\n"
        f"⏱ <b>Темп:</b> {hours_str}\n\n"
        f"🔥 <b>Серия:</b> {streak_str}\n"
        f"📅 <b>До ЕГЭ:</b> {days_left_str}\n"
        f"🎯 <b>Цель на сегодня:</b> {daily_goal_str}\n\n"
        "🚀 Что делаем дальше? 👇"
    )
