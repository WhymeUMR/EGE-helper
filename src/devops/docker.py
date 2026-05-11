"""Тонкая обёртка над `docker compose` — async, без сторонних либ.

Используем CLI вместо docker SDK сознательно: SDK тащит requests + кучу
зависимостей и не понимает compose-проектов из коробки. CLI — то что
бот, парсер и api запускают в проде, и тут мы дёргаем ровно его же.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    state: str           # running / exited / created / paused / dead / —
    health: str | None   # healthy / starting / unhealthy / None
    container_id: str | None

    @property
    def is_up(self) -> bool:
        return self.state == "running"

    @property
    def display(self) -> str:
        if self.health == "healthy":
            return "healthy"
        if self.health == "starting":
            return "starting"
        if self.health == "unhealthy":
            return "unhealthy"
        return self.state or "—"


async def _compose(*args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", *args,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


async def list_services() -> list[str]:
    code, out, _ = await _compose("config", "--services")
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


async def status_all() -> list[ServiceStatus]:
    """Все сервисы из compose-файла + их актуальный статус.

    `ps` показывает только созданные контейнеры — мерджим с `config --services`
    чтобы остановленные тоже были в списке (можно нажать start).
    """
    declared = await list_services()
    code, out, _ = await _compose("ps", "-a", "--format", "json")
    seen: dict[str, ServiceStatus] = {}
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = row.get("Service") or row.get("Name") or ""
            seen[name] = ServiceStatus(
                name=name,
                state=(row.get("State") or "").lower(),
                health=(row.get("Health") or None) or None,
                container_id=row.get("ID") or None,
            )

    return [
        seen.get(name, ServiceStatus(name=name, state="stopped", health=None, container_id=None))
        for name in declared
    ]


async def start(service: str) -> tuple[int, str]:
    code, out, err = await _compose("up", "-d", service)
    return code, (err or out).strip()


async def stop(service: str) -> tuple[int, str]:
    code, out, err = await _compose("stop", service)
    return code, (err or out).strip()


async def restart(service: str) -> tuple[int, str]:
    code, out, err = await _compose("restart", service)
    return code, (err or out).strip()


async def up_all() -> tuple[int, str]:
    code, out, err = await _compose("up", "-d", "--build")
    return code, (err or out).strip()


async def down_all() -> tuple[int, str]:
    code, out, err = await _compose("down")
    return code, (err or out).strip()


async def stream_logs(service: str, tail: int = 80) -> AsyncIterator[str]:
    """Стримим `docker compose logs -f` строка за строкой.

    Прерывание делаем через CancelledError на стороне вызывающего: когда
    юзер переключает сервис, отменяем итератор и subprocess получает SIGTERM.
    """
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "logs", "--no-color", "-f", "--tail", str(tail), service,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    try:
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            yield raw.decode(errors="replace").rstrip("\n")
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                proc.kill()
