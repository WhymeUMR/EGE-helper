from __future__ import annotations

from bot.catalog import SUBJECT_KEYS
from parser.catalog import SUBJECT_TO_SDAMGIA


def test_all_bot_subjects_have_sdamgia_code():
    missing = SUBJECT_KEYS - SUBJECT_TO_SDAMGIA.keys()
    assert not missing, f"в маппинге не хватает: {missing}"


def test_no_extra_codes_in_mapping():
    extra = SUBJECT_TO_SDAMGIA.keys() - SUBJECT_KEYS
    assert not extra, f"в маппинге лишние: {extra}"


def test_known_codes():
    assert SUBJECT_TO_SDAMGIA["math"] == "math"
    assert SUBJECT_TO_SDAMGIA["russian"] == "rus"
    assert SUBJECT_TO_SDAMGIA["informatics"] == "inf"
    assert SUBJECT_TO_SDAMGIA["physics"] == "phys"
