from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from parser.client import AsyncSdamGIA


def _make(retries: int = 2):
    return AsyncSdamGIA(concurrency=1, request_delay=0, retries=retries, retry_delay=0)


@pytest.mark.asyncio
async def test_run_succeeds_first_try():
    client = _make()
    fn = MagicMock(__name__="ok", return_value=42)
    result = await client._run(fn)
    assert result == 42
    assert fn.call_count == 1


@pytest.mark.asyncio
async def test_run_retries_then_succeeds():
    client = _make(retries=2)
    fn = MagicMock(__name__="flaky", side_effect=[RuntimeError("1"), RuntimeError("2"), "ok"])
    result = await client._run(fn)
    assert result == "ok"
    assert fn.call_count == 3


@pytest.mark.asyncio
async def test_run_raises_after_exhausting_retries():
    client = _make(retries=2)
    fn = MagicMock(__name__="bad", side_effect=RuntimeError("nope"))
    with pytest.raises(RuntimeError, match="nope"):
        await client._run(fn)
    assert fn.call_count == 3  # 1 первая + 2 ретрая
