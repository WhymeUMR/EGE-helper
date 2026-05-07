import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.db.postgres import SessionLocal, check_postgres, engine
from bot.db.redis_client import check_redis, redis_client
from bot.handlers import router
from bot.middlewares import ResourcesMiddleware


async def on_startup() -> None:
    await check_postgres()
    await check_redis()


async def on_shutdown(bot: Bot) -> None:
    await bot.session.close()
    await redis_client.close()
    await engine.dispose()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    dp.update.middleware(ResourcesMiddleware(redis_client, SessionLocal))
    dp.include_router(router)

    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())
