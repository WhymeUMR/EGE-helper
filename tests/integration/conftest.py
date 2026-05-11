"""Фикстуры для integration-тестов: своя БД ege_helper_test + TRUNCATE перед каждым тестом."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from bot.db.models import Base


def _admin_dsn() -> str:
    user = os.environ.get("POSTGRES_TEST_USER", "ege_user")
    pw = os.environ.get("POSTGRES_TEST_PASSWORD", "ege_password")
    host = os.environ.get("POSTGRES_TEST_HOST", "localhost")
    port = os.environ.get("POSTGRES_TEST_PORT", "5433")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/postgres"


def _test_dsn() -> str:
    user = os.environ.get("POSTGRES_TEST_USER", "ege_user")
    pw = os.environ.get("POSTGRES_TEST_PASSWORD", "ege_password")
    host = os.environ.get("POSTGRES_TEST_HOST", "localhost")
    port = os.environ.get("POSTGRES_TEST_PORT", "5433")
    db = os.environ.get("POSTGRES_TEST_DB", "ege_helper_test")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


_schema_ready = False


@pytest_asyncio.fixture
async def engine():
    # NullPool обязателен: asyncpg привязывает коннекты к loop'у, а pytest-asyncio
    # запускает каждый тест в новом loop'е → иначе ловим `attached to a different loop`
    global _schema_ready
    db_name = os.environ.get("POSTGRES_TEST_DB", "ege_helper_test")

    if not _schema_ready:
        admin_engine = create_async_engine(
            _admin_dsn(), isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with admin_engine.connect() as conn:
                try:
                    await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                except Exception as exc:
                    if "already exists" not in str(exc):
                        raise
        except Exception as exc:
            pytest.skip(f"postgres недоступна для integration: {exc}")
        finally:
            await admin_engine.dispose()

        bootstrap = create_async_engine(_test_dsn(), poolclass=NullPool)
        async with bootstrap.begin() as conn:
            # пересобираем схему с нуля — миграций пока нет, а структура
            # активно эволюционирует, иначе старые БД ловят несовместимость
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_problems_subject_topic_number "
                    "ON problems (subject, topic_number)"
                )
            )
        await bootstrap.dispose()
        _schema_ready = True

    eng = create_async_engine(_test_dsn(), poolclass=NullPool)
    yield eng
    await eng.dispose()


_ALL_TABLES = (
    "attempt_answers",
    "attempts",
    "variants",
    "bookmarks",
    "problem_reports",
    "problems",
    "telegram_link_codes",
    "refresh_tokens",
    "blueprints",
    "scoring_rules",
    "users",
)


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    async with engine.begin() as conn:
        await conn.execute(
            text(f"TRUNCATE TABLE {', '.join(_ALL_TABLES)} RESTART IDENTITY CASCADE")
        )
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as s:
        yield s


@pytest_asyncio.fixture
async def api_client(engine, monkeypatch) -> AsyncClient:
    # подменяем get_session на сессию из тестовой БД, всё остальное в app живёт как в проде
    from api.deps import get_session
    from api.main import app

    sf = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with sf() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
