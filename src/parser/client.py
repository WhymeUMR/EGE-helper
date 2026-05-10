"""Async-обёртка над синхронным sdamgia.SdamGIA.

Либа архивирована и сидит на requests, поэтому каждый вызов кидаем в
to_thread + держим семафор и небольшие паузы, чтобы не словить бан.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

from sdamgia import SdamGIA  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncSdamGIA:
    def __init__(
        self,
        concurrency: int = 4,
        request_delay: float = 0.15,
        retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        self._client = SdamGIA()
        self._sem = asyncio.Semaphore(concurrency)
        self._delay = request_delay
        self._retries = retries
        self._retry_delay = retry_delay

    async def _run(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            async with self._sem:
                await asyncio.sleep(self._delay)
                try:
                    return await asyncio.to_thread(fn, *args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning(
                        "sdamgia call failed (%s, attempt %d/%d): %s",
                        fn.__name__, attempt + 1, self._retries + 1, exc,
                    )
                    if attempt < self._retries:
                        await asyncio.sleep(self._retry_delay * (attempt + 1))
        assert last_error is not None
        raise last_error

    async def get_catalog(self, subject_code: str) -> list[dict[str, Any]]:
        return await self._run(self._client.get_catalog, subject_code)

    async def get_category(
        self, subject_code: str, category_id: str, page: int = 1
    ) -> list[str]:
        return await self._run(
            self._client.get_category_by_id, subject_code, category_id, page
        )

    async def get_problem(
        self, subject_code: str, problem_id: str
    ) -> dict[str, Any] | None:
        return await self._run(
            self._client.get_problem_by_id, subject_code, problem_id
        )
