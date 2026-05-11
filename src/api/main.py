"""Entrypoint API: FastAPI + uvicorn."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

from api.config import settings
from api.deps import engine
from api.routers.auth import router as auth_router
from api.routers.me import router as me_router
from api.routes import router as legacy_router
from bot.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    description="REST API платформы EGE Helper.",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(legacy_router)  # старые /api/v1/{subjects,topics,problems,problems/*}


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    setup_logging()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
