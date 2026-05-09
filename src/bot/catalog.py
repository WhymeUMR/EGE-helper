"""Каталог продуктовых констант: предметы, классы, лимиты онбординга

Тут источник правды для всего, что про предметы и границы выбора.
Менять состав ЕГЭ-предметов или варианты часов — только в этом файле.
"""

# тут такой же порядок, как потом отрисуется в боте
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

SUBJECT_KEYS: set[str] = {key for key, _, _ in SUBJECTS}
SUBJECT_LABELS: dict[str, str] = {
    key: f"{emoji} {label}" for key, label, emoji in SUBJECTS
}
SUBJECT_EMOJIS: dict[str, str] = {key: emoji for key, _, emoji in SUBJECTS}

# минимум 3: русский, математика и хотя бы один профильный
# меньше — для поступления в нормальный вуз обычно не хватает
MIN_SUBJECTS = 3
# больше пяти — это уже распыление, в UI ловим залоченным «🔒» и тостом
MAX_SUBJECTS = 5

# варианты часов в неделю на шаге темпа
WEEKLY_HOURS: list[int] = [10, 20, 30, 40]
# set чтобы быстро проверить валидность значения из callback_data
WEEKLY_HOURS_SET: set[int] = set(WEEKLY_HOURS)

GRADE_LABELS: dict[int, str] = {
    10: "📘 10 класс",
    11: "🎓 11 класс",
}
