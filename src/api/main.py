"""Entrypoint API-сервиса: FastAPI + uvicorn + составной индекс на старте."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

from api.config import settings
from api.deps import engine
from api.routes import router
from bot.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # составной индекс ускоряет основной сценарий «subject + номер»
    # IF NOT EXISTS — идемпотентно, безопасно держать в startup
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_problems_subject_topic_number "
                "ON problems (subject, topic_number)"
            )
        )
    logger.info("api ready on %s:%d", settings.api_host, settings.api_port)
    yield
    await engine.dispose()


app = FastAPI(
    title="EGE Helper API",
    description="Доступ к каталогу задач СдамГИА из БД EGE Helper.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    setup_logging()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,  # пусть rich-логгер из bot.logging_config рулит
    )


if __name__ == "__main__":
    main()
