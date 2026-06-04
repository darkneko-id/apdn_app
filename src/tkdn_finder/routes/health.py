# src/tkdn_finder/routes/health.py
"""Health check and metrics routes."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ..config import get_settings
from ..db import get_connection, get_stats

logger = logging.getLogger(__name__)
router = APIRouter()

_start_time = time.time()


def _get_stats_sync(db_path: str) -> dict[str, object]:
    conn = get_connection(db_path)
    try:
        return get_stats(conn)
    finally:
        conn.close()


@router.get("/health")
async def health() -> dict[str, object]:
    """Check application health including DB connectivity."""
    settings = get_settings()
    db_ok = False
    total_rows = 0
    try:
        conn = get_connection(settings.get_db_path())
        total_rows = conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]
        conn.close()
        db_ok = True
    except Exception as exc:
        logger.warning("Health check DB error: %s", exc)

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "total_rows": total_rows,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    """Expose basic Prometheus-format metrics."""
    settings = get_settings()
    try:
        stats = await asyncio.to_thread(_get_stats_sync, settings.get_db_path())
        total = stats["total_rows"]
    except Exception:
        total = 0

    uptime = round(time.time() - _start_time, 1)
    lines = [
        "# HELP tkdn_certificate_total Total number of TKDN certificates in database",
        "# TYPE tkdn_certificate_total gauge",
        f"tkdn_certificate_total {total}",
        "# HELP tkdn_app_uptime_seconds Application uptime in seconds",
        "# TYPE tkdn_app_uptime_seconds gauge",
        f"tkdn_app_uptime_seconds {uptime}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n")
