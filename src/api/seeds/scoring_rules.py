"""Шкалы перевода первичный→тестовый балл.

ВАЖНО ПРО ВЕРСИОНИРОВАНИЕ ШКАЛ
==============================

Официальные шкалы Рособрнадзора нелинейны (например, в математике 2025 года
от 0 до 5 первичных шкала растёт ~5 баллов на 1 первичный, потом плавно
замедляется). Полный набор официальных шкал — это таблица примерно из 11
предметов × 30-100 строк, источник — приказы Рособрнадзора (публикуются
ежегодно в июле). Хардкодить их без сверки = вводить пользователей в
заблуждение.

Поэтому здесь:
- Для каждого предмета даём ЛИНЕЙНУЮ аппроксимацию (0 → 0, max_primary →
  100, целочисленное округление).
- Версия помечена как `2025-linear-approx`.
- Пороговые баллы (`min_test_score_pass`, `min_test_score_university`) —
  типичные общеизвестные значения (минимум для аттестата / для подачи в вуз).

Когда придёт время — заменяем `2025-linear-approx` на `2025` с реальными
таблицами из приказа Рособрнадзора. Эндпоинт `/scoring-rules` будет отдавать
самую свежую версию.
"""

from __future__ import annotations

from typing import TypedDict

from api.seeds.blueprints import BLUEPRINTS


class ScoringRule(TypedDict):
    subject: str
    version: str
    primary_to_test: dict[str, int]
    min_test_score_pass: int
    min_test_score_university: int | None
    notes: str


# минимальные тестовые баллы (общеизвестные данные ФИПИ-2025)
_MIN_PASS: dict[str, int] = {
    "math": 27,  # для аттестата по математике профильной — фактически 27
    "russian": 24,
    "informatics": 40,
    "physics": 36,
    "chemistry": 36,
    "biology": 36,
    "history": 32,
    "social": 42,
    "english": 22,
    "literature": 32,
    "geography": 37,
}
_MIN_UNIVERSITY: dict[str, int] = {
    "math": 39,
    "russian": 36,
    "informatics": 44,
    "physics": 39,
    "chemistry": 39,
    "biology": 39,
    "history": 35,
    "social": 45,
    "english": 22,
    "literature": 40,
    "geography": 40,
}


def _linear_scale(max_primary: int) -> dict[str, int]:
    """0..max_primary → 0..100, линейно, целочисленно. Ключи — строки (для JSON)."""
    if max_primary <= 0:
        return {"0": 0}
    return {str(i): round(i * 100 / max_primary) for i in range(max_primary + 1)}


def _build() -> dict[str, ScoringRule]:
    out: dict[str, ScoringRule] = {}
    for key, bp in BLUEPRINTS.items():
        out[key] = {
            "subject": key,
            "version": "2025-linear-approx",
            "primary_to_test": _linear_scale(bp["max_primary_score"]),
            "min_test_score_pass": _MIN_PASS[key],
            "min_test_score_university": _MIN_UNIVERSITY.get(key),
            "notes": (
                "Линейная аппроксимация первичный→тестовый. Замени на "
                "официальную шкалу Рособрнадзора-2025 для боевого режима."
            ),
        }
    return out


SCORING_RULES: dict[str, ScoringRule] = _build()
