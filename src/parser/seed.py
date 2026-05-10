"""Импорт seed-дампа задач из GitHub Releases при пустой БД.

Парсить с нуля долго, поэтому свежий `pg_dump --data-only` лежит на
Releases, а сервис на пустой problems его подтягивает и разворачивает
через psql (asyncpg плохо ест COPY-скрипты от pg_dump).
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.models import Problem
from parser.config import ParserSettings

logger = logging.getLogger(__name__)


async def _table_is_empty(session_factory: async_sessionmaker) -> bool:
    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(Problem))
        return (result.scalar() or 0) == 0


async def _download(url: str, dest: Path) -> None:
    logger.info("downloading seed dump from %s", url)
    await asyncio.to_thread(urllib.request.urlretrieve, url, str(dest))
    size_mb = dest.stat().st_size / 1024 / 1024
    logger.info("seed downloaded: %.1f MB", size_mb)


async def _restore_with_psql(dump_path: Path, settings: ParserSettings) -> None:
    # gunzip pipe в psql — не пишем распакованный sql на диск.
    # PGPASSWORD через env, чтобы не светить пароль в `ps`.
    cmd = (
        f"gunzip -c {dump_path} | "
        f"psql -v ON_ERROR_STOP=1 "
        f"-h {settings.postgres_host} "
        f"-p {settings.postgres_port} "
        f"-U {settings.postgres_user} "
        f"-d {settings.postgres_db}"
    )
    env = {**os.environ, "PGPASSWORD": settings.postgres_password}
    proc = await asyncio.create_subprocess_shell(
        cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"psql restore failed (exit {proc.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )
    logger.info("seed restored via psql")


async def import_if_empty(
    session_factory: async_sessionmaker, settings: ParserSettings
) -> bool:
    """True если импортировали, False если пропустили.

    Любая ошибка логируется и глотается — парсер дальше пойдёт обычным
    путём, не валясь из-за недоступного seed-сервера.
    """
    if not settings.parser_seed_url:
        logger.info("PARSER_SEED_URL not set — skipping seed import")
        return False
    if not await _table_is_empty(session_factory):
        logger.info("problems table is not empty — skipping seed import")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        dump_path = Path(tmpdir) / "problems.sql.gz"
        try:
            await _download(settings.parser_seed_url, dump_path)
            await _restore_with_psql(dump_path, settings)
        except Exception:  # noqa: BLE001
            logger.exception("seed import failed; continuing with empty DB")
            return False

    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(Problem))
        count = result.scalar() or 0
    logger.info("seed import done: %d problems in DB", count)
    return True
