"""Block 3: /problems extensions — search/similar/check/bookmark/report."""

from __future__ import annotations

import pytest

from parser.repository import insert_problem

pytestmark = pytest.mark.integration


def _problem(sdamgia_id: str, **overrides):
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
        "answer": "42",
        "analogs": [],
        "url": f"https://x/{sdamgia_id}",
    }
    base.update(overrides)
    return base


async def _register(api_client, email="alice@example.com"):
    resp = await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "pass1234"},
    )
    return resp.json()


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


# ───────────────────── /problems/search ─────────────────────


@pytest.mark.asyncio
async def test_search_by_text_query(session, api_client):
    await insert_problem(session, _problem("1", condition_text="Найти производную"))
    await insert_problem(session, _problem("2", condition_text="Решить уравнение"))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/search", json={"text_query": "производ"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sdamgia_id"] == "1"


@pytest.mark.asyncio
async def test_search_by_multiple_topics(session, api_client):
    await insert_problem(session, _problem("1", topic_number="7"))
    await insert_problem(session, _problem("2", topic_number="13"))
    await insert_problem(session, _problem("3", topic_number="19"))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/search",
        json={"subject": "math", "topic_numbers": ["7", "13"]},
    )
    body = response.json()
    assert body["total"] == 2
    assert {i["sdamgia_id"] for i in body["items"]} == {"1", "2"}


@pytest.mark.asyncio
async def test_search_by_has_solution_filter(session, api_client):
    await insert_problem(session, _problem("1", solution_text="ответ: 42"))
    await insert_problem(session, _problem("2", solution_text=None))
    await session.commit()
    only_with = (await api_client.post(
        "/api/v1/problems/search", json={"has_solution": True}
    )).json()
    assert only_with["total"] == 1 and only_with["items"][0]["sdamgia_id"] == "1"
    only_without = (await api_client.post(
        "/api/v1/problems/search", json={"has_solution": False}
    )).json()
    assert only_without["total"] == 1 and only_without["items"][0]["sdamgia_id"] == "2"


@pytest.mark.asyncio
async def test_search_by_sdamgia_ids(session, api_client):
    for sid in ("1", "2", "3"):
        await insert_problem(session, _problem(sid))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/search", json={"sdamgia_ids": ["1", "3"]}
    )
    body = response.json()
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_search_pagination_and_sort(session, api_client):
    for i in range(5):
        await insert_problem(session, _problem(str(i)))
    await session.commit()
    page1 = (await api_client.post(
        "/api/v1/problems/search", json={"limit": 2, "offset": 0, "sort": "newest"}
    )).json()
    assert page1["total"] == 5 and len(page1["items"]) == 2


# ───────────────────── /problems/similar ─────────────────────


@pytest.mark.asyncio
async def test_similar_returns_same_category_first(session, api_client):
    await insert_problem(session, _problem("pivot", category_id="C1", topic_number="7"))
    await insert_problem(session, _problem("a", category_id="C1", topic_number="7"))
    await insert_problem(session, _problem("b", category_id="C1", topic_number="7"))
    await insert_problem(session, _problem("c", category_id="C2", topic_number="7"))
    await session.commit()
    response = await api_client.get("/api/v1/problems/similar/math/pivot?limit=10")
    assert response.status_code == 200
    items = response.json()
    assert {i["sdamgia_id"] for i in items} >= {"a", "b"}
    # pivot не возвращается
    assert all(i["sdamgia_id"] != "pivot" for i in items)


@pytest.mark.asyncio
async def test_similar_404_for_unknown_problem(api_client):
    response = await api_client.get("/api/v1/problems/similar/math/0000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_similar_falls_back_to_same_topic(session, api_client):
    # pivot единственный в своей категории, но в топике есть ещё задачи
    await insert_problem(session, _problem("pivot", category_id="X", topic_number="7"))
    await insert_problem(session, _problem("a", category_id="Y", topic_number="7"))
    await insert_problem(session, _problem("b", category_id="Z", topic_number="7"))
    await session.commit()
    response = await api_client.get("/api/v1/problems/similar/math/pivot?limit=10")
    items = response.json()
    assert {i["sdamgia_id"] for i in items} >= {"a", "b"}


# ───────────────────── /problems/check ─────────────────────


@pytest.mark.asyncio
async def test_check_correct_answer(session, api_client):
    await insert_problem(session, _problem("1", answer="42"))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "42"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["has_correct_answer"] is True


@pytest.mark.asyncio
async def test_check_wrong_answer(session, api_client):
    await insert_problem(session, _problem("1", answer="42"))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "13"}
    )
    body = response.json()
    assert body["is_correct"] is False


