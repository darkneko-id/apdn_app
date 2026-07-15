# src/tkdn_finder/charts.py
"""Pure-Python sparkline geometry for the year-count trend charts.

Templates must not contain layout math (see CLAUDE.md anti-patterns), so the
SVG polyline coordinates are computed here and handed to Jinja2 as plain data.
"""

from __future__ import annotations

import sqlite3

from .constants import (
    YEAR_TREND_CHART_HEIGHT,
    YEAR_TREND_CHART_PAD_X,
    YEAR_TREND_CHART_PAD_Y,
    YEAR_TREND_CHART_WIDTH,
)
from .models import YearTrendChart


def build_year_trend_chart(
    tahun: int,
    rows: list[sqlite3.Row],
    width: int = YEAR_TREND_CHART_WIDTH,
    height: int = YEAR_TREND_CHART_HEIGHT,
) -> YearTrendChart:
    """Build sparkline geometry for one year from ascending-date snapshot rows.

    `rows` must be ordered oldest-first (as returned by get_year_count_trends).
    """
    counts = [int(r["cert_count"]) for r in rows]
    current = counts[-1]
    delta = current - counts[-2] if len(counts) >= 2 else None
    min_count = min(counts)
    max_count = max(counts)

    pad_x, pad_y = YEAR_TREND_CHART_PAD_X, YEAR_TREND_CHART_PAD_Y
    plot_w = width - 2 * pad_x
    plot_h = height - 2 * pad_y

    def _x(i: int) -> float:
        if len(counts) == 1:
            return width / 2
        return pad_x + plot_w * i / (len(counts) - 1)

    def _y(count: int) -> float:
        if max_count == min_count:
            return height / 2
        # Invert: higher count → smaller y (closer to top of the SVG).
        return pad_y + plot_h * (1 - (count - min_count) / (max_count - min_count))

    xs = [_x(i) for i in range(len(counts))]
    ys = [_y(c) for c in counts]

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys)) if len(counts) >= 2 else ""

    return YearTrendChart(
        tahun=tahun,
        current=current,
        delta=delta,
        min_count=min_count,
        max_count=max_count,
        point_count=len(counts),
        polyline=polyline,
        last_x=xs[-1],
        last_y=ys[-1],
        width=width,
        height=height,
        first_date=str(rows[0]["snapshot_date"]) if rows else None,
        last_date=str(rows[-1]["snapshot_date"]) if rows else None,
    )
