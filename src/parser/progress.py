"""Live-прогресс парсинга через rich.

Три этажа в одной панели:
  шапка (текущий предмет + категория + общая статистика),
  бар по задачам внутри предмета (✓ ⏭ ✗ + ETA),
  бар по предметам (X/11).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text


@dataclass
class SubjectStats:
    fetched: int = 0
    skipped: int = 0
    errors: int = 0
    current_category: str = ""


@dataclass
class ParserUI:
    console: Console = field(default_factory=Console)
    overall_progress: Progress = field(init=False)
    subject_progress: Progress = field(init=False)
    live: Live = field(init=False)
    overall_task_id: int = field(init=False, default=-1)
    subject_task_id: int = field(init=False, default=-1)

    current_subject_label: str = ""
    stats: SubjectStats = field(default_factory=SubjectStats)

    def __post_init__(self) -> None:
        self.overall_progress = Progress(
            TextColumn("[bold cyan]Предметы[/]"),
            BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
            MofNCompleteColumn(),
            TextColumn("|"),
            TimeElapsedColumn(),
            console=self.console,
            expand=True,
        )
        self.subject_progress = Progress(
            SpinnerColumn(style="magenta"),
            TextColumn("[bold]{task.description}[/]"),
            BarColumn(bar_width=None, complete_style="magenta", finished_style="green"),
            MofNCompleteColumn(),
            TextColumn("[green]OK {task.fields[fetched]}[/]"),
            TextColumn("[yellow]SKIP {task.fields[skipped]}[/]"),
            TextColumn("[red]ERR {task.fields[errors]}[/]"),
            TextColumn("|"),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        )

    def start(self, total_subjects: int) -> None:
        self.overall_task_id = self.overall_progress.add_task(
            "subjects", total=total_subjects
        )
        self.live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=8,
            transient=False,
        )
        self.live.start()

    def stop(self) -> None:
        self.live.update(self._render())
        self.live.stop()

    def enter_subject(self, label: str) -> None:
        # сбор id по категориям не быстрый — зажигаем имя в шапке заранее,
        # чтобы не висеть с прочерком пока считаем total
        self.current_subject_label = label
        self.stats = SubjectStats()
        self._refresh()

    def begin_subject(self, label: str, total_problems: int) -> None:
        self.current_subject_label = label
        if self.subject_task_id != -1:
            self.subject_progress.remove_task(self.subject_task_id)
        self.subject_task_id = self.subject_progress.add_task(
            description=label,
            total=max(total_problems, 1),
            fetched=0,
            skipped=0,
            errors=0,
        )
        self._refresh()

    def end_subject(self) -> None:
        if self.subject_task_id != -1:
            self.subject_progress.update(
                self.subject_task_id,
                completed=self.subject_progress.tasks[self.subject_task_id].total,
            )
        self.overall_progress.advance(self.overall_task_id)
        self._refresh()

    def set_category(self, name: str) -> None:
        self.stats.current_category = name
        self._refresh()

    def tick_fetched(self) -> None:
        self.stats.fetched += 1
        self._tick()

    def tick_skipped(self) -> None:
        self.stats.skipped += 1
        self._tick()

    def tick_error(self) -> None:
        self.stats.errors += 1
        self._tick()

    def _tick(self) -> None:
        self.subject_progress.update(
            self.subject_task_id,
            advance=1,
            fetched=self.stats.fetched,
            skipped=self.stats.skipped,
            errors=self.stats.errors,
        )
        self._refresh()

    def _refresh(self) -> None:
        if hasattr(self, "live") and self.live.is_started:
            self.live.update(self._render())

    def _header(self) -> Table:
        table = Table.grid(expand=True)
        table.add_column(justify="left")
        table.add_column(justify="right")

        left = Text()
        left.append("SUBJECT ", style="bold")
        left.append(self.current_subject_label or "—", style="bold cyan")
        if self.stats.current_category:
            left.append("  |  ", style="dim")
            left.append(self.stats.current_category, style="white")

        right = Text()
        right.append(f"OK {self.stats.fetched} ", style="green")
        right.append(f"SKIP {self.stats.skipped} ", style="yellow")
        right.append(f"ERR {self.stats.errors}", style="red")

        table.add_row(left, right)
        return table

    def _render(self) -> Panel:
        body = Group(
            self._header(),
            Text(),
            self.subject_progress,
            self.overall_progress,
        )
        return Panel(
            body,
            title="[bold cyan]EGE Parser | SdamGIA -> Postgres[/]",
            border_style="cyan",
            box=box.SQUARE,
            padding=(0, 1),
        )
