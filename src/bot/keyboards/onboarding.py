from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SUBJECTS: list[tuple[str, str, str]] = [
    ("math", "Профильная математика", "📐"),
    ("russian", "Русский язык", "📖"),
    ("informatics", "Информатика", "💻"),
    ("physics", "Физика", "🧲"),
    ("chemistry", "Химия", "⚗️"),
    ("biology", "Биология", "🧬"),
    ("history", "История", "🏛"),
    ("social", "Обществознание", "⚖️"),
    ("english", "Английский язык", "🇬🇧"),
    ("literature", "Литература", "📚"),
    ("geography", "География", "🌍"),
]

# Inline button styles introduced in Bot API 9.4 (aiogram >= 3.27).
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
        ]
    )


def subjects_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []

    for key, label, emoji in SUBJECTS:
        is_selected = key in selected
        mark = "✅" if is_selected else emoji
        text = f"{mark} {label}"
        button = InlineKeyboardButton(
            text=text,
            callback_data=f"onb:subject:{key}",
            style=SUCCESS if is_selected else None,
        )
        pair.append(button)
        if len(pair) == 2:
            rows.append(pair)
            pair = []

    if pair:
        rows.append(pair)

    selected_count = len(selected)
    can_finish = selected_count >= 2
    done_text = (
        f"✨ Готово ({selected_count})"
        if can_finish
        else f"🔒 Выбери ещё {2 - selected_count}"
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


WEEKLY_HOURS = [10, 20, 30, 40]


def hours_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"⏱ {h} ч/нед",
                callback_data=f"onb:hours:{h}",
                style=PRIMARY,
            )
            for h in WEEKLY_HOURS[:2]
        ],
        [
            InlineKeyboardButton(
                text=f"🔥 {h} ч/нед",
                callback_data=f"onb:hours:{h}",
                style=PRIMARY,
            )
            for h in WEEKLY_HOURS[2:]
        ],
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Тренировка", callback_data="menu:train", style=SUCCESS
                ),
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="menu:stats", style=PRIMARY
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗓 Мой план", callback_data="menu:plan", style=PRIMARY
                ),
                InlineKeyboardButton(
                    text="⚙️ Настройки", callback_data="menu:settings"
                ),
            ],
            [
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
            ],
        ]
    )


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
