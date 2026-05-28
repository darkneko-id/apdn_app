# Scraper Implementation Guide — P3DN URL Discovery

## Overview

App no longer hardcodes download URLs. Instead, it **scrapes P3DN homepage** to discover current download links automatically. This handles token rotation gracefully.

## Architecture

```
[Scheduler] 02:00 AM daily
    ↓
[Scraper] GET https://p3dn.kemenperin.go.id/
    ↓ parse HTML, extract export_excel.php links
    ↓
{
  "2024": "https://p3dn.kemenperin.go.id/export_excel.php?thn=XO3tSoRY4lHDtw2EKfSt-1gNj9Q-dwKGgBz5nb8EM",
  "2025": "https://p3dn.kemenperin.go.id/export_excel.php?thn=2sOoXJh1Pq6y1tkg5oA7MV6Ia96M2Hfla6_ABTCB2u8",
  "2026": "https://p3dn.kemenperin.go.id/export_excel.php?thn=2LtIAq-S_CL6ShnR120ukm23GZ4e8eNd5rq2cOwvPnM"
}
    ↓
[Downloader] download 3 files
    ↓
[Parser] → [Merger] → [Index]
```

## Implementation: src/tkdn_finder/scraper.py

```python
from bs4 import BeautifulSoup
import httpx
import re
import logging

logger = logging.getLogger(__name__)

async def discover_download_urls(
    homepage_url: str = "https://p3dn.kemenperin.go.id/",
    timeout: int = 60,
    user_agent: str = "TKDN-Finder/0.1 (procurement tooling)"
) -> dict[str, str]:
    """
    Scrape P3DN homepage, extract export_excel.php URLs.
    
    Expected HTML structure:
        <a href="/export_excel.php?thn=TOKEN" class="btn btn-primary">
            <i class="fa fa-download"></i>
            Download TKDN LVI 2024
        </a>
    
    Args:
        homepage_url: P3DN homepage URL (trailing slash optional)
        timeout: HTTP request timeout in seconds
        user_agent: User-Agent header (must identify this tool)
    
    Returns:
        dict: {"2024": "full_url", "2025": "full_url", "2026": "full_url"}
        
    Raises:
        httpx.RequestError: if download fails (4xx, 5xx, timeout, etc.)
        ValueError: if no download links found (page structure changed)
    """
    
    homepage_url = homepage_url.rstrip('/')
    
    # Download page
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            homepage_url,
            headers={"User-Agent": user_agent}
        )
        resp.raise_for_status()
    
    logger.info(f"Scraped P3DN homepage, {len(resp.text)} bytes")
    
    # Parse HTML
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all export_excel.php links
    urls = {}
    for link in soup.find_all('a', href=re.compile(r'export_excel\.php')):
        href = link.get('href')
        text = link.get_text(strip=True)
        
        # Extract year from text: "Download TKDN LVI 2024" → "2024"
        year_match = re.search(r'(\d{4})', text)
        if not year_match:
            logger.warning(f"Could not extract year from link text: {text}")
            continue
        
        year = year_match.group(1)
        
        # Build full URL if relative
        if href.startswith('/'):
            full_url = homepage_url + href
        else:
            full_url = href
        
        urls[year] = full_url
        logger.info(f"Discovered {year} download URL: {full_url[:80]}...")
    
    if not urls:
        raise ValueError("No download links found on P3DN homepage. Page structure may have changed.")
    
    logger.info(f"Discovered {len(urls)} download URLs: {list(urls.keys())}")
    return urls


async def discover_with_fallback(
    homepage_url: str,
    cached_urls: dict[str, str] | None = None,
    timeout: int = 60,
    user_agent: str = "TKDN-Finder/0.1 (procurement tooling)"
) -> dict[str, str]:
    """
    Discover URLs with fallback to cached/previous URLs.
    
    Args:
        homepage_url: P3DN homepage
        cached_urls: Previous successful URLs from DB (fallback)
        timeout: HTTP timeout
        user_agent: User-Agent header
    
    Returns:
        dict: discovered URLs, or cached if discovery fails
        
    Raises:
        ValueError: if discovery fails AND no cache available
    """
    
    try:
        urls = await discover_download_urls(
            homepage_url=homepage_url,
            timeout=timeout,
            user_agent=user_agent
        )
        return urls
    
    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        
        if cached_urls:
            logger.warning(f"Using cached URLs from previous run: {list(cached_urls.keys())}")
            return cached_urls
        
        raise ValueError(
            f"URL discovery failed and no cached URLs available. Error: {e}"
        )
```

## Integration: src/tkdn_finder/scheduler.py

