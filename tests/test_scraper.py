# tests/test_scraper.py
"""Tests for the P3DN URL scraper."""

from __future__ import annotations

import pytest
import respx
import httpx

from tkdn_finder.scraper import discover_download_urls, discover_with_fallback


HOMEPAGE_URL = "https://p3dn.kemenperin.go.id/"

MOCK_HTML_VALID = """
<html><body>
<a href="/export_excel.php?thn=ABC123" class="btn btn-primary">
    <i class="fa fa-download"></i> Download TKDN LVI 2024
</a>
<a href="/export_excel.php?thn=DEF456" class="btn btn-primary">
    Download TKDN LVI 2025
</a>
<a href="/export_excel.php?thn=GHI789" class="btn btn-primary">
    Download TKDN LVI 2026
</a>
</body></html>
"""

MOCK_HTML_NO_LINKS = "<html><body><p>Tidak ada data.</p></body></html>"

MOCK_HTML_MISSING_YEAR = """
<html><body>
<a href="/export_excel.php?thn=XYZ" class="btn">Download Data</a>
</body></html>
"""


@pytest.mark.asyncio
async def test_discover_urls_happy_path():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(
            return_value=httpx.Response(200, text=MOCK_HTML_VALID)
        )
        urls = await discover_download_urls(HOMEPAGE_URL)

    assert len(urls) == 3
    assert "2024" in urls
    assert "2025" in urls
    assert "2026" in urls
    assert "export_excel.php" in urls["2024"]
    assert "ABC123" in urls["2024"]


@pytest.mark.asyncio
async def test_discover_urls_builds_full_url():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(
            return_value=httpx.Response(200, text=MOCK_HTML_VALID)
        )
        urls = await discover_download_urls(HOMEPAGE_URL)

    # Relative href should be joined to base URL
    assert urls["2024"].startswith("https://p3dn.kemenperin.go.id")


@pytest.mark.asyncio
async def test_discover_urls_raises_if_no_links():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(
            return_value=httpx.Response(200, text=MOCK_HTML_NO_LINKS)
        )
        with pytest.raises(ValueError, match="No export links found"):
            await discover_download_urls(HOMEPAGE_URL)


@pytest.mark.asyncio
async def test_discover_urls_skips_links_without_year():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(
            return_value=httpx.Response(200, text=MOCK_HTML_MISSING_YEAR)
        )
        with pytest.raises(ValueError, match="No export links found"):
            await discover_download_urls(HOMEPAGE_URL)


@pytest.mark.asyncio
async def test_discover_urls_raises_on_http_error():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(httpx.HTTPStatusError):
            await discover_download_urls(HOMEPAGE_URL)


@pytest.mark.asyncio
async def test_discover_with_fallback_returns_discovered():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(
            return_value=httpx.Response(200, text=MOCK_HTML_VALID)
        )
        urls = await discover_with_fallback(
            HOMEPAGE_URL, cached_urls={"2023": "https://old.url"}
        )

    assert "2024" in urls  # discovered, not cached


@pytest.mark.asyncio
async def test_discover_with_fallback_uses_cache_on_failure():
    cached = {"2024": "https://cached.url/2024", "2025": "https://cached.url/2025"}
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(return_value=httpx.Response(503))
        urls = await discover_with_fallback(HOMEPAGE_URL, cached_urls=cached)

    assert urls == cached


@pytest.mark.asyncio
async def test_discover_with_fallback_raises_if_no_cache():
    with respx.mock:
        respx.get(HOMEPAGE_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(ValueError, match="No export URLs discovered"):
            await discover_with_fallback(HOMEPAGE_URL, cached_urls={})
