"""Композиция экранов: из состояния юзера достаём пару (текст, клавиатура)

Слой над texts и keyboards — склеивает их по тому, как далеко юзер
продвинулся в онбординге. Используется в /start, в кнопке «Продолжить»
на resume-экране и в «Отмене» при сбросе.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from bot.db.models import User
from bot.keyboards.menu import main_menu_keyboard
from bot.keyboards.onboarding import (
    calibration_keyboard,
    hours_keyboard,
    resume_keyboard,
    subjects_keyboard,
    welcome_keyboard,
)
from bot.services.users import onboarding_step_for
from bot.texts import (
    calibration_text,
    hours_text,
    main_menu_text,
    resume_text,
    subjects_text,
    welcome_text,
)


def step_screen(user: User, name: str) -> tuple[str, InlineKeyboardMarkup]:
    """(текст, клавиатура) для текущего шага онбординга

    нужно когда хочется нырнуть прямо внутрь шага — например после клика
    «Продолжить» на resume-экране
    """
    step = onboarding_step_for(user)
    if step == "subjects":
        return (
            subjects_text(user, name),
            subjects_keyboard(set(user.subjects or [])),
        )
    if step == "hours":
        return hours_text(name), hours_keyboard(selected=user.weekly_hours)
    if step == "calibration":
        subjects = list(user.subjects or [])
        return calibration_text(subjects, name), calibration_keyboard(subjects)
    return welcome_text(name), welcome_keyboard()


def initial_state_screen(
    user: User, name: str
) -> tuple[str, InlineKeyboardMarkup]:
    """стартовый экран по сохранённому состоянию юзера

    - онбординг закончен → главное меню
    - прогресс есть, но не закончен → resume-экран (Продолжить / Начать заново)
    - ничего нет → классический welcome
    """
    if user.onboarding_completed:
        return main_menu_text(user, name), main_menu_keyboard()
    step = onboarding_step_for(user)
    if step == "welcome":
        return welcome_text(name), welcome_keyboard()
    return resume_text(step, name), resume_keyboard()
