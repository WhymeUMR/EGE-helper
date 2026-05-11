"""Block 6: /api/v1/checking/*"""

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
        "/api/v1/auth/register", json={"email": email, "password": "pass1234"}
    )).json()


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


# ───────────────────── /answers ─────────────────────


@pytest.mark.asyncio
async def test_validate_normalizes(api_client):
    response = await api_client.post(
        "/api/v1/checking/answers/validate", json={"answer": "  0,5  "}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["normalized"] == "0.5"
    assert body["looks_numeric"] is True


@pytest.mark.asyncio
async def test_validate_empty(api_client):
    body = (await api_client.post(
        "/api/v1/checking/answers/validate", json={"answer": "   "}
    )).json()
    assert body["is_empty"] is True


@pytest.mark.asyncio
async def test_check_pair_correct(api_client):
    body = (await api_client.post(
        "/api/v1/checking/answers/check",
        json={"user_answer": "0,5", "correct_answer": "0.500"},
    )).json()
    assert body["is_correct"] is True


@pytest.mark.asyncio
async def test_check_pair_alternatives(api_client):
    body = (await api_client.post(
        "/api/v1/checking/answers/check",
        json={"user_answer": "yes", "correct_answer": "да|yes|ага"},
    )).json()
    assert body["is_correct"] is True


# ───────────────────── /attempts/{id}/* ─────────────────────


async def _start_attempt_with_2_correct(session, api_client):
    """Создаёт attempt где 2 из 3 ответов сохранены и оба верные.
    Возвращает (tokens, attempt_id, pids)."""
    for sid, ans in (("p1", "1"), ("p2", "2"), ("p3", "3")):
        await insert_problem(session, _problem(sid, answer=ans))
    await session.commit()
    from sqlalchemy import select
    from bot.db.models import Problem
    pids = [
        p.id for p in (
            await session.execute(
                select(Problem).where(Problem.subject == "math").order_by(Problem.sdamgia_id)
            )
        ).scalars()
    ]
    tokens = await _register(api_client)
    started = (await api_client.post(
        "/api/v1/attempts/start",
        headers=_bearer(tokens["access_token"]),
        json={"subject": "math", "problem_ids": pids},
    )).json()
    await api_client.post(
        f"/api/v1/attempts/{started['id']}/answers",
        headers=_bearer(tokens["access_token"]),
        json={"answers": [
            {"problem_id": pids[0], "answer": "1"},
            {"problem_id": pids[1], "answer": "2"},
        ]},
    )
    return tokens, started["id"], pids


@pytest.mark.asyncio
async def test_recheck_recalculates(session, api_client):
    tokens, aid, _ = await _start_attempt_with_2_correct(session, api_client)
    response = await api_client.post(
        f"/api/v1/checking/attempts/{aid}/recheck",
        headers=_bearer(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_score"] == 2


@pytest.mark.asyncio
async def test_score_endpoint(session, api_client):
    tokens, aid, _ = await _start_attempt_with_2_correct(session, api_client)
    await api_client.post(
        f"/api/v1/checking/attempts/{aid}/recheck",
        headers=_bearer(tokens["access_token"]),
    )
    response = await api_client.get(
        f"/api/v1/checking/attempts/{aid}/score",
        headers=_bearer(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_score"] == 2
    assert body["max_primary_score"] == 32  # math
    assert body["correct_count"] == 2
    assert body["answered_count"] == 2


@pytest.mark.asyncio
async def test_criteria_endpoint(session, api_client):
    tokens, aid, _ = await _start_attempt_with_2_correct(session, api_client)
    response = await api_client.get(
        f"/api/v1/checking/attempts/{aid}/criteria",
        headers=_bearer(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    # все задачи имеют answer → has_extended_answer = False
    assert any(item for item in body["items"])


@pytest.mark.asyncio
async def test_primary_points_breakdown(session, api_client):
    tokens, aid, pids = await _start_attempt_with_2_correct(session, api_client)
    await api_client.post(
        f"/api/v1/checking/attempts/{aid}/recheck",
        headers=_bearer(tokens["access_token"]),
    )
    body = (await api_client.get(
        f"/api/v1/checking/attempts/{aid}/primary-points",
        headers=_bearer(tokens["access_token"]),
    )).json()
    assert body["primary_score"] == 2
    assert body["max_primary_score"] == 32
    assert len(body["breakdown"]) == 2


@pytest.mark.asyncio
async def test_test_points_with_pass_threshold(session, api_client):
    tokens, aid, _ = await _start_attempt_with_2_correct(session, api_client)
    await api_client.post(
        f"/api/v1/checking/attempts/{aid}/recheck",
        headers=_bearer(tokens["access_token"]),
    )
    body = (await api_client.get(
        f"/api/v1/checking/attempts/{aid}/test-points",
        headers=_bearer(tokens["access_token"]),
    )).json()
    assert body["subject"] == "math"
    assert body["scoring_version"] == "2025-linear-approx"
    assert body["min_test_score_pass"] == 27
    # 2/32 ≈ 6 баллов → не сдан
    assert body["passed"] is False


@pytest.mark.asyncio
async def test_attempts_endpoints_require_auth(session, api_client):
    response = await api_client.get("/api/v1/checking/attempts/1/score")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_attempt_not_found(session, api_client):
    tokens = await _register(api_client)
    response = await api_client.get(
        "/api/v1/checking/attempts/9999/score",
        headers=_bearer(tokens["access_token"]),
    )
    assert response.status_code == 404
