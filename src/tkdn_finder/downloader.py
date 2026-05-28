# src/tkdn_finder/downloader.py
"""Download P3DN HTML export files with retry and deduplication."""

from __future__ import annotations

import asyncio
import glob
import hashlib
import logging
import os
import time

import httpx

from .constants import (
    DEFAULT_USER_AGENT,
    DOWNLOAD_RETRY_BACKOFF_SECONDS,
    DOWNLOAD_RETRY_COUNT,
    DOWNLOAD_TIMEOUT_SECONDS,
    RAW_RETENTION_COUNT,
)

logger = logging.getLogger(__name__)


def _md5_file(path: str) -> str:
    """Return MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _prune_old_files(raw_dir: str, year: str, keep: int = RAW_RETENTION_COUNT) -> None:
    """Keep only the last `keep` rotated backups for a given year."""
    pattern = os.path.join(raw_dir, f"tkdn_{year}_*.html")
    old_files = sorted(glob.glob(pattern))
    for path in old_files[:-keep]:
        try:
            os.remove(path)
            logger.debug("Pruned old file: %s", path)
        except OSError as exc:
            logger.warning("Could not prune file %s: %s", path, exc)


async def download_file(
    url: str,
    year: str,
    raw_dir: str,
    timeout: int = DOWNLOAD_TIMEOUT_SECONDS,
    max_retries: int = DOWNLOAD_RETRY_COUNT,
    user_agent: str = DEFAULT_USER_AGENT,
    verify_ssl: bool = True,
) -> str:
    """Download a P3DN export file to raw_dir/tkdn_{year}.html.

    Uses hash-based change detection to skip unchanged files.
    Retries on failure with exponential backoff.
    Returns the file path.
    """
    os.makedirs(raw_dir, exist_ok=True)
    dest_path = os.path.join(raw_dir, f"tkdn_{year}.html")
    headers = {"User-Agent": user_agent}

    # Redact year token from logs
    safe_url = url.split("?")[0] + "?[redacted]" if "?" in url else url

    if not verify_ssl:
        logger.warning("TLS verification disabled for downloader year=%s — MITM risk accepted via config", year)
    logger.info("Starting download for year=%s url=%s", year, safe_url)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, verify=verify_ssl) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                content = response.content

            new_md5 = hashlib.md5(content).hexdigest()

            # Check existing file for change
            if os.path.exists(dest_path):
                old_md5 = _md5_file(dest_path)
                if old_md5 == new_md5:
                    logger.info(
                        "Download unchanged for year=%s (md5=%s), skipping",
                        year,
                        new_md5[:8],
                    )
                    return dest_path

                # Rotate old file before overwriting
                rotated = dest_path.replace(".html", f"_{int(time.time())}.html")
                os.rename(dest_path, rotated)
                _prune_old_files(raw_dir, year)

            with open(dest_path, "wb") as f:
                f.write(content)

            logger.info(
                "Download complete for year=%s size=%d md5=%s",
                year,
                len(content),
                new_md5[:8],
            )
            return dest_path

        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            last_exc = exc
            if attempt < max_retries:
                backoff = DOWNLOAD_RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    "Download attempt %d/%d failed for year=%s, retrying in %ds: %s",
                    attempt,
                    max_retries,
                    year,
                    backoff,
                    exc,
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "Download failed for year=%s after %d attempts",
                    year,
                    max_retries,
                    extra={"error": str(exc)},
                )

    raise RuntimeError(f"Download failed for year={year} after {max_retries} attempts") from last_exc
