from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Problem


async def list_subjects_with_stats(session: AsyncSession) -> list[dict]:
    stmt = (
        select(
            Problem.subject,
            func.count(Problem.id).label("problems"),
            func.count(func.distinct(Problem.topic_number)).label("topics"),
        )
        .group_by(Problem.subject)
        .order_by(func.count(Problem.id).desc())
    )
    rows = await session.execute(stmt)
    return [
        {"subject": r.subject, "problems": r.problems, "topics": r.topics}
        for r in rows
    ]


async def list_topics(session: AsyncSession, subject: str) -> list[dict]:
    # один плоский GROUP BY → дерево собираем на python'е (так читабельнее
    # чем jsonb_agg, а быстродействия с индексом хватает с запасом)
    stmt = (
        select(
            Problem.topic_number,
            Problem.topic_name,
            Problem.category_id,
            Problem.category_name,
            func.count(Problem.id).label("count"),
        )
        .where(Problem.subject == subject)
        .group_by(
            Problem.topic_number,
            Problem.topic_name,
            Problem.category_id,
            Problem.category_name,
        )
    )
    rows = (await session.execute(stmt)).all()

    grouped: dict[tuple[str | None, str | None], dict] = {}
    for r in rows:
        key = (r.topic_number, r.topic_name)
        topic = grouped.setdefault(
            key,
            {
                "topic_number": r.topic_number,
                "topic_name": r.topic_name,
                "problems_count": 0,
                "categories": [],
            },
        )
        topic["problems_count"] += r.count
        topic["categories"].append(
            {
                "category_id": r.category_id,
                "category_name": r.category_name,
                "problems_count": r.count,
            }
        )

    # порядок: 1, 2, …, 19, потом Д1..Д19 и прочее в строковом порядке
    def sort_key(t: dict) -> tuple[int, str]:
        n = t["topic_number"] or ""
        if n.isdigit():
            return (0, f"{int(n):03d}")
        return (1, n)

    result = sorted(grouped.values(), key=sort_key)
    for topic in result:
        topic["categories"].sort(key=lambda c: -c["problems_count"])
    return result


async def find_problems(
    session: AsyncSession,
    *,
    subject: str,
    topic_number: str | None = None,
    category_name: str | None = None,
    category_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Problem]]:
    base = select(Problem).where(Problem.subject == subject)
    if topic_number is not None:
        base = base.where(Problem.topic_number == topic_number)
    if category_name is not None:
        base = base.where(Problem.category_name == category_name)
    if category_id is not None:
        base = base.where(Problem.category_id == category_id)

    total = await session.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0

    rows = await session.execute(
        base.order_by(Problem.id).limit(limit).offset(offset)
    )
    return total, list(rows.scalars())


async def random_problem(
    session: AsyncSession,
    *,
    subject: str,
    topic_number: str | None = None,
    category_name: str | None = None,
    category_id: str | None = None,
) -> Problem | None:
    # ORDER BY random() ок на текущих объёмах (<100к); если упрёмся — TABLESAMPLE
    stmt = select(Problem).where(Problem.subject == subject)
    if topic_number is not None:
        stmt = stmt.where(Problem.topic_number == topic_number)
    if category_name is not None:
        stmt = stmt.where(Problem.category_name == category_name)
    if category_id is not None:
        stmt = stmt.where(Problem.category_id == category_id)
    stmt = stmt.order_by(func.random()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_problem_by_id(
    session: AsyncSession, *, subject: str, sdamgia_id: str
) -> Problem | None:
    stmt = select(Problem).where(
        Problem.subject == subject, Problem.sdamgia_id == sdamgia_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()
