from __future__ import annotations

from typing import Any

import pytest

from parser.service import _collect_category_ids


class FakeClient:
    def __init__(self, pages: list[list[str]]):
        self._pages = pages
        self.calls: list[int] = []

    async def get_category(self, subject: str, cat_id: str, page: int = 1) -> list[str]:
        self.calls.append(page)
        idx = page - 1
        if idx >= len(self._pages):
            return []
        return self._pages[idx]


@pytest.mark.asyncio
async def test_collect_stops_on_empty_page():
    client = FakeClient([["1", "2", "3"], ["4", "5"], []])
    ids = await _collect_category_ids(client, "math", "42", max_pages=10)
    assert ids == ["1", "2", "3", "4", "5"]
    assert client.calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_stops_on_repeated_page():
    # после реальной последней страницы sdamgia любит вернуть её копию вместо 404
    client = FakeClient([["1", "2"], ["3", "4"], ["3", "4"], ["3", "4"]])
    ids = await _collect_category_ids(client, "math", "42", max_pages=10)
    assert ids == ["1", "2", "3", "4"]
    assert client.calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_dedupes_within_page():
    client = FakeClient([["1", "1", "2", "2", "3"]])
    ids = await _collect_category_ids(client, "math", "42", max_pages=10)
    assert ids == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_collect_respects_max_pages():
    pages = [[f"{i*10+j}" for j in range(5)] for i in range(20)]
    client = FakeClient(pages)
    ids = await _collect_category_ids(client, "math", "42", max_pages=3)
    assert len(ids) == 15
    assert client.calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_swallows_network_error():
    class ErrorClient:
        async def get_category(self, *args: Any, **kwargs: Any) -> list[str]:
            raise ConnectionError("boom")

    ids = await _collect_category_ids(ErrorClient(), "math", "42", max_pages=10)
    assert ids == []