@pytest.mark.asyncio
async def test_check_normalizes_decimal_separator(session, api_client):
    await insert_problem(session, _problem("1", answer="0.5"))
    await session.commit()
    body = (await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "0,5"}
    )).json()
    assert body["is_correct"] is True
    assert body["user_answer_normalized"] == "0.5"


@pytest.mark.asyncio
async def test_check_normalizes_trailing_zeros(session, api_client):
    await insert_problem(session, _problem("1", answer="1.5"))
    await session.commit()
    body = (await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "1.500"}
    )).json()
    assert body["is_correct"] is True


@pytest.mark.asyncio
async def test_check_strips_whitespace(session, api_client):
    await insert_problem(session, _problem("1", answer="привет"))
    await session.commit()
    body = (await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "  ПриВеТ  "}
    )).json()
    assert body["is_correct"] is True


@pytest.mark.asyncio
async def test_check_when_no_correct_answer(session, api_client):
    await insert_problem(session, _problem("1", answer=None))
    await session.commit()
    body = (await api_client.post(
        "/api/v1/problems/math/1/check", json={"answer": "42"}
    )).json()
    assert body["is_correct"] is False
    assert body["has_correct_answer"] is False


@pytest.mark.asyncio
async def test_check_accepts_alternatives_in_correct_answer(session, api_client):
    await insert_problem(session, _problem("1", answer="да|yes"))
    await session.commit()
    for ans in ("да", "yes", "ДА"):
        body = (await api_client.post(
            "/api/v1/problems/math/1/check", json={"answer": ans}
        )).json()
        assert body["is_correct"] is True, ans


@pytest.mark.asyncio
async def test_check_404_for_unknown_problem(api_client):
    response = await api_client.post(
        "/api/v1/problems/math/0000/check", json={"answer": "1"}
    )
    assert response.status_code == 404


# ───────────────────── /bookmark ─────────────────────


@pytest.mark.asyncio
async def test_bookmark_requires_auth(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    response = await api_client.post("/api/v1/problems/math/1/bookmark")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bookmark_create_and_idempotent(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    tokens = await _register(api_client)
    headers = _bearer(tokens["access_token"])

    r1 = await api_client.post("/api/v1/problems/math/1/bookmark", headers=headers)
    assert r1.status_code == 201
    r2 = await api_client.post("/api/v1/problems/math/1/bookmark", headers=headers)
    assert r2.status_code == 201
    # тот же bookmark, не дубликат — bookmarked_at одинаковый
    assert r1.json()["bookmarked_at"] == r2.json()["bookmarked_at"]


@pytest.mark.asyncio
async def test_bookmark_delete(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    tokens = await _register(api_client)
    headers = _bearer(tokens["access_token"])
    await api_client.post("/api/v1/problems/math/1/bookmark", headers=headers)

    deleted = await api_client.delete("/api/v1/problems/math/1/bookmark", headers=headers)
    assert deleted.status_code == 204

    # повторно удалить — 404
    again = await api_client.delete("/api/v1/problems/math/1/bookmark", headers=headers)
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_bookmark_404_for_unknown_problem(session, api_client):
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/problems/math/0000/bookmark", headers=_bearer(tokens["access_token"])
    )
    assert response.status_code == 404


# ───────────────────── /report ─────────────────────


@pytest.mark.asyncio
async def test_report_creates_record(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/problems/math/1/report",
        headers=_bearer(tokens["access_token"]),
        json={"reason": "wrong_answer", "comment": "ответ 42 не сходится с 41"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["reason"] == "wrong_answer"
    assert body["status"] == "open"


@pytest.mark.asyncio
async def test_report_requires_auth(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    response = await api_client.post(
        "/api/v1/problems/math/1/report",
        json={"reason": "typo"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_rejects_invalid_reason(session, api_client):
    await insert_problem(session, _problem("1"))
    await session.commit()
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/problems/math/1/report",
        headers=_bearer(tokens["access_token"]),
        json={"reason": "not_a_real_reason"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_404_for_unknown_problem(session, api_client):
    tokens = await _register(api_client)
    response = await api_client.post(
        "/api/v1/problems/math/0000/report",
        headers=_bearer(tokens["access_token"]),
        json={"reason": "other"},
    )
    assert response.status_code == 404
