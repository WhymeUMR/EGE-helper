"""Entrypoint API: FastAPI + uvicorn."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from starlette.responses import Response

from api.config import settings
from api.deps import engine
from api.routers.attempts import router as attempts_router
from api.routers.auth import router as auth_router
from api.routers.catalog import router as catalog_router
from api.routers.checking import router as checking_router
from api.routers.me import router as me_router
from api.routers.meta import (
    http_request_duration_seconds,
    http_requests_total,
    infra_router,
    meta_router,
)
from api.routers.problems import router as problems_router
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


# ───────────────────── OpenAPI tags ─────────────────────
# Один источник правды для swagger: порядок групп, описания, ссылки.
# В каждом роуте tag совпадает с tag.name.

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": (
            "Аутентификация. Email + пароль с bcrypt, JWT (access+refresh) "
            "с rotating refresh-токенами. В БД хранится только sha256-хеш "
            "refresh-токена."
        ),
    },
    {
        "name": "me",
        "description": (
            "Профиль текущего пользователя: онбординг, настройки, soft-delete, "
            "линковка Telegram через одноразовый код."
        ),
    },
    {
        "name": "catalog",
        "description": (
            "Метаданные предметов ЕГЭ: blueprints (структура варианта), "
            "topic-map (темы по реальным задачам в БД), difficulty-scale "
            "и scoring-rules (шкала первичный→тестовый)."
        ),
    },
    {
        "name": "problems",
        "description": (
            "Каталог задач: список/фильтры, поиск, похожие, проверка "
            "ответа, закладки, репорты на ошибки в условии."
        ),
    },
    {
        "name": "attempts",
        "description": (
            "Сессия решения варианта: создание (по variant_id или inline "
            "из problem_ids), сохранение ответов, submit/resume/abandon, "
            "review с разбором, список ошибок."
        ),
    },
    {
        "name": "checking",
        "description": (
            "Нормализация и проверка ответов: pure-функции для пары "
            "ответ/эталон + endpoints поверх attempt — recheck, текущий "
            "счёт, критерии, первичный/тестовый балл."
        ),
    },
    {
        "name": "meta",
        "description": (
            "Платформа и health-чеки: /health, /live, /ready, "
            "/metrics (Prometheus), /api/v1/meta/{version,features,limits}."
        ),
    },
]


app = FastAPI(
    title="EGE Helper API",
    description=(
        "REST API платформы **EGE Helper** — подготовка к ЕГЭ.\n\n"
        "**Авторизация**: большинство эндпоинтов защищены JWT. Получи "
        "пару токенов через `POST /api/v1/auth/register` или "
        "`/auth/login`, затем нажми **Authorize** в правом верхнем углу "
        "и вставь `access_token`.\n\n"
        "Полный список реализованных эндпоинтов и статус по блокам — "
        "в README репозитория."
    ),
    version="0.2.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "none",
        "filter": True,
    },
)


def _custom_openapi():
    """Добавляем глобальную BearerAuth схему чтобы в /docs была кнопка
    'Authorize'. На сами роуты security не вешаем — у нас mix авторизации
    (open/optional/required) и FastAPI выводит её через Depends."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerAuth"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Вставь access_token из /auth/login без префикса 'Bearer'.",
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


@app.middleware("http")
async def _prometheus_middleware(request: Request, call_next) -> Response:
    """Считаем все запросы; путь нормализуется до route.path чтобы не плодить
    кардинальность из {variant_id}/{problem_id}."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
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
