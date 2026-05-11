"""Block 5: /api/v1/attempts/* — start, get, patch, answers, submit,
resume, abandon, review, mistakes."""

from __future__ import annotations

import pytest

from parser.repository import insert_problem

pytestmark = pytest.mark.integration


def _problem(sdamgia_id: str, *, answer="42", **overrides):
    base = {
        "subject": "math",
        "sdamgia_id": sdamgia_id,
        "topic_number": "7",
        "topic_name": "Преобразования",
        "category_id": "100",
        "category_name": "Логарифмы",
        "condition_text": f"условие #{sdamgia_id}",
        "condition_images": [],
        "solution_text": None,
        "solution_images": [],
        "answer": answer,
        "analogs": [],
        "url": f"https://x/{sdamgia_id}",
    }
    base.update(overrides)
    return base


async def _register(api_client, email="alice@example.com"):
    return (await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "pass1234"},
    )).json()


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _seed_three_problems(session) -> list[int]:
    """3 задачи с известными ответами 1/2/3, возвращает их .id (по порядку sdamgia)."""
    for sid, ans in (("p1", "1"), ("p2", "2"), ("p3", "3")):
        await insert_problem(session, _problem(sid, answer=ans))
    await session.commit()
    from sqlalchemy import select
    from bot.db.models import Problem
    rows = list((await session.execute(
        select(Problem).where(Problem.subject == "math").order_by(Problem.sdamgia_id)
    )).scalars())
    return [r.id for r in rows]


# ───────────────────── start ─────────────────────


@pytest.mark.asyncio
async def test_start_attempt_inline_with_problem_ids(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids, "title": "test1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["subject"] == "math"
    assert body["problem_ids"] == pids
    assert body["answers"] == []


@pytest.mark.asyncio
async def test_start_attempt_inline_with_sdamgia_ids(session, api_client):
    await _seed_three_problems(session)
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "sdamgia_ids": ["p1", "p2"]},
    )
    assert response.status_code == 201
    assert len(response.json()["problem_ids"]) == 2


@pytest.mark.asyncio
async def test_start_attempt_with_variant_id(session, api_client):
    pids = await _seed_three_problems(session)
    from bot.db.models import Variant
    variant = Variant(subject="math", title="custom", problem_ids=pids, kind="assembled")
    session.add(variant)
    await session.commit()
    await session.refresh(variant)

    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"variant_id": variant.id},
    )
    assert response.status_code == 201
    assert response.json()["variant_id"] == variant.id


@pytest.mark.asyncio
async def test_start_attempt_requires_either_variant_or_inline(session, api_client):
    tokens = await _register(api_client)
    bad = await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={},
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_start_attempt_404_for_unknown_variant(session, api_client):
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"variant_id": 99999},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_start_attempt_requires_auth(api_client):
    response = await api_client.post(
        "/api/v1/attempts/start", json={"subject": "math", "problem_ids": [1]}
    )
    assert response.status_code == 401


# ───────────────────── get / patch ─────────────────────


