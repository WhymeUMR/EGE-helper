"""Визуал прогресса онбординга: бар (▰▰▱) и шапка шага"""

from __future__ import annotations

TOTAL_ONBOARDING_STEPS = 3


def progress_bar(step: int, total: int = TOTAL_ONBOARDING_STEPS) -> str:
    """`▰▰▱` — закрашенный и пустой сегменты по числу пройденных шагов"""
    # клампим step в [0, total] — на случай если откуда-то прилетит число побольше
    step = max(0, min(step, total))
    return "▰" * step + "▱" * (total - step)


def step_header(step: int, title: str, icon: str) -> str:
    """шапка шага в HTML: `🎓 Шаг 1 из 3 — Класс  ▰▱▱`"""
    return (
        f"{icon} <b>Шаг {step} из {TOTAL_ONBOARDING_STEPS} — {title}</b>  "
        f"{progress_bar(step)}"
    )
