"""Маппинг ключей предметов бота → коды СдамГИА.

В боте предметы зовутся `russian`/`informatics`/..., у sdamgia коды
`rus`/`inf`/... — это единственное место связи.
"""

from __future__ import annotations

SUBJECT_TO_SDAMGIA: dict[str, str] = {
    "math": "math",
    "russian": "rus",
    "informatics": "inf",
    "physics": "phys",
    "chemistry": "chem",
    "biology": "bio",
    "history": "hist",
    "social": "soc",
    "english": "en",
    "literature": "lit",
    "geography": "geo",
}
