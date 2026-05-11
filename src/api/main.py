"""Entrypoint API: FastAPI + uvicorn."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy import text
from starlette.responses import Response

from api.config import settings
from api.deps import engine
from api.routers.attempts import router as attempts_router
from api.routers.auth import router as auth_router
from api.routers.catalog import router as catalog_router
from api.routers.checking import router as checking_router
from api.routers.me import router as me_router
from api.routers.problems import router as problems_router
from api.routers.meta import (
    http_request_duration_seconds,
    http_requests_total,
    infra_router,
    meta_router,
)
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


@app.middleware("http")
async def _prometheus_middleware(request: Request, call_next) -> Response:
    """Считаем все запросы; путь нормализуется до route.path чтобы не плодить
    кардинальность из {variant_id}/{problem_id}."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    # route может быть None для 404 на ненайденных путях
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    http_requests_total.labels(
        method=request.method, path=path, status=str(response.status_code)
    ).inc()
    http_request_duration_seconds.labels(method=request.method, path=path).observe(elapsed)
    return response


app.include_router(infra_router)
app.include_router(meta_router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(catalog_router)
app.include_router(problems_router)
app.include_router(attempts_router)
app.include_router(checking_router)
app.include_router(legacy_router)


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
