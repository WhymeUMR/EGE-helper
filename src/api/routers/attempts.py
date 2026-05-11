"""Block 5: /api/v1/attempts/* — solving session.

Состояния attempt: in_progress → paused (abandon-light) → in_progress (resume)
                                → submitted (финальный) → abandoned.
Submitted и abandoned терминальны, дальнейшие изменения запрещены.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_session
from api.services.scoring import recompute_scores
from bot.catalog import SUBJECT_KEYS
from bot.db.models import Attempt, AttemptAnswer, Problem, User, Variant

router = APIRouter(prefix="/api/v1/attempts", tags=["attempts"])


# ───────────────────── schemas ─────────────────────


class StartAttemptRequest(BaseModel):
    """Старт по существующему variant_id ИЛИ inline по списку problem_ids
    (создаётся synthetic-вариант)."""

    variant_id: int | None = None
    subject: str | None = None
    problem_ids: list[int] | None = None
    sdamgia_ids: list[str] | None = None  # альтернатива problem_ids
    title: str | None = None
    time_limit_seconds: int | None = Field(default=None, ge=60)

    @model_validator(mode="after")
    def _check(self):
        has_variant = self.variant_id is not None
        has_inline = bool(self.problem_ids) or bool(self.sdamgia_ids)
        if has_variant == has_inline:
            raise ValueError("provide either variant_id OR (problem_ids|sdamgia_ids)+subject")
        if has_inline and self.subject is None:
            raise ValueError("subject is required for inline attempt")
        if has_inline and self.subject not in SUBJECT_KEYS:
            raise ValueError(f"unknown subject: {self.subject}")
        return self


class AnswerOut(BaseModel):
    problem_id: int
    sdamgia_id: str
    answer: str | None
    is_correct: bool | None
    primary_score: int | None
    criteria_scores: dict
    time_spent_seconds: int
    answered_at: datetime | None


class AttemptOut(BaseModel):
    id: int
    user_id: int
    variant_id: int
    subject: str
    status: str
    time_limit_seconds: int | None
    time_spent_seconds: int
    primary_score: int | None
    test_score: int | None
    started_at: datetime
    submitted_at: datetime | None
    problem_ids: list[int]
    answers: list[AnswerOut]


class AttemptPatch(BaseModel):
    time_spent_seconds: int | None = Field(default=None, ge=0)


class SingleAnswerRequest(BaseModel):
    answer: str
    time_spent_seconds: int | None = Field(default=None, ge=0)
    criteria_scores: dict | None = None


class BatchAnswerItem(BaseModel):
    problem_id: int
    answer: str
    time_spent_seconds: int | None = Field(default=None, ge=0)
    criteria_scores: dict | None = None


class BatchAnswerRequest(BaseModel):
    answers: list[BatchAnswerItem]


class ReviewItem(BaseModel):
    position: int
    problem_id: int
    sdamgia_id: str
    user_answer: str | None
    correct_answer: str | None
    is_correct: bool | None
    primary_score: int | None
    max_score: int | None  # пока None — не знаем точную позицию


class ReviewOut(BaseModel):
    attempt_id: int
    primary_score: int | None
    test_score: int | None
    items: list[ReviewItem]


# ───────────────────── helpers ─────────────────────


async def _get_attempt(
    session: AsyncSession, attempt_id: int, user: User
) -> Attempt:
    a = await session.scalar(select(Attempt).where(Attempt.id == attempt_id))
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="attempt not found")
    return a


async def _attempt_to_out(session: AsyncSession, attempt: Attempt) -> AttemptOut:
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    answers_rows = list(
        (await session.execute(
            select(AttemptAnswer, Problem)
            .join(Problem, AttemptAnswer.problem_id == Problem.id)
            .where(AttemptAnswer.attempt_id == attempt.id)
        )).all()
    )
    answers = [
        AnswerOut(
            problem_id=a.problem_id,
            sdamgia_id=p.sdamgia_id,
            answer=a.answer,
            is_correct=a.is_correct,
            primary_score=a.primary_score,
            criteria_scores=dict(a.criteria_scores or {}),
            time_spent_seconds=a.time_spent_seconds,
            answered_at=a.answered_at,
        )
        for (a, p) in answers_rows
    ]
    return AttemptOut(
        id=attempt.id,
        user_id=attempt.user_id,
        variant_id=attempt.variant_id,
        subject=variant.subject if variant else "",
        status=attempt.status,
        time_limit_seconds=attempt.time_limit_seconds,
        time_spent_seconds=attempt.time_spent_seconds,
        primary_score=attempt.primary_score,
        test_score=attempt.test_score,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        problem_ids=list(variant.problem_ids) if variant else [],
        answers=answers,
    )


def _ensure_active(attempt: Attempt) -> None:
    if attempt.status in ("submitted", "abandoned"):
        raise HTTPException(
            status_code=409,
            detail=f"attempt is {attempt.status}, no further changes allowed",
        )


# ───────────────────── start ─────────────────────


@router.post("/start", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
async def start_attempt(
    body: StartAttemptRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    if body.variant_id is not None:
        variant = await session.scalar(
            select(Variant).where(Variant.id == body.variant_id)
        )
        if variant is None:
            raise HTTPException(status_code=404, detail="variant not found")
    else:
        # inline: собираем problems по ids
        if body.problem_ids:
            problems = list(
                (await session.execute(
                    select(Problem).where(Problem.id.in_(body.problem_ids))
                )).scalars()
            )
        else:
            problems = list(
                (await session.execute(
                    select(Problem).where(
                        Problem.subject == body.subject,
                        Problem.sdamgia_id.in_(body.sdamgia_ids or []),
                    )
                )).scalars()
            )
        if not problems:
            raise HTTPException(status_code=404, detail="no problems matched")
        # все problems должны быть из заявленного subject
        wrong = [p for p in problems if p.subject != body.subject]
        if wrong:
            raise HTTPException(
                status_code=422,
                detail=f"problems from other subjects: {[p.sdamgia_id for p in wrong]}",
            )
        # сохраняем порядок: problem_ids — в том порядке, что прислал клиент
        if body.problem_ids:
            order = {pid: i for i, pid in enumerate(body.problem_ids)}
            problems.sort(key=lambda p: order.get(p.id, 0))
        else:
            order_sdam = {sid: i for i, sid in enumerate(body.sdamgia_ids or [])}
            problems.sort(key=lambda p: order_sdam.get(p.sdamgia_id, 0))
        variant = Variant(
            subject=body.subject,
            title=body.title or "Inline attempt",
            problem_ids=[p.id for p in problems],
            kind="synthetic",
            author_id=user.id,
        )
        session.add(variant)
        await session.flush()

    attempt = Attempt(
        user_id=user.id,
        variant_id=variant.id,
        time_limit_seconds=body.time_limit_seconds,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


# ───────────────────── get / patch ─────────────────────


@router.get("/{attempt_id}", response_model=AttemptOut)
async def get_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    return await _attempt_to_out(session, attempt)


@router.patch("/{attempt_id}", response_model=AttemptOut)
async def patch_attempt(
    attempt_id: int,
    body: AttemptPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    _ensure_active(attempt)
    if body.time_spent_seconds is not None:
        attempt.time_spent_seconds = body.time_spent_seconds
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


# ───────────────────── save answers ─────────────────────


async def _upsert_answer(
    session: AsyncSession,
    attempt: Attempt,
    *,
    problem_id: int,
    answer: str,
    time_spent_seconds: int | None,
    criteria_scores: dict | None,
) -> AttemptAnswer:
    existing = await session.scalar(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt.id,
            AttemptAnswer.problem_id == problem_id,
        )
    )
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = AttemptAnswer(
            attempt_id=attempt.id,
            problem_id=problem_id,
            answer=answer,
            time_spent_seconds=time_spent_seconds or 0,
            criteria_scores=criteria_scores or {},
            answered_at=now,
        )
        session.add(existing)
    else:
        existing.answer = answer
        if time_spent_seconds is not None:
            existing.time_spent_seconds = time_spent_seconds
        if criteria_scores is not None:
            existing.criteria_scores = criteria_scores
        existing.answered_at = now
    return existing


@router.post(
    "/{attempt_id}/answer/{problem_id}",
    response_model=AttemptOut,
)
async def save_single_answer(
    attempt_id: int,
    problem_id: int,
    body: SingleAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    _ensure_active(attempt)
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    if variant is None or problem_id not in (variant.problem_ids or []):
        raise HTTPException(
            status_code=422, detail="problem_id not in this attempt's variant"
        )
    await _upsert_answer(
        session, attempt,
        problem_id=problem_id,
        answer=body.answer,
        time_spent_seconds=body.time_spent_seconds,
        criteria_scores=body.criteria_scores,
    )
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


@router.post("/{attempt_id}/answers", response_model=AttemptOut)
async def save_batch_answers(
    attempt_id: int,
    body: BatchAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    _ensure_active(attempt)
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    valid_ids = set(variant.problem_ids or []) if variant else set()
    bad = [a.problem_id for a in body.answers if a.problem_id not in valid_ids]
    if bad:
        raise HTTPException(
            status_code=422, detail=f"problem_ids not in variant: {bad}"
        )
    for item in body.answers:
        await _upsert_answer(
            session, attempt,
            problem_id=item.problem_id,
            answer=item.answer,
            time_spent_seconds=item.time_spent_seconds,
            criteria_scores=item.criteria_scores,
        )
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


# ───────────────────── submit / resume / abandon ─────────────────────


@router.post("/{attempt_id}/submit", response_model=AttemptOut)
async def submit_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    if attempt.status == "submitted":
        # идемпотентно
        return await _attempt_to_out(session, attempt)
    if attempt.status == "abandoned":
        raise HTTPException(status_code=409, detail="attempt was abandoned")
    await recompute_scores(session, attempt)
    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


@router.post("/{attempt_id}/resume", response_model=AttemptOut)
async def resume_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    if attempt.status in ("submitted", "abandoned"):
        raise HTTPException(
            status_code=409, detail=f"cannot resume {attempt.status} attempt"
        )
    attempt.status = "in_progress"
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


@router.post("/{attempt_id}/abandon", response_model=AttemptOut)
async def abandon_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    attempt = await _get_attempt(session, attempt_id, user)
    if attempt.status == "submitted":
        raise HTTPException(status_code=409, detail="attempt already submitted")
    attempt.status = "abandoned"
    await session.commit()
    await session.refresh(attempt)
    return await _attempt_to_out(session, attempt)


# ───────────────────── review / mistakes ─────────────────────


async def _build_review(session: AsyncSession, attempt: Attempt) -> ReviewOut:
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    problem_ids = list(variant.problem_ids) if variant else []
    problems = {
        p.id: p
        for p in (
            await session.execute(select(Problem).where(Problem.id.in_(problem_ids)))
        ).scalars()
    }
    answers = {
        a.problem_id: a
        for a in (
            await session.execute(
                select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
            )
        ).scalars()
    }
    items: list[ReviewItem] = []
    for position, pid in enumerate(problem_ids, start=1):
        problem = problems.get(pid)
        ans = answers.get(pid)
        items.append(
            ReviewItem(
                position=position,
                problem_id=pid,
                sdamgia_id=problem.sdamgia_id if problem else "",
                user_answer=ans.answer if ans else None,
                correct_answer=problem.answer if problem else None,
                is_correct=ans.is_correct if ans else None,
                primary_score=ans.primary_score if ans else None,
                max_score=None,
            )
        )
    return ReviewOut(
        attempt_id=attempt.id,
        primary_score=attempt.primary_score,
        test_score=attempt.test_score,
        items=items,
    )


@router.get("/{attempt_id}/review", response_model=ReviewOut)
async def get_review(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReviewOut:
    attempt = await _get_attempt(session, attempt_id, user)
    return await _build_review(session, attempt)


@router.get("/{attempt_id}/mistakes", response_model=list[ReviewItem])
async def get_mistakes(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ReviewItem]:
    attempt = await _get_attempt(session, attempt_id, user)
    review = await _build_review(session, attempt)
    return [item for item in review.items if item.is_correct is False]
