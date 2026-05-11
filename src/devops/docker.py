"""Тонкая обёртка над `docker compose` — async, без сторонних либ.

Используем CLI вместо docker SDK сознательно: SDK тащит requests + кучу
зависимостей и не понимает compose-проектов из коробки. CLI — то что
бот, парсер и api запускают в проде, и тут мы дёргаем ровно его же.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE_CMD: tuple[str, ...] | None = None


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
    global _COMPOSE_CMD
    if _COMPOSE_CMD is None:
        if shutil.which("docker-compose"):
            _COMPOSE_CMD = ("docker-compose",)
        else:
            _COMPOSE_CMD = ("docker", "compose")

    async def _run(cmd: tuple[str, ...]) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, *args,
            cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )

    code, out, err = await _run(_COMPOSE_CMD)
    # If docker exists but compose plugin is missing, retry with docker-compose.
    if (
        code != 0
        and _COMPOSE_CMD == ("docker", "compose")
        and shutil.which("docker-compose")
        and ("is not a docker command" in err.lower() or "unknown command" in err.lower())
    ):
        _COMPOSE_CMD = ("docker-compose",)
        return await _run(_COMPOSE_CMD)

    return code, out, err


async def list_services() -> list[str]:
    code, out, _ = await _compose("config", "--services")
    if code == 0:
        services = [line.strip() for line in out.splitlines() if line.strip()]
        if services:
            return services

    # fallback: some compose/plugin versions fail on `config --services`
    # while `ps --services` still works.
    code, out, _ = await _compose("ps", "--services")
    if code == 0:
        return [line.strip() for line in out.splitlines() if line.strip()]
    return []


async def _docker_inspect(container_id: str) -> tuple[str, str | None]:
    """Return (state, health) from docker inspect. Unknowns -> ('stopped', None)."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "inspect",
        "--format",
        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
        container_id,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return "stopped", None
    raw = stdout.decode(errors="replace").strip()
    if not raw:
        return "stopped", None
    state, _, health = raw.partition("|")
    return (state.strip().lower() or "stopped"), (health.strip().lower() or None)


async def status_all() -> list[ServiceStatus]:
    """Все сервисы из compose-файла + их актуальный статус.

    `ps` показывает только созданные контейнеры — мерджим с `config --services`
    чтобы остановленные тоже были в списке (можно нажать start).
    """
    declared = await list_services()
    # Cross-version path compatible with docker compose plugin and legacy docker-compose:
    # resolve container IDs per service, then inspect via plain docker.
    statuses: list[ServiceStatus] = []
    for service in declared:
        code, out, _ = await _compose("ps", "-q", service)
        container_id = out.strip() if code == 0 else ""
        if not container_id:
            statuses.append(
                ServiceStatus(name=service, state="stopped", health=None, container_id=None)
            )
            continue

        state, health = await _docker_inspect(container_id)
        statuses.append(
            ServiceStatus(
                name=service,
                state=state,
                health=health,
                container_id=container_id,
            )
        )

    return statuses


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
    global _COMPOSE_CMD
    if _COMPOSE_CMD is None:
        if shutil.which("docker-compose"):
            _COMPOSE_CMD = ("docker-compose",)
        else:
            _COMPOSE_CMD = ("docker", "compose")

    proc = await asyncio.create_subprocess_exec(
        *_COMPOSE_CMD, "logs", "--no-color", "-f", "--tail", str(tail), service,
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
