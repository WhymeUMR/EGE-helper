"""Block 6: /api/v1/checking/* — нормализация, проверка, recheck, score,
critaria, primary/test points.

Часть 1 проверяется автоматически по answer; часть 2 (developed answer)
оценивается через criteria_scores в каждом AttemptAnswer (заполняется
вручную клиентом или экспертом). Эти эндпоинты — view + триггер пересчёта.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_session
from api.seeds.scoring_rules import SCORING_RULES
from api.services.answer_check import answers_equal, normalize_answer
from api.services.scoring import recompute_scores
from bot.db.models import Attempt, AttemptAnswer, Problem, User, Variant

router = APIRouter(prefix="/api/v1/checking", tags=["checking"])


# ───────────────────── /answers ─────────────────────


class ValidateRequest(BaseModel):
    answer: str
    expected_format: str | None = Field(
        default=None,
        description="число / последовательность / строка. Сейчас игнорится — нормализатор универсальный.",
    )


class ValidateResponse(BaseModel):
    raw: str
    normalized: str
    looks_numeric: bool
    is_empty: bool


@router.post("/answers/validate", response_model=ValidateResponse)
async def validate_answer(body: ValidateRequest) -> ValidateResponse:
    n = normalize_answer(body.answer)
    looks_numeric = bool(n) and all(c in "0123456789.-" for c in n) and any(c.isdigit() for c in n)
    return ValidateResponse(
        raw=body.answer,
        normalized=n,
        looks_numeric=looks_numeric,
        is_empty=not n,
    )


class CheckRequest(BaseModel):
    """Проверка пары ответов вне контекста задачи."""

    user_answer: str
    correct_answer: str


class CheckResponse(BaseModel):
    is_correct: bool
    user_normalized: str
    correct_normalized: str


@router.post("/answers/check", response_model=CheckResponse)
async def check_answers(body: CheckRequest) -> CheckResponse:
    return CheckResponse(
        is_correct=answers_equal(body.user_answer, body.correct_answer),
        user_normalized=normalize_answer(body.user_answer),
        correct_normalized=normalize_answer(body.correct_answer),
    )


# ───────────────────── /attempts/{id}/* ─────────────────────


async def _get_owned_attempt(
    session: AsyncSession, attempt_id: int, user: User
) -> Attempt:
    a = await session.scalar(select(Attempt).where(Attempt.id == attempt_id))
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="attempt not found")
    return a


class RecheckResponse(BaseModel):
    attempt_id: int
    primary_score: int | None
    test_score: int | None


@router.post("/attempts/{attempt_id}/recheck", response_model=RecheckResponse)
async def recheck_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecheckResponse:
    attempt = await _get_owned_attempt(session, attempt_id, user)
    await recompute_scores(session, attempt)
    await session.commit()
    await session.refresh(attempt)
    return RecheckResponse(
        attempt_id=attempt.id,
        primary_score=attempt.primary_score,
        test_score=attempt.test_score,
    )


class ScoreOut(BaseModel):
    attempt_id: int
    status: str
    primary_score: int | None
    test_score: int | None
    max_primary_score: int | None
    answered_count: int
    correct_count: int
    incorrect_count: int


@router.get("/attempts/{attempt_id}/score", response_model=ScoreOut)
async def get_score(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScoreOut:
    attempt = await _get_owned_attempt(session, attempt_id, user)
    answers = list(
        (await session.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
        )).scalars()
    )
    answered = sum(1 for a in answers if a.answer is not None)
    correct = sum(1 for a in answers if a.is_correct is True)
    incorrect = sum(1 for a in answers if a.is_correct is False)

    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    max_primary = None
    if variant is not None:
        rule = SCORING_RULES.get(variant.subject)
        if rule is not None:
            max_primary = max(int(k) for k in rule["primary_to_test"].keys())

    return ScoreOut(
        attempt_id=attempt.id,
        status=attempt.status,
        primary_score=attempt.primary_score,
        test_score=attempt.test_score,
        max_primary_score=max_primary,
        answered_count=answered,
        correct_count=correct,
        incorrect_count=incorrect,
    )


class CriteriaItem(BaseModel):
    problem_id: int
    sdamgia_id: str
    has_extended_answer: bool
    criteria_scores: dict
    primary_score: int | None


class CriteriaOut(BaseModel):
    attempt_id: int
    items: list[CriteriaItem]


@router.get("/attempts/{attempt_id}/criteria", response_model=CriteriaOut)
async def get_criteria(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CriteriaOut:
    attempt = await _get_owned_attempt(session, attempt_id, user)
    rows = list(
        (await session.execute(
            select(AttemptAnswer, Problem)
            .join(Problem, AttemptAnswer.problem_id == Problem.id)
            .where(AttemptAnswer.attempt_id == attempt.id)
        )).all()
    )
    items = [
        CriteriaItem(
            problem_id=a.problem_id,
            sdamgia_id=p.sdamgia_id,
            # эвристика: если у задачи нет answer'а или solution_text есть —
            # это часть 2 / задача с развёрнутым ответом
            has_extended_answer=(p.answer is None or bool(p.solution_text)),
            criteria_scores=dict(a.criteria_scores or {}),
            primary_score=a.primary_score,
        )
        for (a, p) in rows
    ]
    return CriteriaOut(attempt_id=attempt.id, items=items)


class PrimaryPointsOut(BaseModel):
    attempt_id: int
    primary_score: int | None
    max_primary_score: int | None
    breakdown: list[dict]


@router.get("/attempts/{attempt_id}/primary-points", response_model=PrimaryPointsOut)
async def primary_points(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PrimaryPointsOut:
    attempt = await _get_owned_attempt(session, attempt_id, user)
    rows = list(
        (await session.execute(
            select(AttemptAnswer, Problem)
            .join(Problem, AttemptAnswer.problem_id == Problem.id)
            .where(AttemptAnswer.attempt_id == attempt.id)
        )).all()
    )
    breakdown = [
        {
            "problem_id": a.problem_id,
            "sdamgia_id": p.sdamgia_id,
            "is_correct": a.is_correct,
            "primary_score": a.primary_score,
        }
        for (a, p) in rows
    ]
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    max_primary = None
    if variant is not None:
        rule = SCORING_RULES.get(variant.subject)
        if rule is not None:
            max_primary = max(int(k) for k in rule["primary_to_test"].keys())
    return PrimaryPointsOut(
        attempt_id=attempt.id,
        primary_score=attempt.primary_score,
        max_primary_score=max_primary,
        breakdown=breakdown,
    )


class TestPointsOut(BaseModel):
    attempt_id: int
    test_score: int | None
    primary_score: int | None
    subject: str | None
    scoring_version: str | None
    min_test_score_pass: int | None
    min_test_score_university: int | None
    passed: bool | None
    university_eligible: bool | None


@router.get("/attempts/{attempt_id}/test-points", response_model=TestPointsOut)
async def test_points(
    attempt_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TestPointsOut:
    attempt = await _get_owned_attempt(session, attempt_id, user)
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    subject = variant.subject if variant else None
    rule = SCORING_RULES.get(subject) if subject else None
    test_score = attempt.test_score
    passed = None
    uni = None
    if rule and test_score is not None:
        passed = test_score >= rule["min_test_score_pass"]
        if rule["min_test_score_university"] is not None:
            uni = test_score >= rule["min_test_score_university"]
    return TestPointsOut(
        attempt_id=attempt.id,
        test_score=test_score,
        primary_score=attempt.primary_score,
        subject=subject,
        scoring_version=rule["version"] if rule else None,
        min_test_score_pass=rule["min_test_score_pass"] if rule else None,
        min_test_score_university=rule["min_test_score_university"] if rule else None,
        passed=passed,
        university_eligible=uni,
    )
