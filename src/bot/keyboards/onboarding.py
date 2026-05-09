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

# Минимум: рус + математика + 1 профильный — это база ЕГЭ для поступления.
# Меньше 3-х предметов по факту = недосбор для большинства вузов.
MIN_SUBJECTS = 3
# Реалистичный потолок: больше 5 предметов разом — это уже не подготовка,
# а распыление. Кап мягкий: пользователь видит «🔒» и поясняющий тост.
MAX_SUBJECTS = 5

WEEKLY_HOURS = [10, 20, 30, 40]


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
            # Визуально «залочены» — клик всё равно отработает, но
            # хендлер откажет с тостом, и юзер сразу понимает почему.
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
