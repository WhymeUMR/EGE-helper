"""Middleware'ы aiogram'а — прокидывают общие ресурсы в хендлеры"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker


class ResourcesMiddleware(BaseMiddleware):
    """кладёт redis и db_session_factory в data каждого апдейта

    хендлерам не нужно таскать глобальные синглтоны — нужные ресурсы
    прилетают аргументами через DI-механизм aiogram'а
    """

    def __init__(
        self,
        redis: Redis,
        session_factory: async_sessionmaker,
    ) -> None:
        self.redis = redis
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["redis"] = self.redis
        data["db_session_factory"] = self.session_factory
        return await handler(event, data)
