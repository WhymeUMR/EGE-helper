from __future__ import annotations

from datetime import date

import pytest

from bot.utils.dates import days_to_ege, decline_days
from bot.utils.names import safe_name
from bot.utils.progress import progress_bar, step_header


class TestDeclineDays:
    @pytest.mark.parametrize(
        "n,expected",
        [
            (1, "день"),
            (2, "дня"),
            (3, "дня"),
            (4, "дня"),
            (5, "дней"),
            (10, "дней"),
            (11, "дней"),
            (14, "дней"),
            (15, "дней"),
            (21, "день"),
            (22, "дня"),
            (25, "дней"),
            (101, "день"),
            (111, "дней"),
            (114, "дней"),
            (122, "дня"),
            (0, "дней"),
            (-3, "дня"),
        ],
    )
    def test_cases(self, n: int, expected: str):
        assert decline_days(n) == expected


class TestDaysToEge:
    def test_11th_grade_before_may(self):
        assert days_to_ege(11, today=date(2025, 1, 1)) == (date(2025, 5, 23) - date(2025, 1, 1)).days

    def test_11th_grade_after_may_rolls_to_next_year(self):
        # май уже прошёл — целимся в следующий
        assert days_to_ege(11, today=date(2025, 6, 1)) == (date(2026, 5, 23) - date(2025, 6, 1)).days

    def test_10th_grade_adds_a_year(self):
        # 10кл сдаёт через год после 11-классников
        assert days_to_ege(10, today=date(2025, 1, 1)) == (date(2026, 5, 23) - date(2025, 1, 1)).days

    def test_unknown_grade_treated_as_11(self):
        assert days_to_ege(None, today=date(2025, 1, 1)) == days_to_ege(11, today=date(2025, 1, 1))

    def test_exam_day_itself_returns_zero(self):
        assert days_to_ege(11, today=date(2025, 5, 23)) == 0


class TestSafeName:
    def test_html_escaped(self):
        assert safe_name("<script>") == "&lt;script&gt;"

    def test_ampersand_escaped(self):
        assert safe_name("Tom & Jerry") == "Tom &amp; Jerry"

    def test_empty_falls_back(self):
        assert safe_name(None) == "друг"
        assert safe_name("") == "друг"
        assert safe_name("   ") == "друг"

    def test_custom_fallback(self):
        assert safe_name(None, fallback="приятель") == "приятель"

    def test_strips_whitespace(self):
        assert safe_name("  Bogdan  ") == "Bogdan"


class TestProgressBar:
    @pytest.mark.parametrize(
        "step,total,expected",
        [
            (0, 3, "▱▱▱"),
            (1, 3, "▰▱▱"),
            (2, 3, "▰▰▱"),
            (3, 3, "▰▰▰"),
            (5, 3, "▰▰▰"),  # должны clamp'нуть в total
            (-1, 3, "▱▱▱"),
        ],
    )
    def test_bar(self, step: int, total: int, expected: str):
        assert progress_bar(step, total) == expected

    def test_step_header_contains_step_and_bar(self):
        header = step_header(2, "Предметы", "📚")
        assert "Шаг 2 из 3" in header
        assert "Предметы" in header
        assert "📚" in header
        assert "▰▰▱" in header
