from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback


def setup_logging(level: int = logging.INFO) -> None:
    console = Console(force_terminal=True)
    install_rich_traceback(console=console, show_locals=False)

    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_path=False,
        log_time_format="[%X]",
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[handler],
        force=True,
    )

    # глушим разговорчивые библиотеки — на INFO/DEBUG они валят простыни
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
