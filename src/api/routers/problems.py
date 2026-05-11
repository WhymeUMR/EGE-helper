"""Block 3: /api/v1/problems/* — list / get / random / search / similar /
check / bookmark / report.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_session
from api.services.answer_check import answers_equal, normalize_answer
from bot.catalog import SUBJECT_KEYS
from bot.db.models import Bookmark, Problem, ProblemReport, User

router = APIRouter(prefix="/api/v1/problems", tags=["problems"])


# ───────────────────── schemas ─────────────────────


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject: str
    sdamgia_id: str
    topic_number: str | None
    topic_name: str | None
    category_id: str | None
    category_name: str | None
    condition_text: str | None
    condition_images: list[str]
    solution_text: str | None
    solution_images: list[str]
    answer: str | None
    analogs: list[str]
    url: str | None
    created_at: datetime
    updated_at: datetime


class ProblemsPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProblemOut]


class SearchRequest(BaseModel):
    """Тяжёлые фильтры идут POST'ом — длиннющие text-запросы и массивы id плохо
    укладываются в querystring."""

    subject: str | None = None
    topic_numbers: list[str] | None = None
    category_ids: list[str] | None = None
    category_names: list[str] | None = None
    text_query: str | None = Field(default=None, description="ILIKE по condition_text")
    has_solution: bool | None = None
    has_answer: bool | None = None
    sdamgia_ids: list[str] | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort: Literal["id", "newest", "oldest"] = "id"


class CheckAnswerRequest(BaseModel):
    answer: str
    time_spent_seconds: int | None = Field(default=None, ge=0)


class CheckAnswerResponse(BaseModel):
    is_correct: bool
    user_answer_normalized: str
    correct_answer_normalized: str | None
    has_correct_answer: bool


class BookmarkOut(BaseModel):
    subject: str
    sdamgia_id: str
    bookmarked_at: datetime


class ReportRequest(BaseModel):
    reason: Literal["wrong_answer", "typo", "broken_image", "duplicate", "other"]
    comment: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    id: int
    subject: str
    sdamgia_id: str
    reason: str
    status: str
    created_at: datetime


# ───────────────────── helpers ─────────────────────


async def _get_problem(session: AsyncSession, subject: str, sdamgia_id: str) -> Problem:
    p = await session.scalar(
        select(Problem).where(Problem.subject == subject, Problem.sdamgia_id == sdamgia_id)
    )
    if p is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return p


def _ensure_subject(subject: str) -> None:
    if subject not in SUBJECT_KEYS:
        raise HTTPException(status_code=404, detail=f"unknown subject: {subject}")


# ───────────────────── list / random / get (порядок имеет значение
# из-за коллизии путей: /random должен быть до /{subject}/{id}) ─────


@router.get("", response_model=ProblemsPage)
async def list_problems(
    subject: str = Query(...),
    topic_number: str | None = None,
    category_name: str | None = None,
    category_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ProblemsPage:
    base = select(Problem).where(Problem.subject == subject)
    if topic_number is not None:
        base = base.where(Problem.topic_number == topic_number)
    if category_name is not None:
        base = base.where(Problem.category_name == category_name)
    if category_id is not None:
        base = base.where(Problem.category_id == category_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await session.execute(base.order_by(Problem.id).limit(limit).offset(offset))
    items = list(rows.scalars())
    return ProblemsPage(
        total=total, limit=limit, offset=offset,
        items=[ProblemOut.model_validate(p) for p in items],
    )


@router.get("/random", response_model=ProblemOut)
async def random_problem(
    subject: str = Query(...),
    topic_number: str | None = None,
    category_name: str | None = None,
    category_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> ProblemOut:
    stmt = select(Problem).where(Problem.subject == subject)
    if topic_number is not None:
        stmt = stmt.where(Problem.topic_number == topic_number)
    if category_name is not None:
        stmt = stmt.where(Problem.category_name == category_name)
    if category_id is not None:
        stmt = stmt.where(Problem.category_id == category_id)
    p = await session.scalar(stmt.order_by(func.random()).limit(1))
    if p is None:
        raise HTTPException(status_code=404, detail="no problems matching filter")
    return ProblemOut.model_validate(p)


@router.post("/search", response_model=ProblemsPage)
async def search_problems(
    body: SearchRequest, session: AsyncSession = Depends(get_session)
) -> ProblemsPage:
    base = select(Problem)
    if body.subject is not None:
        base = base.where(Problem.subject == body.subject)
    if body.topic_numbers:
        base = base.where(Problem.topic_number.in_(body.topic_numbers))
    if body.category_ids:
        base = base.where(Problem.category_id.in_(body.category_ids))
    if body.category_names:
        base = base.where(Problem.category_name.in_(body.category_names))
    if body.sdamgia_ids:
        base = base.where(Problem.sdamgia_id.in_(body.sdamgia_ids))
    if body.text_query:
        # ILIKE по condition_text — медленно на больших БД, но для текущих объёмов ОК.
        # На будущее: pg_trgm индекс или tsvector.
        like = f"%{body.text_query}%"
        base = base.where(
            or_(
                Problem.condition_text.ilike(like),
                Problem.solution_text.ilike(like),
            )
        )
    if body.has_solution is True:
        base = base.where(Problem.solution_text.is_not(None))
    elif body.has_solution is False:
        base = base.where(Problem.solution_text.is_(None))
    if body.has_answer is True:
        base = base.where(Problem.answer.is_not(None))
    elif body.has_answer is False:
        base = base.where(Problem.answer.is_(None))

    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0

    if body.sort == "newest":
        base = base.order_by(Problem.created_at.desc())
    elif body.sort == "oldest":
        base = base.order_by(Problem.created_at.asc())
    else:
        base = base.order_by(Problem.id)

    rows = await session.execute(base.limit(body.limit).offset(body.offset))
    items = list(rows.scalars())
    return ProblemsPage(
        total=total, limit=body.limit, offset=body.offset,
        items=[ProblemOut.model_validate(p) for p in items],
    )


@router.get("/similar/{subject}/{sdamgia_id}", response_model=list[ProblemOut])
async def similar_problems(
    subject: str,
    sdamgia_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[ProblemOut]:
    """Похожие = совпадает (subject, topic_number, category_id или
    category_name). Ранжируем по совпадению категории, потом по id — так
    same-category выпадают первыми, затем same-topic из других категорий.
    """
    pivot = await _get_problem(session, subject, sdamgia_id)

    # сначала пробуем same category
    stmt = (
        select(Problem)
        .where(
            Problem.subject == subject,
            Problem.id != pivot.id,
        )
        .order_by(Problem.id)
    )
    if pivot.category_id is not None:
        same_cat_stmt = stmt.where(Problem.category_id == pivot.category_id).limit(limit)
    elif pivot.topic_number is not None:
        same_cat_stmt = stmt.where(Problem.topic_number == pivot.topic_number).limit(limit)
    else:
        same_cat_stmt = stmt.limit(limit)

    rows = list((await session.execute(same_cat_stmt)).scalars())
    if len(rows) < limit and pivot.topic_number is not None:
        # добираем same-topic из других категорий
        seen_ids = {r.id for r in rows}
        more_stmt = (
            stmt.where(Problem.topic_number == pivot.topic_number)
            .where(~Problem.id.in_(seen_ids | {pivot.id}))
            .limit(limit - len(rows))
        )
        rows.extend(list((await session.execute(more_stmt)).scalars()))
    return [ProblemOut.model_validate(p) for p in rows]


@router.get("/{subject}/{sdamgia_id}", response_model=ProblemOut)
async def get_problem(
    subject: str, sdamgia_id: str, session: AsyncSession = Depends(get_session)
) -> ProblemOut:
    return ProblemOut.model_validate(await _get_problem(session, subject, sdamgia_id))


# ───────────────────── check answer ─────────────────────


@router.post(
    "/{subject}/{sdamgia_id}/check",
    response_model=CheckAnswerResponse,
)
async def check_answer(
    subject: str,
    sdamgia_id: str,
    body: CheckAnswerRequest,
    session: AsyncSession = Depends(get_session),
) -> CheckAnswerResponse:
    """Сверяет пользовательский ответ с эталоном. Не требует auth — чтобы можно
    было использовать в публичной демке. Записи прогресса делаются через
    /attempts/* (аутентифицированные).
    """
    p = await _get_problem(session, subject, sdamgia_id)
    user_norm = normalize_answer(body.answer)
    correct_norm = normalize_answer(p.answer) if p.answer else None
    has_correct = bool(p.answer)
    is_correct = has_correct and answers_equal(body.answer, p.answer)
    return CheckAnswerResponse(
        is_correct=is_correct,
        user_answer_normalized=user_norm,
        correct_answer_normalized=correct_norm,
        has_correct_answer=has_correct,
    )


# ───────────────────── bookmark / unbookmark ─────────────────────


@router.post(
    "/{subject}/{sdamgia_id}/bookmark",
    response_model=BookmarkOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_bookmark(
    subject: str,
    sdamgia_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookmarkOut:
    p = await _get_problem(session, subject, sdamgia_id)
    existing = await session.scalar(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.problem_id == p.id)
    )
    if existing is None:
        existing = Bookmark(user_id=user.id, problem_id=p.id)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
    return BookmarkOut(
        subject=p.subject, sdamgia_id=p.sdamgia_id, bookmarked_at=existing.created_at
    )


@router.delete(
    "/{subject}/{sdamgia_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_bookmark(
    subject: str,
    sdamgia_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    p = await _get_problem(session, subject, sdamgia_id)
    bookmark = await session.scalar(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.problem_id == p.id)
    )
    if bookmark is None:
        raise HTTPException(status_code=404, detail="not bookmarked")
    await session.delete(bookmark)
    await session.commit()
    return None


# ───────────────────── report ─────────────────────


@router.post(
    "/{subject}/{sdamgia_id}/report",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def report_problem(
    subject: str,
    sdamgia_id: str,
    body: ReportRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReportOut:
    p = await _get_problem(session, subject, sdamgia_id)
    report = ProblemReport(
        user_id=user.id, problem_id=p.id, reason=body.reason, comment=body.comment
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return ReportOut(
        id=report.id,
        subject=p.subject,
        sdamgia_id=p.sdamgia_id,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
    )