@pytest.mark.asyncio
async def test_get_attempt_belongs_to_user(session, api_client):
    pids = await _seed_three_problems(session)
    alice = await _register(api_client, "alice@example.com")
    bob = await _register(api_client, "bob@example.com")

    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(alice["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()

    # alice видит свой attempt
    own = await api_client.get(
        f"/api/v1/attempts/{started['id']}", headers=_bearer(alice["access_token"])
    )
    assert own.status_code == 200

    # bob — нет (404, не 403, чтобы не палить существование)
    foreign = await api_client.get(
        f"/api/v1/attempts/{started['id']}", headers=_bearer(bob["access_token"])
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_patch_attempt_updates_time_spent(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    response = await api_client.patch(
        f"/api/v1/attempts/{started['id']}",
        headers=_bearer(tokens["access_token"]),
        json={"time_spent_seconds": 600},
    )
    assert response.status_code == 200
    assert response.json()["time_spent_seconds"] == 600


# ───────────────────── save answers ─────────────────────


@pytest.mark.asyncio
async def test_save_single_answer(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    response = await api_client.post(
        f"/api/v1/attempts/{started['id']}/answer/{pids[0]}",
        headers=_bearer(tokens["access_token"]),
        json={"answer": "1", "time_spent_seconds": 30},
    )
    assert response.status_code == 200
    answers = {a["problem_id"]: a for a in response.json()["answers"]}
    assert answers[pids[0]]["answer"] == "1"


@pytest.mark.asyncio
async def test_save_single_answer_rejects_alien_problem(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": [pids[0]]},
    )).json()
    response = await api_client.post(
        f"/api/v1/attempts/{started['id']}/answer/{pids[1]}",  # не в варианте
        headers=_bearer(tokens["access_token"]),
        json={"answer": "x"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_save_batch_answers(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    response = await api_client.post(
        f"/api/v1/attempts/{started['id']}/answers",
        headers=_bearer(tokens["access_token"]),
        json={
            "answers": [
                {"problem_id": pids[0], "answer": "1"},
                {"problem_id": pids[1], "answer": "2"},
            ]
        },
    )
    assert response.status_code == 200
    assert sum(1 for a in response.json()["answers"] if a["answer"]) == 2


@pytest.mark.asyncio
async def test_save_overwrites_existing_answer(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    await api_client.post(
        f"/api/v1/attempts/{aid}/answer/{pids[0]}",
        headers=_bearer(tokens["access_token"]),
        json={"answer": "wrong"},
    )
    second = await api_client.post(
        f"/api/v1/attempts/{aid}/answer/{pids[0]}",
        headers=_bearer(tokens["access_token"]),
        json={"answer": "1"},
    )
    answers = {a["problem_id"]: a for a in second.json()["answers"]}
    assert answers[pids[0]]["answer"] == "1"


# ───────────────────── submit / review / mistakes ─────────────────────


@pytest.mark.asyncio
async def test_submit_calculates_score(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    # 2 из 3 правильных
    await api_client.post(
        f"/api/v1/attempts/{aid}/answers",
        headers=_bearer(tokens["access_token"]),
        json={"answers": [
            {"problem_id": pids[0], "answer": "1"},
            {"problem_id": pids[1], "answer": "wrong"},
            {"problem_id": pids[2], "answer": "3"},
        ]},
    )
    submitted = await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["primary_score"] == 2  # 2 правильных
    # test_score рассчитан по линейной шкале math (32 → 100)
    assert body["test_score"] is not None and body["test_score"] > 0


@pytest.mark.asyncio
async def test_submit_is_idempotent(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    second = await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    assert second.status_code == 200
    assert second.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_modifications_blocked_after_submit(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    blocked = await api_client.post(
        f"/api/v1/attempts/{aid}/answer/{pids[0]}",
        headers=_bearer(tokens["access_token"]),
        json={"answer": "1"},
    )
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_abandon_attempt(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    abandon = await api_client.post(
        f"/api/v1/attempts/{aid}/abandon", headers=_bearer(tokens["access_token"])
    )
    assert abandon.status_code == 200
    assert abandon.json()["status"] == "abandoned"

    # после abandon — нельзя resume
    resume = await api_client.post(
        f"/api/v1/attempts/{aid}/resume", headers=_bearer(tokens["access_token"])
    )
    assert resume.status_code == 409


@pytest.mark.asyncio
async def test_review_lists_all_positions(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    await api_client.post(
        f"/api/v1/attempts/{aid}/answers",
        headers=_bearer(tokens["access_token"]),
        json={"answers": [
            {"problem_id": pids[0], "answer": "1"},
            {"problem_id": pids[2], "answer": "wrong"},
        ]},
    )
    await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    review = await api_client.get(
        f"/api/v1/attempts/{aid}/review", headers=_bearer(tokens["access_token"])
    )
    assert review.status_code == 200
    items = review.json()["items"]
    assert len(items) == 3
    # позиции от 1 до 3
    assert [i["position"] for i in items] == [1, 2, 3]


@pytest.mark.asyncio
async def test_mistakes_returns_only_incorrect(session, api_client):
    pids = await _seed_three_problems(session)
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    aid = started["id"]
    await api_client.post(
        f"/api/v1/attempts/{aid}/answers",
        headers=_bearer(tokens["access_token"]),
        json={"answers": [
            {"problem_id": pids[0], "answer": "1"},  # верно
            {"problem_id": pids[1], "answer": "999"},  # неверно
        ]},
    )
    await api_client.post(
        f"/api/v1/attempts/{aid}/submit", headers=_bearer(tokens["access_token"])
    )
    mistakes = await api_client.get(
        f"/api/v1/attempts/{aid}/mistakes", headers=_bearer(tokens["access_token"])
    )
    assert mistakes.status_code == 200
    body = mistakes.json()
    assert len(body) == 1
    assert body[0]["problem_id"] == pids[1]
