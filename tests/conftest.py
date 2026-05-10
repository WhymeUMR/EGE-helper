"""Подсовываем env до импорта Settings — иначе bot.config упадёт на pydantic-валидации."""

from __future__ import annotations

import os

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "ege_helper")
os.environ.setdefault("POSTGRES_USER", "ege_user")
os.environ.setdefault("POSTGRES_PASSWORD", "ege_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
