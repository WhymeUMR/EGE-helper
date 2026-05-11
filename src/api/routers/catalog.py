"""Block 2: catalog meta — subjects + per-subject {meta, blueprints,
topic-map, difficulty-scale, scoring-rules}.

Источник истины для blueprints и scoring_rules — модули в `api.seeds`.
topic-map агрегируется из реально лежащих в БД задач по `subject`.
difficulty-scale выводится из blueprint (часть 1 = базовый/повышенный,
часть 2 = высокий уровень).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.seeds.blueprints import BLUEPRINTS
from api.seeds.scoring_rules import SCORING_RULES
from bot.catalog import SUBJECT_EMOJIS, SUBJECT_KEYS, SUBJECT_LABELS
from bot.db.models import Problem

router = APIRouter(prefix="/api/v1/subjects", tags=["catalog"])


class SubjectListItem(BaseModel):
    key: str
    label: str
    emoji: str
    problems_count: int
    topics_count: int
    has_blueprint: bool
    has_scoring_rules: bool


@router.get("", response_model=list[SubjectListItem])
async def list_subjects(session: AsyncSession = Depends(get_session)) -> list[SubjectListItem]:
    """Все предметы из catalog. Признак наличия blueprint/scoring + статистика."""
    rows = (
        await session.execute(
            select(
                Problem.subject,
                func.count(Problem.id),
                func.count(func.distinct(Problem.topic_number)),
            ).group_by(Problem.subject)
        )
    ).all()
    counts = {r[0]: (r[1], r[2]) for r in rows}
    out: list[SubjectListItem] = []
    for key in sorted(SUBJECT_KEYS):
        problems_n, topics_n = counts.get(key, (0, 0))
        out.append(
            SubjectListItem(
                key=key,
                # label без эмодзи-префикса (эмодзи отдельным полем)
                label=SUBJECT_LABELS.get(key, key).split(" ", 1)[-1],
                emoji=SUBJECT_EMOJIS.get(key, ""),
                problems_count=problems_n,
                topics_count=topics_n,
                has_blueprint=key in BLUEPRINTS,
                has_scoring_rules=key in SCORING_RULES,
            )
        )
    return out


def _ensure_known(subject: str) -> None:
    if subject not in SUBJECT_KEYS:
        raise HTTPException(status_code=404, detail=f"unknown subject: {subject}")


# ───────────────────── meta ─────────────────────


class SubjectMeta(BaseModel):
    key: str
    label: str
    emoji: str
    problems_count: int
    topics_count: int
    has_blueprint: bool
    has_scoring_rules: bool
    duration_minutes: int | None
    max_primary_score: int | None


@router.get("/{subject}/meta", response_model=SubjectMeta)
async def subject_meta(
    subject: str, session: AsyncSession = Depends(get_session)
) -> SubjectMeta:
    _ensure_known(subject)
    problems_count = (
        await session.scalar(
            select(func.count(Problem.id)).where(Problem.subject == subject)
        )
    ) or 0
    topics_count = (
        await session.scalar(
            select(func.count(func.distinct(Problem.topic_number))).where(
                Problem.subject == subject
            )
        )
    ) or 0
    bp = BLUEPRINTS.get(subject)
    return SubjectMeta(
        key=subject,
        label=SUBJECT_LABELS.get(subject, subject).split(" ", 1)[-1],
        emoji=SUBJECT_EMOJIS.get(subject, ""),
        problems_count=problems_count,
        topics_count=topics_count,
        has_blueprint=bp is not None,
        has_scoring_rules=subject in SCORING_RULES,
        duration_minutes=bp["duration_minutes"] if bp else None,
        max_primary_score=bp["max_primary_score"] if bp else None,
    )


# ───────────────────── blueprints ─────────────────────


class BlueprintOut(BaseModel):
    subject: str
    version: str
    positions_total: int
    max_primary_score: int
    duration_minutes: int
    slots: list[dict]
    notes: str


@router.get("/{subject}/blueprints", response_model=BlueprintOut)
async def subject_blueprint(subject: str) -> BlueprintOut:
    _ensure_known(subject)
    bp = BLUEPRINTS.get(subject)
    if bp is None:
        raise HTTPException(
            status_code=404, detail=f"no blueprint configured for subject={subject}"
        )
    return BlueprintOut(**bp)


# ───────────────────── topic-map ─────────────────────


class TopicMapEntry(BaseModel):
    topic_number: str | None
    topic_name: str | None
    problems_count: int
    categories: list[dict[str, Any]]


@router.get("/{subject}/topic-map", response_model=list[TopicMapEntry])
async def subject_topic_map(
    subject: str, session: AsyncSession = Depends(get_session)
) -> list[TopicMapEntry]:
    """Карта тем предмета: какие topic_number/topic_name есть, и какие
    категории внутри. Источник — реально загруженные в БД problems.
    """
    _ensure_known(subject)
    rows = (
        await session.execute(
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
    ).all()

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

    def sort_key(t: dict) -> tuple[int, str]:
        n = t["topic_number"] or ""
        if n.isdigit():
            return (0, f"{int(n):03d}")
        return (1, n)

    out = sorted(grouped.values(), key=sort_key)
    for topic in out:
        topic["categories"].sort(key=lambda c: -c["problems_count"])
    return [TopicMapEntry(**t) for t in out]


# ───────────────────── difficulty-scale ─────────────────────


class DifficultySlot(BaseModel):
    positions: str
    level: str  # basic / advanced / high
    max_score: int


class DifficultyScale(BaseModel):
    subject: str
    version: str
    levels: list[DifficultySlot]
    notes: str


def _level_for_slot(slot: dict) -> str:
    """Эвристика: часть 1 с answer_type=short = basic/advanced, часть 2 = high.
    Различение basic/advanced на уровне slot невозможно без таблицы кодификатора;
    клиент вправе считать всю часть 1 как 'basic_advanced'.
    """
    if slot.get("part") == 2:
        return "high"
    return "basic_advanced"


@router.get("/{subject}/difficulty-scale", response_model=DifficultyScale)
async def subject_difficulty(subject: str) -> DifficultyScale:
    _ensure_known(subject)
    bp = BLUEPRINTS.get(subject)
    if bp is None:
        raise HTTPException(
            status_code=404, detail=f"no blueprint configured for subject={subject}"
        )
    levels = [
        DifficultySlot(
            positions=s["positions"],
            level=_level_for_slot(s),
            max_score=s["max_score"],
        )
        for s in bp["slots"]
    ]
    return DifficultyScale(
        subject=subject,
        version=bp["version"],
        levels=levels,
        notes=(
            "Часть 1 помечена как basic_advanced (точное различение требует "
            "сверки с кодификатором ФИПИ). Часть 2 — high."
        ),
    )


# ───────────────────── scoring-rules ─────────────────────


class ScoringRulesOut(BaseModel):
    subject: str
    version: str
    primary_to_test: dict[str, int]
    min_test_score_pass: int
    min_test_score_university: int | None
    notes: str
    max_primary_score: int


@router.get("/{subject}/scoring-rules", response_model=ScoringRulesOut)
async def subject_scoring(subject: str) -> ScoringRulesOut:
    _ensure_known(subject)
    rule = SCORING_RULES.get(subject)
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=f"no scoring rules configured for subject={subject}",
        )
    return ScoringRulesOut(
        **rule,
        max_primary_score=max(int(k) for k in rule["primary_to_test"].keys()),
    )
