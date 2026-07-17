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

from rapidfuzz import utils

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


# Leading legal-entity prefixes ("PT." / "PT" / "CV." ...) — P3DN registers
# the same company under inconsistent spellings of these.
_LEGAL_ENTITY_PREFIX_RE = re.compile(r"^(?:pt|cv|ud|pd)\.?\s+", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")


def company_search_term(name: str | None) -> str:
    """Distinctive part of a company name to use as a website search query.

    P3DN's search.php does substring matching, and the same company can be
    registered as both "PT Bumi Kaya ..." and "PT. Bumi Kaya ..." — querying
    with the full stored name only returns one spelling. Dropping the
    legal-entity prefix makes the query match all spellings; callers must
    then filter results back down with company_key().
    """
    if not name:
        return ""
    stripped = _LEGAL_ENTITY_PREFIX_RE.sub("", clean_cell_text(name))
    return stripped or clean_cell_text(name)


def company_key(name: str | None) -> str:
    """Company-name equality key: punctuation-, case-, spacing- and
    legal-entity-prefix-insensitive ("PT. Bumi Kaya" == "PT Bumi Kaya")."""
    if not name:
        return ""
    return _NON_ALNUM_RE.sub("", company_search_term(name).casefold())


def _is_abbrev_pair(a: str, b: str) -> bool:
    """True when one token is a prefix-abbreviation of the other ('dia' ~
    'diameter', 'gr' ~ 'grade'). Requires ≥2 chars so noise can't pair up."""
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= 2 and longer.startswith(shorter)


def texts_equivalent(a: str, b: str) -> bool:
    """Order-insensitive, abbreviation-aware equality of certificate text.

    Last-resort matching for text the two government sources word differently
    ('Dia. 4 1/2' vs 'Diameter 4 1/2', reordered product names) — cases
    match_key() cannot absorb. Token sets must be equal except for tokens that
    pair up as prefix-abbreviations across the two sides.

    Deliberately NOT a fuzzy score: character-level ratios rate 'Heat
    Treatment' vs 'Non-Heat Treatment' (distinct certificates!) at 97+ because
    the differentiating token is short. Here the unmatched 'non' token rejects
    the pair outright. Callers must still gate this behind a strong
    discriminator (same company + same TKDN value).
    """
    tokens_a = set(utils.default_process(a).split())
    tokens_b = set(utils.default_process(b).split())
    only_a = tokens_a - tokens_b
    only_b = tokens_b - tokens_a
    if not only_a and not only_b:
        return bool(tokens_a)  # identical token sets (both non-empty)
    return bool(tokens_a & tokens_b) and all(
        any(_is_abbrev_pair(x, y) for y in only_b) for x in only_a
    ) and all(any(_is_abbrev_pair(x, y) for y in only_a) for x in only_b)


def equivalent_text_indices(needle: str, haystack: list[str]) -> list[int]:
    """Indices of haystack entries token-equivalent to needle."""
    return [i for i, hay in enumerate(haystack) if texts_equivalent(needle, hay)]


def parse_tkdn_percent(value: str | None) -> float | None:
    """Parse a scraped TKDN percentage ('35,53 %', '35.53') to float."""
    if not value:
        return None
    cleaned = value.replace("%", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
