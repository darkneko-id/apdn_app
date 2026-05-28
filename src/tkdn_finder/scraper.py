# src/tkdn_finder/scraper.py
"""Discover P3DN export download URLs by scraping the homepage."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .constants import (
    DEFAULT_USER_AGENT,
    EXPORT_LINK_HREF_PATTERN,
    SCRAPER_TIMEOUT_SECONDS,
    YEAR_EXTRACTION_PATTERN,
)

logger = logging.getLogger(__name__)


async def discover_download_urls(
    homepage_url: str,
    timeout: int = SCRAPER_TIMEOUT_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, str]:
    """Scrape the P3DN homepage to find export download URLs.

    Returns a dict mapping year string to full URL, e.g. {"2024": "https://...", "2025": "..."}.
    Raises ValueError if no export links are found.
    """
    headers = {"User-Agent": user_agent}
    logger.info("Scraping P3DN homepage for export links", extra={"url": homepage_url})

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(homepage_url, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    results: dict[str, str] = {}
    pattern = re.compile(EXPORT_LINK_HREF_PATTERN)
    year_pattern = re.compile(YEAR_EXTRACTION_PATTERN)

    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"]
        if not pattern.search(href):
            continue

        # Try to extract year from link text first, then href
        text = anchor.get_text(strip=True)
        year_match = year_pattern.search(text) or year_pattern.search(href)
        if not year_match:
            logger.debug("Export link found but no year extractable: %s", href)
            continue

        year = year_match.group(1)
        full_url = urljoin(homepage_url, href)
        results[year] = full_url
        logger.debug("Discovered export URL for year %s", year)

    if not results:
        raise ValueError(f"No export links found on P3DN homepage: {homepage_url}")

    logger.info(
        "Discovered %d export URLs: years=%s",
        len(results),
        list(results.keys()),
    )
    return results


async def discover_with_fallback(
    homepage_url: str,
    cached_urls: dict[str, str],
    timeout: int = SCRAPER_TIMEOUT_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, str]:
    """Try to discover URLs; fall back to cached URLs on any error.

    Raises ValueError if no discovered and no cached URLs are available.
    """
    try:
        return await discover_download_urls(homepage_url, timeout=timeout, user_agent=user_agent)
    except Exception as exc:
        logger.warning(
            "Failed to discover export URLs, using cache",
            extra={"error": str(exc)},
        )
        if cached_urls:
            logger.info("Using %d cached URLs", len(cached_urls))
            return cached_urls
        raise ValueError("No export URLs discovered and no cache available") from exc
