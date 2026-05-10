"""Entrypoint parser-сервиса: схема → seed → первый прогон → APScheduler."""

from __future__ import annotations

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.models import Base
from bot.logging_config import setup_logging
from parser.config import settings
from parser.seed import import_if_empty
from parser.service import run_once

logger = logging.getLogger(__name__)


async def _init_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _run_safely(session_factory: async_sessionmaker) -> None:
    # упавший прогон не должен ронять scheduler
    try:
        await run_once(session_factory)
    except Exception:  # noqa: BLE001
        logger.exception("parser run failed")


async def amain() -> None:
    setup_logging()
    logger.info("parser service starting")

    engine = create_async_engine(settings.postgres_dsn, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    await _init_schema(engine)

    # сначала seed (если есть и БД пустая) — потом парсер уже доливает свежее
    await import_if_empty(session_factory, settings)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_safely,
        trigger="interval",
        hours=settings.parser_interval_hours,
        args=[session_factory],
        id="parse-sdamgia",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    if settings.parser_run_on_startup:
        await _run_safely(session_factory)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info(
        "parser idle; next run in %s hours", settings.parser_interval_hours
    )
    await stop_event.wait()

    logger.info("parser service stopping")
    scheduler.shutdown(wait=False)
    await engine.dispose()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
