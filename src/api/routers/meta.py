"""Platform / Infra: health / ready / live / metrics / meta.

В роутер /api/v1/meta/* складываем версию, флаги фич и лимиты системы.
/health, /ready, /live, /metrics монтируются на корне (без префикса).
"""

from __future__ import annotations

import time
from importlib.metadata import PackageNotFoundError, version as pkg_version

from fastapi import APIRouter, Depends, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.deps import get_session
from bot.catalog import (
    MAX_SUBJECTS,
    MIN_SUBJECTS,
    SUBJECT_KEYS,
    WEEKLY_HOURS,
)

# ───────────────────── Prometheus metrics ─────────────────────
# Экспортируем counters/histograms через middleware (в main.py).
# Glob-имена с префиксом ege_ — чтобы выделялись на дашборде.

http_requests_total = Counter(
    "ege_http_requests_total",
    "Total HTTP requests by method/path/status",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "ege_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)


_started_at_monotonic = time.monotonic()


def _app_version() -> str:
    try:
        return pkg_version("ege-helper-bot")
    except PackageNotFoundError:
        return "0.0.0"


# ───────────────────── корневые роуты (без /api/v1) ─────────────────────

infra_router = APIRouter(tags=["meta"])


@infra_router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """Процесс жив. Не проверяет внешние зависимости."""
    return {"status": "alive"}


@infra_router.get("/ready", summary="Readiness probe")
async def ready(session: AsyncSession = Depends(get_session)) -> Response:
    """Готов обслуживать трафик: пингуем postgres."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return Response(
            content=f'{{"status":"not_ready","detail":"db: {exc!s}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )
    return Response(
        content='{"status":"ready"}',
        status_code=200,
        media_type="application/json",
    )


@infra_router.get("/metrics", summary="Prometheus metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ───────────────────── /api/v1/meta/* ─────────────────────

meta_router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


class VersionInfo(BaseModel):
    version: str
    api: str = "v1"
    uptime_seconds: int


class FeaturesInfo(BaseModel):
    auth_email_password: bool
    auth_telegram: bool
    registration_open: bool
    blocks: dict[str, bool]


class LimitsInfo(BaseModel):
    password_min_length: int
    password_max_length: int
    subjects_min: int
    subjects_max: int
    subjects_known: list[str]
    weekly_hours_options: list[int]
    problems_page_max: int
    refresh_token_ttl_days: int
    access_token_ttl_minutes: int
    telegram_link_ttl_minutes: int


@meta_router.get("/version", response_model=VersionInfo)
async def version() -> VersionInfo:
    return VersionInfo(
        version=_app_version(),
        uptime_seconds=int(time.monotonic() - _started_at_monotonic),
    )


@meta_router.get("/features", response_model=FeaturesInfo)
async def features() -> FeaturesInfo:
    """Какие блоки API в этом билде живые. Делаем явно — клиент знает что трогать."""
    return FeaturesInfo(
        auth_email_password=True,
        auth_telegram=True,
        registration_open=settings.registration_open,
        blocks={
            "auth": True,
            "users": True,
            "catalog_meta": True,
            "problems": True,
            "variants": False,  # phase 2
            "attempts": True,
            "checking": True,
            "analytics": False,  # phase 2
            "homework": False,  # phase 2
            "social": False,  # phase 2
            "notifications": False,  # phase 2
            "admin": False,  # phase 2
            "platform": True,
        },
    )


@meta_router.get("/limits", response_model=LimitsInfo)
async def limits() -> LimitsInfo:
    return LimitsInfo(
        password_min_length=8,
        password_max_length=128,
        subjects_min=MIN_SUBJECTS,
        subjects_max=MAX_SUBJECTS,
        subjects_known=sorted(SUBJECT_KEYS),
        weekly_hours_options=list(WEEKLY_HOURS),
        problems_page_max=200,
        refresh_token_ttl_days=settings.jwt_refresh_ttl_days,
        access_token_ttl_minutes=settings.jwt_access_ttl_minutes,
        telegram_link_ttl_minutes=settings.telegram_link_ttl_minutes,
    )
