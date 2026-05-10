from __future__ import annotations

import pytest

from parser.repository import get_existing_ids, insert_problem


def _payload(sdamgia_id: str, subject: str = "math", **overrides) -> dict:
    base = {
        "subject": subject,
        "sdamgia_id": sdamgia_id,
        "topic_number": "7",
        "topic_name": "Преобразования",
        "category_id": "100",
        "category_name": "Логарифмы",
        "condition_text": f"условие {sdamgia_id}",
        "condition_images": [],
        "solution_text": None,
        "solution_images": [],
        "answer": "42",
        "analogs": [],
        "url": f"https://example/{sdamgia_id}",
    }
    base.update(overrides)
    return base


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_insert_returns_true_on_new(session):
    inserted = await insert_problem(session, _payload("1001"))
    await session.commit()
    assert inserted is True

    existing = await get_existing_ids(session, "math")
    assert existing == {"1001"}


@pytest.mark.asyncio
async def test_insert_returns_false_on_duplicate(session):
    # ON CONFLICT DO NOTHING — повтор не падает и не перезаписывает старую запись
    await insert_problem(session, _payload("2002"))
    await session.commit()

    again = await insert_problem(session, _payload("2002", answer="другой ответ"))
    await session.commit()
    assert again is False

    existing = await get_existing_ids(session, "math")
    assert existing == {"2002"}


@pytest.mark.asyncio
async def test_same_id_different_subjects_both_insert(session):
    # (subject, sdamgia_id) — составной ключ; один id живёт в разных предметах
    a = await insert_problem(session, _payload("3003", subject="math"))
    b = await insert_problem(session, _payload("3003", subject="russian"))
    await session.commit()
    assert a is True and b is True

    assert await get_existing_ids(session, "math") == {"3003"}
    assert await get_existing_ids(session, "russian") == {"3003"}


@pytest.mark.asyncio
async def test_get_existing_ids_filters_by_subject(session):
    for sid in ("1", "2", "3"):
        await insert_problem(session, _payload(sid, subject="math"))
    await insert_problem(session, _payload("99", subject="russian"))
    await session.commit()

    assert await get_existing_ids(session, "math") == {"1", "2", "3"}
    assert await get_existing_ids(session, "russian") == {"99"}
    assert await get_existing_ids(session, "physics") == set()
