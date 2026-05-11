"""Нормализация и сравнение ответов части 1 ЕГЭ.

ЕГЭ-задачи части 1 ждут ответ в одном из 4 форматов:
- число (целое/десятичное; запятая или точка как разделитель)
- последовательность цифр (например "1234" — для соответствий)
- слово/несколько слов (без учёта регистра)
- строка с допустимыми пробелами

Здесь общая логика — мы НЕ ловим всех нюансов конкретного предмета (это
задача блока 6), но проверяем ответ так как это делает СдамГИА:
1) убираем все пробелы, переводы строк
2) запятая → точка (для чисел)
3) приводим к нижнему регистру
4) числа: 0.5 == 0,5 == .5; 1 == 1.0; 1.50 == 1.5
"""

from __future__ import annotations

import re

_SPACES = re.compile(r"\s+")


def normalize_answer(raw: str | None) -> str:
    """Канонизирует ответ для сравнения. None/пустое → ''."""
    if raw is None:
        return ""
    s = raw.strip()
    if not s:
        return ""
    s = _SPACES.sub("", s)
    s = s.replace(",", ".")
    s = s.lower()
    # числовая нормализация: убираем висячие нули
    if _looks_like_number(s):
        try:
            f = float(s)
            if f.is_integer():
                return str(int(f))
            # уберём trailing zeros: 1.500 → 1.5
            return f"{f:.10f}".rstrip("0").rstrip(".")
        except ValueError:
            pass
    return s


def _looks_like_number(s: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", s))


def answers_equal(user: str | None, correct: str | None) -> bool:
    """True если оба нормализованных ответа равны и непусты."""
    nu = normalize_answer(user)
    nc = normalize_answer(correct)
    if not nu or not nc:
        return False
    if nu == nc:
        return True
    # некоторые задачи допускают альтернативы через | или ; в эталонном ответе
    for alt in re.split(r"[|;]", nc):
        if normalize_answer(alt) == nu:
            return True
    return False
