"""Инлайн-клавиатуры для экранов онбординга

Каждая функция возвращает свежий InlineKeyboardMarkup — кэшировать
нельзя, потому что выбор предметов и текущее значение часов меняют
разметку.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.catalog import MAX_SUBJECTS, MIN_SUBJECTS, SUBJECTS, WEEKLY_HOURS

# стили инлайн-кнопок из Bot API 9.4 (aiogram >= 3.27)
PRIMARY = "primary"
SUCCESS = "success"
DANGER = "danger"


def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Начать подготовку",
                    callback_data="onb:continue",
                    style=PRIMARY,
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ О боте",
                    callback_data="onb:about",
                )
            ],
        ]
    )


def grade_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📘 10 класс", callback_data="onb:grade:10", style=PRIMARY
                ),
                InlineKeyboardButton(
                    text="🎓 11 класс", callback_data="onb:grade:11", style=PRIMARY
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="onb:back_welcome",
                ),
            ],
        ]
    )


def subjects_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    at_max = len(selected) >= MAX_SUBJECTS

    for key, label, emoji in SUBJECTS:
        is_selected = key in selected
        if is_selected:
            mark = "✅"
            style = SUCCESS
        elif at_max:
            # визуально «залочены» — клик всё равно дойдёт, но хендлер
            # откажет тостом, и юзер сразу понимает почему
            mark = "🔒"
            style = None
        else:
            mark = emoji
            style = None
        button = InlineKeyboardButton(
            text=f"{mark} {label}",
            callback_data=f"onb:subject:{key}",
            style=style,
        )
        pair.append(button)
        if len(pair) == 2:
            rows.append(pair)
            pair = []

    if pair:
        rows.append(pair)

    selected_count = len(selected)
    can_finish = selected_count >= MIN_SUBJECTS
    done_text = (
        f"✨ Готово ({selected_count})"
        if can_finish
        else f"🔒 Выбери ещё {MIN_SUBJECTS - selected_count}"
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=done_text,
                callback_data="onb:subjects:done",
                style=SUCCESS if can_finish else None,
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="onb:continue")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hours_keyboard(selected: int | None = None) -> InlineKeyboardMarkup:
    def _cell(h: int, default_emoji: str) -> InlineKeyboardButton:
        is_active = selected == h
        text = f"{'✅' if is_active else default_emoji} {h} ч/нед"
        return InlineKeyboardButton(
            text=text,
            callback_data=f"onb:hours:{h}",
            style=SUCCESS if is_active else PRIMARY,
        )

    rows = [
        [_cell(h, "⏱") for h in WEEKLY_HOURS[:2]],
        [_cell(h, "🔥") for h in WEEKLY_HOURS[2:]],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="onb:back_subjects")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calibration_keyboard(subjects: list[str]) -> InlineKeyboardMarkup:
    labels = {key: (label, emoji) for key, label, emoji in SUBJECTS}
    rows: list[list[InlineKeyboardButton]] = []
    for key in subjects:
        if key not in labels:
            continue
        label, emoji = labels[key]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📝 Пробник: {emoji} {label}",
                    callback_data=f"onb:calib:start:{key}",
                    style=SUCCESS,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data="onb:calib:skip",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="onb:back_hours",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def about_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="onb:back_welcome",
                )
            ]
        ]
    )


def resume_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Продолжить",
                    callback_data="onb:resume:continue",
                    style=PRIMARY,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Начать заново",
                    callback_data="onb:resume:restart",
                )
            ],
        ]
    )
