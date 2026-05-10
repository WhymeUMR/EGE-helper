"""Оркестратор парсинга: каталог → категории → задачи → БД."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.catalog import SUBJECTS, SUBJECT_LABELS
from parser.catalog import SUBJECT_TO_SDAMGIA
from parser.client import AsyncSdamGIA
from parser.config import settings
from parser.progress import ParserUI
from parser.repository import get_existing_ids, insert_problem

logger = logging.getLogger(__name__)


def _normalize_problem(
    raw: dict[str, Any],
    *,
    subject: str,
    topic_number: str | None,
    topic_name: str | None,
    category_id: str,
    category_name: str,
) -> dict[str, Any]:
    """Раскладываем dict от sdamgia-api по колонкам Problem."""
    condition = raw.get("condition") or {}
    solution = raw.get("solution") or {}
    return {
        "subject": subject,
        "sdamgia_id": str(raw.get("id", "")),
        "topic_number": topic_number,
        "topic_name": topic_name,
        "category_id": category_id,
        "category_name": category_name,
        "condition_text": (condition.get("text") or "").strip() or None,
        "condition_images": list(condition.get("images") or []),
        "solution_text": (solution.get("text") or "").strip() or None,
        "solution_images": list(solution.get("images") or []),
        "answer": (raw.get("answer") or "").strip() or None,
        "analogs": list(raw.get("analogs") or []),
        "url": raw.get("url"),
    }


async def _collect_category_ids(
    client: AsyncSdamGIA,
    subject_code: str,
    category_id: str,
    max_pages: int,
) -> list[str]:
    # sdamgia на «следующей после последней» странице тихо отдаёт повтор,
    # а не 404 — поэтому останавливаемся когда новых id на странице нет
    seen: set[str] = set()
    ordered: list[str] = []
    for page in range(1, max_pages + 1):
        try:
            ids = await client.get_category(subject_code, category_id, page=page)
        except Exception:  # noqa: BLE001
            logger.exception(
                "category page failed: subject=%s cat=%s page=%d",
                subject_code, category_id, page,
            )
            break
        if not ids:
            break
        new_on_page = [pid for pid in ids if pid not in seen]
        if not new_on_page:
            break
        for pid in new_on_page:
            seen.add(pid)
            ordered.append(pid)
    return ordered


async def _process_subject(
    *,
    client: AsyncSdamGIA,
    session_factory: async_sessionmaker,
    subject_key: str,
    subject_code: str,
    ui: ParserUI,
) -> None:
    label = SUBJECT_LABELS[subject_key]
    ui.enter_subject(label)

    try:
        catalog = await client.get_catalog(subject_code)
    except Exception:  # noqa: BLE001
        logger.exception("catalog fetch failed for %s", subject_key)
        ui.begin_subject(label, total_problems=0)
        ui.end_subject()
        return

    # тапл: (sdamgia_id, topic_number, topic_name, category_id, category_name)
    all_problems: list[tuple[str, str, str, str, str]] = []
    for topic in catalog:
        topic_number = topic.get("topic_id")
        topic_name = topic.get("topic_name")
        for category in topic.get("categories", []):
            category_id = category.get("category_id")
            category_name = category.get("category_name") or ""
            if not category_id:
                continue
            ui.set_category(f"{topic_name or ''} · {category_name}".strip(" ·"))
            ids = await _collect_category_ids(
                client,
                subject_code,
                category_id,
                settings.parser_max_pages_per_category,
            )
            for pid in ids:
                all_problems.append(
                    (pid, topic_number, topic_name, category_id, category_name)
                )

    # один SELECT вместо проверки existence для каждой задачи
    async with session_factory() as session:
        existing = await get_existing_ids(session, subject_key)

    ui.begin_subject(label, total_problems=len(all_problems))

    async def handle_one(item: tuple[str, str, str, str, str]) -> None:
        sdamgia_id, topic_number, topic_name, category_id, category_name = item
        if sdamgia_id in existing:
            ui.tick_skipped()
            return
        try:
            raw = await client.get_problem(subject_code, sdamgia_id)
        except Exception:  # noqa: BLE001
            ui.tick_error()
            return
        if raw is None:
            ui.tick_error()
            return
        payload = _normalize_problem(
            raw,
            subject=subject_key,
            topic_number=topic_number,
            topic_name=topic_name,
            category_id=category_id,
            category_name=category_name,
        )
        try:
            async with session_factory() as session:
                inserted = await insert_problem(session, payload)
                await session.commit()
        except Exception:  # noqa: BLE001
            ui.tick_error()
            return
        if inserted:
            ui.tick_fetched()
        else:
            # параллельный воркер успел раньше
            ui.tick_skipped()

    # параллельность ограничена семафором в AsyncSdamGIA, тут просто gather
    await asyncio.gather(*(handle_one(item) for item in all_problems))

    ui.end_subject()


async def run_once(session_factory: async_sessionmaker) -> None:
    client = AsyncSdamGIA(
        concurrency=settings.parser_concurrency,
        request_delay=settings.parser_request_delay,
    )
    ui = ParserUI()
    ui.start(total_subjects=len(SUBJECT_TO_SDAMGIA))
    try:
        # порядок предметов берём из bot.catalog — чтобы вывод был стабильный
        for subject_key, _label, _emoji in SUBJECTS:
            sdamgia_code = SUBJECT_TO_SDAMGIA.get(subject_key)
            if sdamgia_code is None:
                continue
            await _process_subject(
                client=client,
                session_factory=session_factory,
                subject_key=subject_key,
                subject_code=sdamgia_code,
                ui=ui,
            )
    finally:
        ui.stop()
