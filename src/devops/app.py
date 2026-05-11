"""TUI для управления стеком: статус сервисов, статистика БД, live-логи через VT100."""

from __future__ import annotations

import asyncio
import re
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static

from devops import docker, stats
from devops.terminal import TerminalView


CSS = """
Screen { layout: vertical; }

#top {
    height: 13;
}

#services-panel {
    width: 50%;
    border: round cyan;
    padding: 0 1;
}

#stats-panel {
    width: 50%;
    border: round magenta;
    padding: 0 2;
}

#logs-panel {
    height: 1fr;
    border: round green;
    padding: 0;
}

DataTable { height: 1fr; }
DataTable > .datatable--cursor { background: $primary 30%; }
"""

REFRESH_STATUS_SEC = 3.0
REFRESH_STATS_SEC = 9.0

# `parser  | content` — префикс docker compose; снимаем перед скармливанием pyte
DOCKER_LOG_PREFIX = re.compile(r"^[\w-]+\s*\|\s?")


class StatsView(Static):
    data: reactive[stats.Stats | None] = reactive(None)

    def render(self) -> Text:
        out = Text()
        if self.data is None:
            out.append("postgres недоступна", style="red")
            return out

        out.append("problems   ", style="dim")
        out.append(f"{self.data.total_problems}\n", style="bold cyan")
        for subj, n in self.data.by_subject:
            out.append(f"  {subj:<12}", style="dim")
            out.append(f"{n}\n")
        if not self.data.by_subject:
            out.append("  (пусто)\n", style="dim")
        out.append("\nusers      ", style="dim")
        out.append(f"{self.data.users}\n", style="bold cyan")
        out.append("\napi        ", style="dim")
        out.append("http://localhost:8000/docs", style="cyan")
        return out


class ServicesTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.show_header = False
        self.add_columns(" ", "service", "status")

    def update_rows(self, services: list[docker.ServiceStatus]) -> None:
        prev = None
        if self.row_count and self.cursor_row < self.row_count:
            try:
                prev = self.get_row_at(self.cursor_row)[1].plain
            except Exception:  # noqa: BLE001
                prev = None

        self.clear()
        for svc in services:
            self.add_row(
                self._dot(svc),
                Text(svc.name, style="bold"),
                Text(svc.display, style=self._status_style(svc)),
                key=svc.name,
            )

        if prev is not None:
            for idx, svc in enumerate(services):
                if svc.name == prev:
                    self.move_cursor(row=idx)
                    break

    @staticmethod
    def _dot(svc: docker.ServiceStatus) -> Text:
        if svc.health == "healthy" or (svc.is_up and svc.health is None):
            return Text("●", style="green")
        if svc.state in {"starting", "created"} or svc.health == "starting":
            return Text("●", style="yellow")
        if svc.health == "unhealthy":
            return Text("●", style="red")
        return Text("○", style="dim")

    @staticmethod
    def _status_style(svc: docker.ServiceStatus) -> str:
        if svc.health == "healthy" or (svc.is_up and svc.health is None):
            return "green"
        if svc.health == "starting" or svc.state == "created":
            return "yellow"
        if svc.health == "unhealthy" or svc.state == "exited":
            return "red"
        return "dim"


class ControlCenter(App):
    CSS = CSS
    TITLE = "EGE Helper"

    BINDINGS: ClassVar = [
        Binding("s", "service('start')", "start"),
        Binding("x", "service('stop')", "stop"),
        Binding("r", "service('restart')", "restart"),
        Binding("l", "follow_logs", "logs"),
        Binding("u", "up_all", "up"),
        Binding("d", "down_all", "down"),
        Binding("R", "refresh_now", "refresh"),
        Binding("q", "quit", "quit"),
    ]

    services: reactive[list[docker.ServiceStatus]] = reactive(list)
    follow_target: reactive[str | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        self._log_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            with Vertical(id="services-panel"):
                yield Static("[bold cyan]Services[/]", markup=True)
                yield ServicesTable(id="services-table")
            with Vertical(id="stats-panel"):
                yield Static("[bold magenta]Stats[/]\n", markup=True)
                yield StatsView(id="stats")
        yield TerminalView(id="logs-panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.set_interval(REFRESH_STATUS_SEC, self._refresh_status)
        self.set_interval(REFRESH_STATS_SEC, self._refresh_stats)
        await self._refresh_status()
        await self._refresh_stats()
        self.query_one(TerminalView).feed_line(
            "select service and press 'l' to follow logs"
        )

    async def _refresh_status(self) -> None:
        services = await docker.status_all()
        self.services = services
        self.query_one(ServicesTable).update_rows(services)
        self._update_logs_title()

    async def _refresh_stats(self) -> None:
        self.query_one(StatsView).data = await stats.fetch_stats()

    def _update_logs_title(self) -> None:
        panel = self.query_one("#logs-panel", TerminalView)
        target = self.follow_target or "—"
        panel.border_title = f"[bold green] Logs · {target} [/]"

    def _selected_service(self) -> str | None:
        table = self.query_one(ServicesTable)
        if not table.row_count:
            return None
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
            return row_key.value
        except Exception:  # noqa: BLE001
            return None

    async def action_service(self, op: str) -> None:
        svc = self._selected_service()
        if not svc:
            self.notify("выбери сервис", severity="warning")
            return
        ops = {"start": docker.start, "stop": docker.stop, "restart": docker.restart}
        code, msg = await ops[op](svc)
        if code == 0:
            self.notify(f"{op} {svc} ok")
        else:
            first = msg.splitlines()[0] if msg else str(code)
            self.notify(f"{op} {svc} failed: {first}", severity="error", timeout=8)
        await self._refresh_status()

    async def action_up_all(self) -> None:
        self.notify("docker compose up -d --build…")
        code, msg = await docker.up_all()
        self.notify(
            "up all ok" if code == 0 else f"up all failed: {msg}",
            severity="error" if code else "information",
        )
        await self._refresh_status()
        await self._refresh_stats()

    async def action_down_all(self) -> None:
        self.notify("docker compose down…")
        code, msg = await docker.down_all()
        self.notify(
            "down all ok" if code == 0 else f"down all failed: {msg}",
            severity="error" if code else "information",
        )
        await self._refresh_status()

    async def action_refresh_now(self) -> None:
        await self._refresh_status()
        await self._refresh_stats()

    async def action_follow_logs(self) -> None:
        svc = self._selected_service()
        if not svc:
            self.notify("выбери сервис", severity="warning")
            return

        if self._log_task is not None:
            self._log_task.cancel()
            try:
                await self._log_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

        self.follow_target = svc
        self._update_logs_title()
        terminal = self.query_one(TerminalView)
        terminal.reset_terminal()
        self._log_task = asyncio.create_task(self._stream(svc))

    async def _stream(self, svc: str) -> None:
        terminal = self.query_one(TerminalView)
        try:
            if svc == "parser":
                # parser emits a live VT stream (rich.Live); feed raw chunks
                # so cursor movement and line erases are preserved correctly.
                # Start from fresh output; tailing old lines may attach to the
                # middle of an already drawn frame and break panel borders.
                async for chunk in docker.stream_logs_raw(svc, tail=0):
                    terminal.feed(chunk)
                return

            async for line in docker.stream_logs(svc, tail=80):
                # снимаем `parser  | ` префикс — пусть pyte видит чистый поток
                payload = DOCKER_LOG_PREFIX.sub("", line)
                terminal.feed_line(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            terminal.feed_line(f"[stream stopped: {exc}]")


def main() -> None:
    ControlCenter().run()


if __name__ == "__main__":
    main()
