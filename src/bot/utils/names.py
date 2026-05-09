"""Достаём имя юзера для подстановки в сообщение, не ломая HTML

В никах бывают `<`, `&`, `>`, эмодзи и прочее весёлое. Всё, что идёт
в текст с ParseMode=HTML, обязано прогоняться через safe_name —
иначе разметка просто умрёт.
"""

from __future__ import annotations

from html import escape

from aiogram.types import User as TelegramUser


def safe_name(name: str | None, fallback: str = "друг") -> str:
    """HTML-экранированное имя; если пусто — отдаём fallback"""
    if not name:
        return fallback
    cleaned = name.strip()
    return escape(cleaned) if cleaned else fallback


def display_name(tg_user: TelegramUser | None, fallback: str = "друг") -> str:
    """имя для приветствия прямо из апдейта aiogram'а"""
    if tg_user is None:
        return fallback
    return safe_name(tg_user.first_name, fallback=fallback)
