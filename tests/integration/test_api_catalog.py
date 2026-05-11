"""Block 2: catalog meta — /subjects + /subjects/{subject}/{meta,blueprints,topic-map,difficulty-scale,scoring-rules}."""

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


# ───────────────────── /subjects ─────────────────────


@pytest.mark.asyncio
async def test_subjects_returns_all_known_subjects(session, api_client):
    response = await api_client.get("/api/v1/subjects")
    assert response.status_code == 200
    body = response.json()
    keys = {row["key"] for row in body}
    # все 11 предметов из catalog
    expected = {
        "math", "russian", "informatics", "physics", "chemistry", "biology",
        "history", "social", "english", "literature", "geography",
    }
    assert expected.issubset(keys)
    for row in body:
        assert "label" in row and "emoji" in row
        assert "problems_count" in row and "topics_count" in row
        assert "has_blueprint" in row and "has_scoring_rules" in row
        # все предметы из catalog покрыты blueprint/scoring сидами
        assert row["has_blueprint"] is True
        assert row["has_scoring_rules"] is True


@pytest.mark.asyncio
async def test_subjects_counts_problems(session, api_client):
    for sid in ("1", "2", "3"):
        await insert_problem(session, _problem(sid, topic_number="1"))
    await insert_problem(session, _problem("4", topic_number="2"))
    await insert_problem(session, _problem("5", subject="russian", topic_number="1"))
    await session.commit()

    by_key = {r["key"]: r for r in (await api_client.get("/api/v1/subjects")).json()}
    assert by_key["math"]["problems_count"] == 4
    assert by_key["math"]["topics_count"] == 2
    assert by_key["russian"]["problems_count"] == 1
    assert by_key["chemistry"]["problems_count"] == 0


# ───────────────────── /subjects/{subject}/meta ─────────────────────


@pytest.mark.asyncio
async def test_subject_meta_known(session, api_client):
    await insert_problem(session, _problem("1", topic_number="13"))
    await session.commit()
    response = await api_client.get("/api/v1/subjects/math/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "math"
    assert body["problems_count"] == 1
    assert body["topics_count"] == 1
    assert body["has_blueprint"] is True
    assert body["max_primary_score"] == 32
    assert body["duration_minutes"] == 235


@pytest.mark.asyncio
async def test_subject_meta_unknown_404(api_client):
    response = await api_client.get("/api/v1/subjects/fortune-telling/meta")
    assert response.status_code == 404


# ───────────────────── /subjects/{subject}/blueprints ─────────────────────


@pytest.mark.asyncio
async def test_blueprint_math(api_client):
    response = await api_client.get("/api/v1/subjects/math/blueprints")
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "math"
    assert body["positions_total"] == 19
    assert body["max_primary_score"] == 32
    # сумма max_score по slots (с агрегатами part1) — близка к max_primary_score
    assert len(body["slots"]) >= 2
    # часть 1 = position "1-12", часть 2 — отдельные позиции
    parts = {s["part"] for s in body["slots"]}
    assert parts == {1, 2}


@pytest.mark.asyncio
async def test_blueprint_for_each_subject(api_client):
    for subject in (
        "math", "russian", "informatics", "physics", "chemistry", "biology",
        "history", "social", "english", "literature", "geography",
    ):
        response = await api_client.get(f"/api/v1/subjects/{subject}/blueprints")
        assert response.status_code == 200, f"{subject}: {response.json()}"
        body = response.json()
        assert body["subject"] == subject
        assert body["positions_total"] > 0
        assert body["max_primary_score"] > 0
        assert body["duration_minutes"] > 0
        assert isinstance(body["slots"], list) and body["slots"]


@pytest.mark.asyncio
async def test_blueprint_unknown_subject_404(api_client):
    response = await api_client.get("/api/v1/subjects/fake/blueprints")
    assert response.status_code == 404


# ───────────────────── topic-map ─────────────────────


@pytest.mark.asyncio
async def test_topic_map_groups_categories(session, api_client):
    await insert_problem(session, _problem("1", topic_number="7", category_name="Логарифмы"))
    await insert_problem(session, _problem("2", topic_number="7", category_name="Логарифмы"))
    await insert_problem(session, _problem("3", topic_number="7", category_name="Степени"))
    await insert_problem(session, _problem("4", topic_number="13", category_name="Уравнения"))
    await session.commit()

    response = await api_client.get("/api/v1/subjects/math/topic-map")
    assert response.status_code == 200
    by_num = {t["topic_number"]: t for t in response.json()}
    assert by_num["7"]["problems_count"] == 3
    assert len(by_num["7"]["categories"]) == 2
    cats = by_num["7"]["categories"]
    assert cats[0]["category_name"] == "Логарифмы" and cats[0]["problems_count"] == 2


@pytest.mark.asyncio
async def test_topic_map_empty_for_subject_with_no_problems(session, api_client):
    response = await api_client.get("/api/v1/subjects/literature/topic-map")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_topic_map_unknown_subject_404(api_client):
    response = await api_client.get("/api/v1/subjects/fake/topic-map")
    assert response.status_code == 404


# ───────────────────── difficulty-scale ─────────────────────


@pytest.mark.asyncio
async def test_difficulty_scale(api_client):
    response = await api_client.get("/api/v1/subjects/math/difficulty-scale")
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "math"
    assert body["levels"]
    levels = {l["level"] for l in body["levels"]}
    assert "high" in levels  # часть 2 у math всегда есть


@pytest.mark.asyncio
async def test_difficulty_unknown_subject_404(api_client):
    response = await api_client.get("/api/v1/subjects/fake/difficulty-scale")
    assert response.status_code == 404


# ───────────────────── scoring-rules ─────────────────────


@pytest.mark.asyncio
async def test_scoring_rules_math(api_client):
    response = await api_client.get("/api/v1/subjects/math/scoring-rules")
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "math"
    assert body["max_primary_score"] == 32
    # шкала покрывает все первичные баллы 0..32
    assert body["primary_to_test"]["0"] == 0
    assert body["primary_to_test"]["32"] == 100
    assert body["min_test_score_pass"] == 27
    assert body["min_test_score_university"] == 39


@pytest.mark.asyncio
async def test_scoring_rules_for_each_subject(api_client):
    for subject in (
        "math", "russian", "informatics", "physics", "chemistry", "biology",
        "history", "social", "english", "literature", "geography",
    ):
        response = await api_client.get(f"/api/v1/subjects/{subject}/scoring-rules")
        assert response.status_code == 200, f"{subject}: {response.json()}"
        body = response.json()
        assert body["primary_to_test"]["0"] == 0
        assert body["primary_to_test"][str(body["max_primary_score"])] == 100
        assert body["min_test_score_pass"] > 0


@pytest.mark.asyncio
async def test_scoring_rules_unknown_subject_404(api_client):
    response = await api_client.get("/api/v1/subjects/fake/scoring-rules")
    assert response.status_code == 404
