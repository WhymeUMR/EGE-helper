"""REST-эндпоинты. Пять штук, документация автоматом по /docs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api import repository as repo
from api.auth import require_token
from api.deps import get_session
from api.schemas import (
    CategoryInfo,
    ProblemOut,
    ProblemsPage,
    SubjectInfo,
    TopicInfo,
)
from bot.catalog import SUBJECT_LABELS

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


@router.get("/subjects", response_model=list[SubjectInfo], tags=["meta"])
async def list_subjects(session: AsyncSession = Depends(get_session)) -> list[SubjectInfo]:
    """Все предметы в БД с количеством задач и номеров заданий."""
    rows = await repo.list_subjects_with_stats(session)
    return [
        SubjectInfo(
            key=r["subject"],
            label=SUBJECT_LABELS.get(r["subject"], r["subject"]),
            problems_count=r["problems"],
            topics_count=r["topics"],
        )
        for r in rows
    ]


@router.get("/topics", response_model=list[TopicInfo], tags=["meta"])
async def list_topics(
    subject: str = Query(..., description="ключ предмета: math, russian, ..."),
    session: AsyncSession = Depends(get_session),
) -> list[TopicInfo]:
    """Структура предмета: какие номера заданий есть и какие типы внутри каждого."""
    topics = await repo.list_topics(session, subject)
    return [
        TopicInfo(
            topic_number=t["topic_number"],
            topic_name=t["topic_name"],
            problems_count=t["problems_count"],
            categories=[CategoryInfo(**c) for c in t["categories"]],
        )
        for t in topics
    ]


@router.get("/problems", response_model=ProblemsPage, tags=["problems"])
async def list_problems(
    subject: str = Query(...),
    topic_number: str | None = Query(default=None, description="например '7' или 'Д8 C1'"),
    category_name: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ProblemsPage:
    """Постраничный список задач под фильтр."""
    total, items = await repo.find_problems(
        session,
        subject=subject,
        topic_number=topic_number,
        category_name=category_name,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return ProblemsPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[ProblemOut.model_validate(p) for p in items],
    )


@router.get("/problems/random", response_model=ProblemOut, tags=["problems"])
async def random_problem(
    subject: str = Query(...),
    topic_number: str | None = Query(default=None),
    category_name: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProblemOut:
    """Одна случайная задача под фильтр — для бота-тренажёра."""
    problem = await repo.random_problem(
        session,
        subject=subject,
        topic_number=topic_number,
        category_name=category_name,
        category_id=category_id,
    )
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no problems matching filter",
        )
    return ProblemOut.model_validate(problem)


@router.get(
    "/problems/{subject}/{sdamgia_id}",
    response_model=ProblemOut,
    tags=["problems"],
)
async def get_problem(
    subject: str,
    sdamgia_id: str,
    session: AsyncSession = Depends(get_session),
) -> ProblemOut:
    """Одна задача по составному ключу `(subject, sdamgia_id)`."""
    problem = await repo.get_problem_by_id(
        session, subject=subject, sdamgia_id=sdamgia_id
    )
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ProblemOut.model_validate(problem)
