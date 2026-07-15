# src/tkdn_finder/textnorm.py
"""Text normalisation shared by scrapers and cross-source matching.

The P3DN bulk export, P3DN search.php and tkdn.kemenperin.go.id render the
same certificate text with different whitespace (double spaces, NBSP, line
breaks inside cells) and different dash characters (hyphen vs en/em dash).
Matching scraped rows against stored rows must therefore never compare raw
strings — build keys with match_key() instead.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
# Unicode hyphen/dash variants that appear interchangeably in P3DN specs
# (e.g. "Dia. 4 1/2 – 13 3/8 inch" vs "4 1/2 - 13 3/8").
_DASH_RE = re.compile(r"[‐‑‒–—―−]")


def clean_cell_text(value: str) -> str:
    """Collapse whitespace runs (spaces, NBSP, newlines) to single spaces."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def match_key(value: str | None) -> str:
    """Whitespace-, case- and dash-insensitive key for cross-source matching.

    Removing ALL whitespace (not just collapsing) also absorbs the case where
    one source drops the space between words entirely (BeautifulSoup's
    get_text(strip=True) joins nested elements without a separator).
    """
    if not value:
        return ""
    return _WHITESPACE_RE.sub("", _DASH_RE.sub("-", value)).casefold()


def parse_tkdn_percent(value: str | None) -> float | None:
    """Parse a scraped TKDN percentage ('35,53 %', '35.53') to float."""
    if not value:
        return None
    cleaned = value.replace("%", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
