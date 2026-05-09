"""Дата/время: now в МСК, приветствие по времени суток, отсчёт до ЕГЭ"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# единого «дня X» у ФИПИ нет, основная волна обычно во второй половине мая
# 23 — нормальное приближение, юзеру не нужна точность до часа
EGE_MONTH = 5
EGE_DAY = 23

try:
    MOSCOW_TZ: ZoneInfo | None = ZoneInfo("Europe/Moscow")
except ZoneInfoNotFoundError:  # pragma: no cover - на хосте нет tzdata
    MOSCOW_TZ = None


def now_msk() -> datetime:
    """текущее время в МСК; если tzdata нет — берём локальное"""
    return datetime.now(MOSCOW_TZ) if MOSCOW_TZ else datetime.now()


def greeting(name: str) -> str:
    """приветствие по времени суток в МСК: утро / день / вечер / ночь"""
    hour = now_msk().hour
    if 5 <= hour < 12:
        prefix = "☀️ Доброе утро"
    elif 12 <= hour < 17:
        prefix = "🌤 Добрый день"
    elif 17 <= hour < 23:
        prefix = "🌆 Добрый вечер"
    else:
        prefix = "🌙 Доброй ночи"
    return f"{prefix}, <b>{name}</b>!"


def decline_days(n: int) -> str:
    """склонение слова «день»: 1 день, 2 дня, 5 дней"""
    n = abs(int(n))
    # 11-14 особый случай — там всегда «дней», независимо от последней цифры
    if 11 <= n % 100 <= 14:
        return "дней"
    last = n % 10
    if last == 1:
        return "день"
    if 2 <= last <= 4:
        return "дня"
    return "дней"


def days_to_ege(grade: int | None, today: date | None = None) -> int:
    """сколько дней осталось до ЕГЭ конкретного юзера

    11кл сдают в ближайший май, 10кл — ещё через год (они доучиваются)
    grade неизвестен — считаем как 11кл
    """
    today = today or now_msk().date()
    target = date(today.year, EGE_MONTH, EGE_DAY)
    # если в этом году май уже прошёл, целимся в следующий
    if today > target:
        target = date(today.year + 1, EGE_MONTH, EGE_DAY)
    # для 10кл накидываем ещё цикл сверху — они сдают в конце 11
    if grade == 10:
        target = date(target.year + 1, EGE_MONTH, EGE_DAY)
    return (target - today).days