```python
from tkdn_finder.scraper import discover_with_fallback
from tkdn_finder.downloader import download_file
from tkdn_finder.db import get_cached_urls, save_download_run

async def refresh_all_years():
    """
    Scheduled task: discover URLs, download, parse, merge.
    
    Flow:
    1. Discover URLs (with fallback to previous cached)
    2. For each URL, download file
    3. Parse, merge, index
    4. Log run result
    """
    
    logger = logging.getLogger(__name__)
    logger.info("Starting scheduled refresh...")
    
    # Get previous URLs as fallback
    cached_urls = await get_cached_urls()  # from DB
    
    try:
        # Discover current URLs
        discovered_urls = await discover_with_fallback(
            homepage_url=settings.p3dn.homepage_url,
            cached_urls=cached_urls,
            timeout=settings.p3dn.download_timeout_seconds,
            user_agent=settings.p3dn.user_agent
        )
        
        # Download, parse, merge
        for year, url in discovered_urls.items():
            logger.info(f"Downloading {year}: {url[:80]}...")
            
            try:
                file_path = await download_file(
                    url=url,
                    year=year,
                    timeout=settings.p3dn.download_timeout_seconds,
                    max_retries=settings.p3dn.retry_count,
                    user_agent=settings.p3dn.user_agent
                )
                
                # Parse and index
                rows = parse_html_export(file_path, year)
                await upsert_rows(rows, year)
                
                # Log success
                await save_download_run(
                    year=year,
                    url=url,
                    status="success",
                    row_count=len(rows)
                )
                
            except Exception as e:
                logger.error(f"Failed to download/parse {year}: {e}")
                await save_download_run(
                    year=year,
                    url=url,
                    status="failed",
                    error_message=str(e)
                )
        
        logger.info("Refresh completed")
    
    except ValueError as e:
        logger.error(f"Fatal: {e}")
        await save_download_run(
            year="unknown",
            url="discovery_failed",
            status="failed",
            error_message=str(e)
        )
        # Alert admin (via admin UI)
```

## Configuration Updates

**No hardcoded URLs needed.** Only:

```yaml
p3dn:
  homepage_url: "https://p3dn.kemenperin.go.id/"
  user_agent: "TKDN-Finder/0.1 (procurement tooling; contact: irsan@phr.pertamina.com)"
  download_timeout_seconds: 60
  retry_count: 3
  retry_backoff_seconds: 5

schedule:
  cron: "0 2 * * *"
```

## Admin UI Integration

Display scraper status on admin page:

```
Last refresh: 2026-05-27 02:00:15 ✓
Status: Success (3 files downloaded)

2024: 4,652 rows ✓
2025: 22,043 rows ✓
2026: 19,848 rows ✓

Next scheduled: 2026-05-28 02:00:00
```

If scraper fails:

```
Last refresh: 2026-05-27 02:00:15 ✗
Status: Failed (scraper)
Error: "No download links found on P3DN homepage"

Fallback: Using cached URLs from 2026-05-26

Action: Check if P3DN page structure changed, or report issue
```

## Testing

```python
# tests/test_scraper.py

@pytest.mark.asyncio
async def test_discover_urls_from_html():
    """Test scraper with real P3DN HTML structure."""
    
    html = '''
    <a href="/export_excel.php?thn=ABC123" class="btn btn-primary">
        <i class="fa fa-download"></i>
        Download TKDN LVI 2024
    </a>
    <a href="/export_excel.php?thn=DEF456" class="btn btn-primary">
        <i class="fa fa-download"></i>
        Download TKDN LVI 2025
    </a>
    '''
    
    # Mock httpx.AsyncClient
    async def mock_get(*args, **kwargs):
        class MockResponse:
            text = html
            def raise_for_status(self):
                pass
        return MockResponse()
    
    # Test
    urls = await discover_download_urls()
    # Expected:
    # {"2024": "https://p3dn.kemenperin.go.id/export_excel.php?thn=ABC123", ...}
    
    assert len(urls) == 2
    assert "2024" in urls
    assert "export_excel.php" in urls["2024"]
```

## Resilience

| Scenario | Behavior |
|---|---|
| Network timeout | Retry 3x with 5s backoff, then use cached URLs if available |
| 404/503 from P3DN | Log error, use cached URLs |
| P3DN page layout changed (no links found) | Use cached URLs, alert admin |
| No cache available (first run, scraper fails) | Fail loudly, admin must manually upload files |
| Scraper succeeds, download fails | Log error per file, reuse any successful files, try again tomorrow |

## Constants (src/tkdn_finder/constants.py)

```python
P3DN_HOMEPAGE_URL = "https://p3dn.kemenperin.go.id/"
EXPORT_LINK_HREF_PATTERN = r"export_excel\.php"
YEAR_EXTRACTION_PATTERN = r"(\d{4})"

SCRAPER_TIMEOUT_SECONDS = 60
SCRAPER_USER_AGENT = "TKDN-Finder/0.1 (procurement tooling)"

DOWNLOAD_RETRY_COUNT = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 5

RAW_RETENTION_COUNT = 7
```

---

## Next Steps

1. Implement `scraper.py` with async BeautifulSoup parsing
2. Update `scheduler.py` to call scraper before downloader
3. Add `test_scraper.py` with mock HTML samples
4. Update admin UI to show scraper status
5. Document fallback behavior in README

Done! Scraper auto-handles token rotation. Zero hardcoded URLs needed.
