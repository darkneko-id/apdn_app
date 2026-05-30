# src/tkdn_finder/refresh_state.py
"""Module-level refresh progress state. Safe for single-process asyncio use."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RefreshState:
    running: bool = False
    stage: str = ""
    percent: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    rows_ingested: int = 0
    years_total: int = 0
    years_done: int = 0


_state = RefreshState()


def get_state() -> RefreshState:
    return _state


def begin() -> None:
    """Mark as running immediately (call before first await in the job)."""
    _state.running = True
    _state.stage = "Mencari tautan unduhan..."
    _state.percent = 5
    _state.error = None
    _state.started_at = datetime.now()
    _state.finished_at = None
    _state.rows_ingested = 0
    _state.years_total = 0
    _state.years_done = 0


def start(years_total: int) -> None:
    """Called after URL discovery — update year count."""
    _state.years_total = years_total


def set_stage(stage: str, percent: int) -> None:
    _state.stage = stage
    _state.percent = percent


def year_done(rows: int) -> None:
    _state.years_done += 1
    _state.rows_ingested += rows
    _state.percent = 10 + (_state.years_done * 90 // max(_state.years_total, 1))


def finish() -> None:
    _state.running = False
    _state.stage = "Selesai"
    _state.percent = 100
    _state.finished_at = datetime.now()


def fail(message: str) -> None:
    _state.running = False
    _state.error = message
    _state.finished_at = datetime.now()
