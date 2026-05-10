from __future__ import annotations

import pytest

from parser.repository import insert_problem


def _problem(sdamgia_id: str, *, subject="math", topic_number="7", category_name="Логарифмы"):
    return {
        "subject": subject,
        "sdamgia_id": sdamgia_id,
        "topic_number": topic_number,
        "topic_name": "Преобразования",
        "category_id": "100",
        "category_name": category_name,
        "condition_text": f"условие #{sdamgia_id}",
        "condition_images": [],
        "solution_text": None,
        "solution_images": [],
        "answer": "42",
        "analogs": [],
        "url": f"https://x/{sdamgia_id}",
    }


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health_no_auth(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_subjects_aggregates_correctly(session, api_client):
    for sid in ("1", "2", "3"):
        await insert_problem(session, _problem(sid, subject="math", topic_number="1"))
    await insert_problem(session, _problem("4", subject="math", topic_number="2"))
    await insert_problem(session, _problem("5", subject="russian", topic_number="1"))
    await session.commit()

    response = await api_client.get("/api/v1/subjects")
    assert response.status_code == 200
    by_key = {row["key"]: row for row in response.json()}
    assert by_key["math"]["problems_count"] == 4
    assert by_key["math"]["topics_count"] == 2  # номера 1 и 2
    assert by_key["russian"]["problems_count"] == 1
    assert "математика" in by_key["math"]["label"].lower()


@pytest.mark.asyncio
async def test_topics_groups_categories_under_topic_number(session, api_client):
    await insert_problem(session, _problem("1", topic_number="7", category_name="Логарифмы"))
    await insert_problem(session, _problem("2", topic_number="7", category_name="Логарифмы"))
    await insert_problem(session, _problem("3", topic_number="7", category_name="Степени"))
    await insert_problem(session, _problem("4", topic_number="13", category_name="Уравнения"))
    await session.commit()

    response = await api_client.get("/api/v1/topics?subject=math")
    assert response.status_code == 200
    topics = response.json()
    by_num = {t["topic_number"]: t for t in topics}

    assert by_num["7"]["problems_count"] == 3
    assert len(by_num["7"]["categories"]) == 2
    # внутри топика категории идут от самой большой к самой маленькой
    cats = by_num["7"]["categories"]
    assert cats[0]["category_name"] == "Логарифмы"
    assert cats[0]["problems_count"] == 2
    assert cats[1]["category_name"] == "Степени"

    assert by_num["13"]["problems_count"] == 1


@pytest.mark.asyncio
async def test_topics_sorted_numerically_then_letter_codes(session, api_client):
    # числовые номера идут как int (1,2,…,19), потом досрочные/демо в строковом порядке
    for tn in ("19", "1", "2", "Д8 C1", "Д1"):
        await insert_problem(session, _problem(tn, topic_number=tn))
    await session.commit()

    response = await api_client.get("/api/v1/topics?subject=math")
    nums = [t["topic_number"] for t in response.json()]
    assert nums == ["1", "2", "19", "Д1", "Д8 C1"]


@pytest.mark.asyncio
async def test_problems_filter_by_topic_number(session, api_client):
    await insert_problem(session, _problem("1", topic_number="7"))
    await insert_problem(session, _problem("2", topic_number="7"))
    await insert_problem(session, _problem("3", topic_number="13"))
    await session.commit()

    response = await api_client.get("/api/v1/problems?subject=math&topic_number=7")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["sdamgia_id"] for item in body["items"]} == {"1", "2"}


@pytest.mark.asyncio
async def test_problems_filter_by_category(session, api_client):
    await insert_problem(session, _problem("1", category_name="A"))
    await insert_problem(session, _problem("2", category_name="A"))
    await insert_problem(session, _problem("3", category_name="B"))
    await session.commit()

    response = await api_client.get("/api/v1/problems?subject=math&category_name=A")
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_problems_pagination(session, api_client):
    for i in range(7):
        await insert_problem(session, _problem(str(i), topic_number="7"))
    await session.commit()

    page1 = (await api_client.get("/api/v1/problems?subject=math&topic_number=7&limit=3&offset=0")).json()
    page2 = (await api_client.get("/api/v1/problems?subject=math&topic_number=7&limit=3&offset=3")).json()
    page3 = (await api_client.get("/api/v1/problems?subject=math&topic_number=7&limit=3&offset=6")).json()

    assert page1["total"] == 7 and len(page1["items"]) == 3
    assert page2["total"] == 7 and len(page2["items"]) == 3
    assert page3["total"] == 7 and len(page3["items"]) == 1
    ids = (
        [i["sdamgia_id"] for i in page1["items"]]
        + [i["sdamgia_id"] for i in page2["items"]]
        + [i["sdamgia_id"] for i in page3["items"]]
    )
    assert len(set(ids)) == 7


@pytest.mark.asyncio
async def test_problems_limit_validation(api_client):
    # ge=1, le=200 — оба края должны падать в 422
    assert (await api_client.get("/api/v1/problems?subject=math&limit=0")).status_code == 422
    assert (await api_client.get("/api/v1/problems?subject=math&limit=999")).status_code == 422


@pytest.mark.asyncio
async def test_random_returns_one_under_filter(session, api_client):
    for sid in ("a", "b", "c"):
        await insert_problem(session, _problem(sid, topic_number="7"))
    await insert_problem(session, _problem("z", topic_number="13"))
    await session.commit()

    response = await api_client.get("/api/v1/problems/random?subject=math&topic_number=7")
    assert response.status_code == 200
    assert response.json()["sdamgia_id"] in {"a", "b", "c"}


@pytest.mark.asyncio
async def test_random_404_when_filter_empty(session, api_client):
    response = await api_client.get("/api/v1/problems/random?subject=math&topic_number=99")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_problem_by_composite_key(session, api_client):
    await insert_problem(session, _problem("12345"))
    await session.commit()

    response = await api_client.get("/api/v1/problems/math/12345")
    assert response.status_code == 200
    assert response.json()["sdamgia_id"] == "12345"


@pytest.mark.asyncio
async def test_get_problem_404_when_unknown(api_client):
    response = await api_client.get("/api/v1/problems/math/0000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_auth_blocks_when_token_set(session, api_client, monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "api_token", "secret123")

    no_token = await api_client.get("/api/v1/subjects")
    assert no_token.status_code == 401

    wrong = await api_client.get(
        "/api/v1/subjects", headers={"Authorization": "Bearer wrong"}
    )
    assert wrong.status_code == 401

    ok = await api_client.get(
        "/api/v1/subjects", headers={"Authorization": "Bearer secret123"}
    )
    assert ok.status_code == 200

    # /health не висит на require_token
    health = await api_client.get("/health")
    assert health.status_code == 200
