"""Расчёт первичного и тестового балла для attempt.

В фазе 1 умеем только автопроверку части 1 (где у problem есть answer):
- если ответ совпадает после нормализации → primary_score = 1
- если не совпадает → primary_score = 0
- если у problem нет answer'а ИЛИ пользователь не дал ответ → None

Часть 2 (развёрнутый ответ) не оценивается автоматически, но клиент может
заполнить criteria_scores вручную; suma по criteria_scores войдёт в
primary_score этого ответа.

Перевод в тестовый балл — через `api.seeds.scoring_rules` (предмет берём из
variant.subject). Если для предмета нет scoring rule — test_score останется
None.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.seeds.scoring_rules import SCORING_RULES
from api.services.answer_check import answers_equal
from bot.db.models import Attempt, AttemptAnswer, Problem, Variant


async def recompute_scores(session: AsyncSession, attempt: Attempt) -> None:
    """Пересчитать primary_score у каждого AttemptAnswer + total на attempt.
    Изменения в session, без commit."""
    answers = list(
        (await session.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
        )).scalars()
    )
    if not answers:
        attempt.primary_score = 0
        attempt.test_score = 0
        return

    problem_ids = [a.problem_id for a in answers]
    problems = {
        p.id: p
        for p in (
            await session.execute(select(Problem).where(Problem.id.in_(problem_ids)))
        ).scalars()
    }

    primary_total = 0
    for ans in answers:
        problem = problems.get(ans.problem_id)
        if problem is None:
            continue
        # ручные критерии части 2 имеют приоритет — если их прислал клиент,
        # primary_score берём как сумму
        if ans.criteria_scores:
            try:
                ans.primary_score = sum(int(v) for v in ans.criteria_scores.values())
            except (TypeError, ValueError):
                ans.primary_score = None
        elif problem.answer and ans.answer is not None:
            ok = answers_equal(ans.answer, problem.answer)
            ans.is_correct = ok
            ans.primary_score = 1 if ok else 0
        else:
            ans.is_correct = None
            ans.primary_score = None
        if ans.primary_score is not None:
            primary_total += ans.primary_score

    attempt.primary_score = primary_total
    # тестовый — через шкалу variant.subject
    variant = await session.scalar(select(Variant).where(Variant.id == attempt.variant_id))
    if variant is not None:
        rule = SCORING_RULES.get(variant.subject)
        if rule is not None:
            scale = rule["primary_to_test"]
            # клампим на максимум
            max_primary = max(int(k) for k in scale.keys())
            key = str(min(primary_total, max_primary))
            attempt.test_score = scale.get(key, 0)
        else:
            attempt.test_score = None
    else:
        attempt.test_score = None
