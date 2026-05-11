"""Счётчики из БД для правой панели TUI."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from bot.db.models import Problem, User


@dataclass(frozen=True)
class Stats:
    total_problems: int
    by_subject: list[tuple[str, int]]
    users: int


def _dsn() -> str:
    # на хосте postgres проброшен на 5433, а в env-конфиге ставит ровно 5432
    # внутри docker-сети. TUI всегда живёт снаружи, переопределяем порт.
    import os
    user = os.environ.get("POSTGRES_USER", "ege_user")
    pw = os.environ.get("POSTGRES_PASSWORD", "ege_password")
    host = os.environ.get("POSTGRES_HOST_TUI", "localhost")
    port = os.environ.get("POSTGRES_PORT_TUI", "5433")
    db = os.environ.get("POSTGRES_DB", "ege_helper")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


async def fetch_stats() -> Stats | None:
    """None если БД не отвечает — TUI просто покажет прочерки."""
    engine = create_async_engine(_dsn(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sf() as s:
            total = await s.scalar(select(func.count()).select_from(Problem)) or 0
            rows = await s.execute(
                select(Problem.subject, func.count(Problem.id))
                .group_by(Problem.subject)
                .order_by(func.count(Problem.id).desc())
            )
            by_subject = [(r[0], r[1]) for r in rows]
            users = await s.scalar(select(func.count()).select_from(User)) or 0
        return Stats(total_problems=total, by_subject=by_subject, users=users)
    except Exception:  # noqa: BLE001
        return None
    finally:
        await engine.dispose()
