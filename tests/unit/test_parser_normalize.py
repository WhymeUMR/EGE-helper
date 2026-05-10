from __future__ import annotations

from parser.service import _normalize_problem


def test_normalize_full_payload():
    raw = {
        "id": "1001",
        "topic": "4",
        "condition": {"text": "Найдите вероятность", "images": ["http://img/1.png"]},
        "solution": {"text": "Решение: ", "images": ["http://img/2.svg"]},
        "answer": "0,95",
        "analogs": ["1001", "1002"],
        "url": "https://math-ege.sdamgia.ru/problem?id=1001",
    }
    result = _normalize_problem(
        raw,
        subject="math",
        topic_number="4",
        topic_name="Вероятность",
        category_id="42",
        category_name="Классическое определение",
    )
    assert result["subject"] == "math"
    assert result["sdamgia_id"] == "1001"
    assert result["topic_number"] == "4"
    assert result["topic_name"] == "Вероятность"
    assert result["category_id"] == "42"
    assert result["category_name"] == "Классическое определение"
    assert result["condition_text"] == "Найдите вероятность"
    assert result["condition_images"] == ["http://img/1.png"]
    assert result["solution_text"] == "Решение:"  # хвостовой пробел отрезан
    assert result["answer"] == "0,95"
    assert result["analogs"] == ["1001", "1002"]
    assert result["url"] == "https://math-ege.sdamgia.ru/problem?id=1001"


def test_normalize_handles_missing_blocks():
    # sdamgia иногда вообще не присылает condition/solution
    raw = {"id": "999", "url": "x"}
    result = _normalize_problem(
        raw,
        subject="russian",
        topic_number=None,
        topic_name=None,
        category_id="0",
        category_name="",
    )
    assert result["sdamgia_id"] == "999"
    assert result["condition_text"] is None
    assert result["solution_text"] is None
    assert result["answer"] is None
    assert result["condition_images"] == []
    assert result["solution_images"] == []
    assert result["analogs"] == []


def test_normalize_strips_whitespace_only_text_to_none():
    raw = {"id": "1", "condition": {"text": "   \n  "}, "answer": "  "}
    result = _normalize_problem(
        raw, subject="math", topic_number="1", topic_name="x", category_id="1", category_name="y",
    )
    assert result["condition_text"] is None
    assert result["answer"] is None


def test_normalize_id_coerced_to_string():
    raw = {"id": 12345}
    result = _normalize_problem(
        raw, subject="math", topic_number="1", topic_name="x", category_id="1", category_name="y",
    )
    assert result["sdamgia_id"] == "12345"
    assert isinstance(result["sdamgia_id"], str)
