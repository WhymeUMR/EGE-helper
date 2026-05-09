"""Инлайн-клавиатуры пост-онбординга: главное меню, настройки и
подтверждение деструктивного действия — сброса прогресса"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.onboarding import DANGER, PRIMARY, SUCCESS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Решать задачи",
                    callback_data="menu:practice",
                    style=SUCCESS,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="menu:stats",
                    style=PRIMARY,
                ),
                InlineKeyboardButton(
                    text="📚 Материалы",
                    callback_data="menu:materials",
                    style=PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="menu:settings",
                ),
                InlineKeyboardButton(
                    text="📝 Пробный вариант",
                    callback_data="menu:mock",
                    style=PRIMARY,
                ),
            ],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Пройти онбординг заново",
                    callback_data="onb:reset:start",
                    style=DANGER,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В главное меню",
                    callback_data="menu:home",
                )
            ],
        ]
    )


def reset_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, начать заново",
                    callback_data="onb:reset:confirm",
                    style=DANGER,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="↩ Отмена",
                    callback_data="onb:reset:cancel",
                ),
            ],
        ]
    )
