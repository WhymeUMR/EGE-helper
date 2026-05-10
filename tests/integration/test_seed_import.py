from __future__ import annotations

import gzip
import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from parser.config import ParserSettings
from parser.repository import insert_problem
from parser.seed import import_if_empty


pytestmark = pytest.mark.integration


def _make_settings_for(engine, seed_url: str = "") -> ParserSettings:
    return ParserSettings(
        POSTGRES_HOST=os.environ.get("POSTGRES_TEST_HOST", "localhost"),
        POSTGRES_PORT=int(os.environ.get("POSTGRES_TEST_PORT", "5433")),
        POSTGRES_DB=os.environ.get("POSTGRES_TEST_DB", "ege_helper_test"),
        POSTGRES_USER=os.environ.get("POSTGRES_TEST_USER", "ege_user"),
        POSTGRES_PASSWORD=os.environ.get("POSTGRES_TEST_PASSWORD", "ege_password"),
        PARSER_SEED_URL=seed_url,
    )


@pytest.mark.asyncio
async def test_empty_url_skips(engine, session):
    sf = async_sessionmaker(engine, expire_on_commit=False)
    settings = _make_settings_for(engine, seed_url="")
    result = await import_if_empty(sf, settings)
    assert result is False


@pytest.mark.asyncio
async def test_non_empty_db_skips(engine, session):
    # БД не пустая → URL даже не дёргаем
    await insert_problem(
        session,
        {
            "subject": "math", "sdamgia_id": "1", "topic_number": "1",
            "topic_name": "x", "category_id": "1", "category_name": "y",
            "condition_text": "z", "condition_images": [],
            "solution_text": None, "solution_images": [],
            "answer": "1", "analogs": [], "url": None,
        },
    )
    await session.commit()

    sf = async_sessionmaker(engine, expire_on_commit=False)
    settings = _make_settings_for(engine, seed_url="https://example.com/whatever.sql.gz")
    result = await import_if_empty(sf, settings)
    assert result is False


@pytest.mark.asyncio
async def test_bogus_url_doesnt_crash(engine, session):
    # 404 от seed-сервера → False + лог, парсер дальше едет с пустой БД
    sf = async_sessionmaker(engine, expire_on_commit=False)
    settings = _make_settings_for(
        engine,
        seed_url="https://github.com/nonexistent-x-y-z/nope/releases/latest/download/x.sql.gz",
    )
    result = await import_if_empty(sf, settings)
    assert result is False


@pytest.mark.asyncio
async def test_imports_local_dump_via_file_url(engine, session, tmp_path: Path):
    # file:// — полный цикл: качаем, разжимаем gzip, скармливаем psql, проверяем БД
    sql = """
    INSERT INTO problems (
        subject, sdamgia_id, topic_number, topic_name, category_id, category_name,
        condition_text, condition_images, solution_text, solution_images,
        answer, analogs, url, created_at, updated_at
    ) VALUES
    ('math', '777', '7', 'Преобразования', '100', 'Логарифмы',
     'тестовое условие', '[]'::jsonb, NULL, '[]'::jsonb,
     '7', '[]'::jsonb, 'http://x', NOW(), NOW()),
    ('math', '778', '7', 'Преобразования', '100', 'Логарифмы',
     'другое условие', '[]'::jsonb, NULL, '[]'::jsonb,
     '8', '[]'::jsonb, 'http://y', NOW(), NOW());
    """
    dump_path = tmp_path / "problems.sql.gz"
    with gzip.open(dump_path, "wt", encoding="utf-8") as f:
        f.write(sql)

    sf = async_sessionmaker(engine, expire_on_commit=False)
    settings = _make_settings_for(engine, seed_url=f"file://{dump_path}")

    result = await import_if_empty(sf, settings)
    assert result is True

    async with sf() as s:
        from parser.repository import get_existing_ids
        ids = await get_existing_ids(s, "math")
    assert ids == {"777", "778"}
