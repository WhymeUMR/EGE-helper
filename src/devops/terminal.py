"""TerminalView: Textual-виджет поверх pyte (VT100-эмулятор).

Зачем нужен: парсер использует rich.live.Live, который в обычном TTY перерисовывает
экран через `\\x1b[1A`/`\\x1b[2K`. В `docker compose logs` эти escape-коды просто
накапливаются текстом — кадр не «обновляется», а «спамится». pyte интерпретирует
их как настоящий терминал, поэтому мы видим один актуальный кадр + историю.

Для сервисов без Live UI (api, bot) поведение тоже корректное — они просто пишут
строки, screen скроллится, ничего лишнего.
"""

from __future__ import annotations

import re

import pyte
from rich.text import Text
from textual.widget import Widget


# pyte-цвета → rich-цвета. Имена в основном совпадают, но есть пара отличий
PYTE_COLOR_MAP = {
    "default": None,
    "black": "black",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "brown": "yellow",
    "brightblack": "bright_black",
    "brightred": "bright_red",
    "brightgreen": "bright_green",
    "brightyellow": "bright_yellow",
    "brightblue": "bright_blue",
    "brightmagenta": "bright_magenta",
    "brightcyan": "bright_cyan",
    "brightwhite": "bright_white",
}


_HEX = re.compile(r"^[0-9a-fA-F]{6}$")


def _color(value: str | None) -> str | None:
    """pyte отдаёт либо имя ('red'), либо hex без префикса ('3a3a3a').
    Rich первое понимает, второе — только с `#`. Нормализуем."""
    if not value or value == "default":
        return None
    mapped = PYTE_COLOR_MAP.get(value)
    if mapped is not None:
        return mapped
    if _HEX.match(value):
        return f"#{value}"
    return value


def _cell_style(cell: pyte.screens.Char) -> str | None:
    parts: list[str] = []
    fg = _color(cell.fg)
    bg = _color(cell.bg)
    if fg:
        parts.append(fg)
    if bg:
        parts.append(f"on {bg}")
    if cell.bold:
        parts.append("bold")
    if cell.italics:
        parts.append("italic")
    if cell.underscore:
        parts.append("underline")
    if cell.reverse:
        parts.append("reverse")
    return " ".join(parts) if parts else None


class TerminalView(Widget):
    DEFAULT_CSS = """
    TerminalView {
        background: $surface;
        color: $text;
        overflow: hidden;
    }
    """

    def __init__(self, *args, cols: int = 200, rows: int = 60, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._screen = pyte.HistoryScreen(cols, rows, history=2000, ratio=0.5)
        self._stream = pyte.Stream(self._screen)

    def _resize_to_viewport(self) -> None:
        # Keep VT grid in sync with actual widget size, otherwise rich frames
        # may look cut off or uneven when terminal/UI dimensions differ.
        cols = max(1, self.size.width)
        rows = max(1, self.size.height)
        if cols != self._screen.columns or rows != self._screen.lines:
            self._screen.resize(lines=rows, columns=cols)

    def feed(self, data: str) -> None:
        self._stream.feed(data)
        self.refresh()

    def feed_line(self, line: str) -> None:
        self.feed(line + "\r\n")

    def reset_terminal(self) -> None:
        self._screen.reset()
        self.refresh()

    def render(self) -> Text:
        self._resize_to_viewport()
        out = Text()
        screen = self._screen
        for y in range(screen.lines):
            line = screen.buffer[y]
            for x in range(screen.columns):
                cell = line[x]
                out.append(cell.data or " ", style=_cell_style(cell))
            out.append("\n")
        return out
