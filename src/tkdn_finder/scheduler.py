# src/tkdn_finder/scheduler.py
"""APScheduler setup and the refresh_all_years job."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def refresh_all_years(settings: object, db_path: str) -> None:
    """Download, parse, and ingest all available TKDN year datasets.

    Never raises. All errors are logged and persisted to download_run.
    """
    from .config import Settings
    from .db import get_cached_urls, get_connection, save_download_run
    from .downloader import download_file
    from .merger import merge_and_upsert
    from .parser import parse_html_export
    from .scraper import discover_with_fallback

    assert isinstance(settings, Settings)

    conn = get_connection(db_path)
    cached_urls = get_cached_urls(conn)
    conn.close()

    try:
        urls = await discover_with_fallback(
            settings.p3dn.homepage_url,
            cached_urls,
            timeout=settings.p3dn.download_timeout_seconds,
            user_agent=settings.p3dn.user_agent,
            verify_ssl=settings.p3dn.verify_ssl,
        )
    except Exception as exc:
        logger.exception("Cannot get any download URLs, aborting refresh", extra={"error": str(exc)})
        return

    logger.info("Starting refresh for years: %s", list(urls.keys()))

    for idx, (year, url) in enumerate(urls.items()):
        if idx > 0:
            await asyncio.sleep(5)  # stagger to avoid hammering P3DN

        started_at = datetime.now(timezone.utc)
        conn = get_connection(db_path)
        try:
            raw_dir = settings.get_raw_dir()
            file_path = await download_file(
                url=url,
                year=year,
                raw_dir=raw_dir,
                timeout=settings.p3dn.download_timeout_seconds,
                max_retries=settings.p3dn.retry_count,
                user_agent=settings.p3dn.user_agent,
                verify_ssl=settings.p3dn.verify_ssl,
            )
            rows = parse_html_export(file_path, year)
            stats = merge_and_upsert(conn, rows)
            finished_at = datetime.now(timezone.utc)
            save_download_run(
                conn,
                year=year,
                url=url,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                row_count=len(rows),
            )
            logger.info(
                "Refresh success: year=%s rows=%d inserted=%d",
                year,
                len(rows),
                stats.get("inserted", 0),
            )
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            logger.exception(
                "Refresh failed for year=%s", year, extra={"error": str(exc)}
            )
            try:
                save_download_run(
                    conn,
                    year=year,
                    url=url,
                    status="failure",
                    started_at=started_at,
                    finished_at=finished_at,
                    error_message=str(exc),
                )
            except Exception as save_exc:
                logger.exception(
                    "Could not save download run failure record",
                    extra={"error": str(save_exc)},
                )
        finally:
            conn.close()


def create_scheduler(settings: object, db_path: str) -> AsyncIOScheduler:
    """Create and configure an AsyncIOScheduler with the refresh job.

    The cron expression comes from settings.schedule.cron.
    """
    from .config import Settings

    assert isinstance(settings, Settings)

    scheduler = AsyncIOScheduler()
    cron_parts = settings.schedule.cron.split()
    if len(cron_parts) == 5:
        minute, hour, day, month, day_of_week = cron_parts
    else:
        minute, hour, day, month, day_of_week = "0", "2", "*", "*", "*"
        logger.warning(
            "Invalid cron expression %r, using default 02:00 daily",
            settings.schedule.cron,
        )

    scheduler.add_job(
        refresh_all_years,
        trigger="cron",
        args=[settings, db_path],
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        id="refresh_all_years",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    logger.info("Scheduler configured with cron=%r", settings.schedule.cron)
    return scheduler
