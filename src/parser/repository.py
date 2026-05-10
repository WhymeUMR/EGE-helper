"""DB-операции для problems: что уже есть и как добавить новое."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Problem


async def get_existing_ids(session: AsyncSession, subject: str) -> set[str]:
    """Список sdamgia_id для предмета — чтобы не качать карточки повторно."""
    rows = await session.execute(
        select(Problem.sdamgia_id).where(Problem.subject == subject)
    )
    return {row[0] for row in rows}


async def insert_problem(session: AsyncSession, payload: dict[str, Any]) -> bool:
    """True если вставили, False если уже было.

    ON CONFLICT DO NOTHING вместо merge — надёжнее на гонках, и сразу
    отдаёт правильный счётчик новых записей.
    """
    stmt = (
        pg_insert(Problem)
        .values(**payload)
        .on_conflict_do_nothing(index_elements=["subject", "sdamgia_id"])
        .returning(Problem.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
