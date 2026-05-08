import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.db.postgres import SessionLocal, check_postgres, engine
from bot.db.redis_client import check_redis, redis_client
from bot.handlers import router
from bot.logging_config import setup_logging
from bot.middlewares import ResourcesMiddleware

log = logging.getLogger("bot")


async def on_startup(bot: Bot) -> None:
    log.info("[bold cyan]🚀 Starting EGE-helper bot...[/bold cyan]")
    log.info("[yellow]🔌 Checking PostgreSQL...[/yellow]")
    await check_postgres()
    log.info("[green]✅ PostgreSQL is up[/green]")

    log.info("[yellow]🔌 Checking Redis...[/yellow]")
    await check_redis()
    log.info("[green]✅ Redis is up[/green]")

    me = await bot.get_me()
    log.info(
        "[bold green]🤖 Bot is ready:[/bold green] "
        f"[bold]@{me.username}[/bold] "
        f"([dim]id={me.id}[/dim])"
    )


async def on_shutdown(bot: Bot) -> None:
    log.info("[bold magenta]🛑 Shutting down...[/bold magenta]")
    await bot.session.close()
    await redis_client.close()
    await engine.dispose()
    log.info("[dim]👋 Bye[/dim]")


async def main() -> None:
    setup_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(ResourcesMiddleware(redis_client, SessionLocal))
    dp.include_router(router)

    await on_startup(bot)
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())
