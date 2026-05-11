"""Blueprints для всех 11 предметов ЕГЭ-2025.

Источник: открытые материалы ФИПИ (демоверсии и спецификации). Цифры
`positions_total`, `max_primary_score`, `duration_minutes` — это
общеизвестные параметры; мы их фиксируем как версия "2025".

Поле `slots` пока агрегатное (диапазон позиций → max_score), а не по каждой
позиции 1..N. Это сознательно: точное соответствие позиция-тема-балл = это
работа на отдельный seed, который проще автогенерить из распарсенной
спецификации, чем хардкодить вручную и потом ловить опечатки. API возвращает
агрегированный slots — клиент знает структуру, но не врёт по конкретной
позиции.
"""

from __future__ import annotations

from typing import TypedDict


class Slot(TypedDict, total=False):
    positions: str  # "1-12" или "13"
    part: int  # 1 или 2
    max_score: int
    answer_type: str  # "short" / "extended" / "essay"
    description: str


class Blueprint(TypedDict):
    subject: str
    version: str
    positions_total: int
    max_primary_score: int
    duration_minutes: int
    slots: list[Slot]
    notes: str


# fmt: off
BLUEPRINTS: dict[str, Blueprint] = {
    "math": {
        "subject": "math",
        "version": "2025",
        "positions_total": 19,
        "max_primary_score": 32,
        "duration_minutes": 235,  # 3ч 55мин
        "slots": [
            {"positions": "1-12", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "часть 1: краткий ответ"},
            {"positions": "13", "part": 2, "max_score": 2, "answer_type": "extended",
             "description": "уравнение"},
            {"positions": "14", "part": 2, "max_score": 3, "answer_type": "extended",
             "description": "стереометрия"},
            {"positions": "15", "part": 2, "max_score": 2, "answer_type": "extended",
             "description": "неравенство"},
            {"positions": "16", "part": 2, "max_score": 2, "answer_type": "extended",
             "description": "финансовая/экономическая"},
            {"positions": "17", "part": 2, "max_score": 3, "answer_type": "extended",
             "description": "планиметрия"},
            {"positions": "18", "part": 2, "max_score": 4, "answer_type": "extended",
             "description": "задача с параметром"},
            {"positions": "19", "part": 2, "max_score": 4, "answer_type": "extended",
             "description": "числа и их свойства"},
        ],
        "notes": "Профильная математика. Демоверсия ФИПИ 2025.",
    },
    "russian": {
        "subject": "russian",
        "version": "2025",
        "positions_total": 27,
        "max_primary_score": 50,
        "duration_minutes": 210,
        "slots": [
            {"positions": "1-26", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "часть 1: краткий ответ (отдельные позиции стоят 2-3 балла, см. спецификацию)"},
            {"positions": "27", "part": 2, "max_score": 24, "answer_type": "essay",
             "description": "сочинение по тексту"},
        ],
        "notes": "В части 1 позиции 8 и 26 стоят 2 балла, остальные 1; макс часть 1 = 26, часть 2 = 24, итого 50.",
    },
    "informatics": {
        "subject": "informatics",
        "version": "2025",
        "positions_total": 27,
        "max_primary_score": 30,
        "duration_minutes": 235,
        "slots": [
            {"positions": "1-25", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "часть 1: краткий ответ"},
            {"positions": "26-27", "part": 2, "max_score": 1, "answer_type": "extended",
             "description": "программирование (за каждую — несколько баллов)"},
        ],
        "notes": "Компьютерный формат. Позиции 26 и 27 — программистские задачи (2 и 3 балла).",
    },
    "physics": {
        "subject": "physics",
        "version": "2025",
        "positions_total": 26,
        "max_primary_score": 45,
        "duration_minutes": 235,
        "slots": [
            {"positions": "1-21", "part": 1, "max_score": 2, "answer_type": "short",
             "description": "часть 1: краткий ответ (1-2 балла за позицию)"},
            {"positions": "22-26", "part": 2, "max_score": 4, "answer_type": "extended",
             "description": "часть 2: с развёрнутым решением (3-4 балла)"},
        ],
        "notes": "Часть 2: позиции 22-23 (3 балла), 24-26 (4 балла).",
    },
    "chemistry": {
        "subject": "chemistry",
        "version": "2025",
        "positions_total": 34,
        "max_primary_score": 56,
        "duration_minutes": 210,
        "slots": [
            {"positions": "1-28", "part": 1, "max_score": 2, "answer_type": "short",
             "description": "часть 1: краткий ответ"},
            {"positions": "29-34", "part": 2, "max_score": 5, "answer_type": "extended",
             "description": "часть 2: с развёрнутым решением"},
        ],
        "notes": "",
    },
    "biology": {
        "subject": "biology",
        "version": "2025",
        "positions_total": 28,
        "max_primary_score": 59,
        "duration_minutes": 235,
        "slots": [
            {"positions": "1-22", "part": 1, "max_score": 3, "answer_type": "short",
             "description": "часть 1: краткий ответ (1-3 балла)"},
            {"positions": "23-28", "part": 2, "max_score": 3, "answer_type": "extended",
             "description": "часть 2: с развёрнутым ответом"},
        ],
        "notes": "",
    },
    "history": {
        "subject": "history",
        "version": "2025",
        "positions_total": 21,
        "max_primary_score": 42,
        "duration_minutes": 210,
        "slots": [
            {"positions": "1-16", "part": 1, "max_score": 2, "answer_type": "short",
             "description": "часть 1: краткий ответ"},
            {"positions": "17-21", "part": 2, "max_score": 4, "answer_type": "extended",
             "description": "часть 2: историческое сочинение и задания с развёрнутым ответом"},
        ],
        "notes": "Позиция 20 (историческое сочинение) — до 7 баллов.",
    },
    "social": {
        "subject": "social",
        "version": "2025",
        "positions_total": 25,
        "max_primary_score": 58,
        "duration_minutes": 210,
        "slots": [
            {"positions": "1-16", "part": 1, "max_score": 2, "answer_type": "short",
             "description": "часть 1"},
            {"positions": "17-25", "part": 2, "max_score": 6, "answer_type": "extended",
             "description": "часть 2: развёрнутые ответы и эссе"},
        ],
        "notes": "",
    },
    "english": {
        "subject": "english",
        "version": "2025",
        "positions_total": 38,
        "max_primary_score": 100,
        "duration_minutes": 195,  # письменная часть; устная отдельно 17 мин
        "slots": [
            {"positions": "1-11", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "аудирование"},
            {"positions": "12-18", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "чтение"},
            {"positions": "19-29", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "грамматика и лексика"},
            {"positions": "30-38", "part": 2, "max_score": 14, "answer_type": "extended",
             "description": "письмо + устная часть"},
        ],
        "notes": "Письменная часть + отдельный устный экзамен. Шкала тестового балла нелинейна.",
    },
    "literature": {
        "subject": "literature",
        "version": "2025",
        "positions_total": 12,
        "max_primary_score": 53,
        "duration_minutes": 235,
        "slots": [
            {"positions": "1-7", "part": 1, "max_score": 6, "answer_type": "short",
             "description": "часть 1: вопросы по тексту (1-6 баллов)"},
            {"positions": "8-11", "part": 2, "max_score": 6, "answer_type": "extended",
             "description": "часть 2: краткий развёрнутый ответ"},
            {"positions": "12", "part": 2, "max_score": 18, "answer_type": "essay",
             "description": "сочинение"},
        ],
        "notes": "",
    },
    "geography": {
        "subject": "geography",
        "version": "2025",
        "positions_total": 31,
        "max_primary_score": 43,
        "duration_minutes": 180,
        "slots": [
            {"positions": "1-23", "part": 1, "max_score": 1, "answer_type": "short",
             "description": "часть 1: краткий ответ"},
            {"positions": "24-31", "part": 2, "max_score": 3, "answer_type": "extended",
             "description": "часть 2: с развёрнутым решением"},
        ],
        "notes": "",
    },
}
# fmt: on
