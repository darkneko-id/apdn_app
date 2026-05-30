# src/tkdn_finder/synonyms.py
"""Synonym management: load from DB, expand queries, seed defaults."""

from __future__ import annotations

import json
import logging
import re
import sqlite3

from .constants import DEFAULT_SYNONYM_SEEDS

# Matches either a double-quoted phrase ("gate valve") or a bare non-space token
_QUERY_TOKEN_RE = re.compile(r'"[^"]*"|\S+')

logger = logging.getLogger(__name__)


def load_synonyms(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Load enabled synonyms from the synonym table.

    Returns a dict mapping canonical term to list of variant strings.
    """
    cursor = conn.execute(
        "SELECT canonical, variants FROM synonym WHERE enabled = 1"
    )
    result: dict[str, list[str]] = {}
    for row in cursor.fetchall():
        canonical = row["canonical"]
        try:
            variants = json.loads(row["variants"])
            if isinstance(variants, list):
                result[canonical] = [str(v) for v in variants]
            else:
                logger.warning("Synonym variants not a JSON list for canonical=%r", canonical)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Could not parse synonym variants for canonical=%r: %s", canonical, exc
            )
    return result


def _expand_bare_tokens(
    tokens: list[str],
    synonyms: dict[str, list[str]],
    prefix_last: bool = False,
) -> list[str]:
    """Expand bare tokens into FTS5 query parts with synonym OR groups.

    Prefix '*' rules (in order of priority):
    1. Token already ends with '*' (user-typed) → keep it, don't double-add.
    2. Last token when prefix_last=True → add '*' automatically.
    3. Otherwise → no prefix.
    """
    result: list[str] = []
    i = 0
    while i < len(tokens):
        is_last = prefix_last and (i == len(tokens) - 1)
        raw = tokens[i]
        user_star = raw.endswith("*")
        base = raw.rstrip("*")          # strip for synonym lookup
        want_prefix = user_star or is_last

        matched = False
        for length in range(min(4, len(tokens) - i), 0, -1):
            # Build phrase from base tokens (strip any user '*')
            phrase = " ".join(t.rstrip("*") for t in tokens[i : i + length])
            if phrase.lower() in synonyms:
                variants = synonyms[phrase.lower()]
                all_forms = [phrase] + variants
                # Prefix each variant when: single-token match and want_prefix
                if want_prefix and length == 1:
                    or_group = " OR ".join(
                        f'"{v}"*' if " " in v else f"{v}*" for v in all_forms
                    )
                else:
                    or_group = " OR ".join(f'"{v}"' if " " in v else v for v in all_forms)
                result.append(f"({or_group})")
                i += length
                matched = True
                break

        if not matched:
            # If token contains a hyphen, quote it so FTS5 doesn't treat '-' as NOT.
            # The unicode61 tokenizer splits "x-over" → ["x","over"], so
            # "x-over" as a quoted phrase matches those adjacent tokens.
            if "-" in base:
                result.append(f'"{base}"' + ("*" if want_prefix else ""))
            else:
                result.append(base + ("*" if want_prefix else ""))
            i += 1
    return result


def expand_query(query: str, synonyms: dict[str, list[str]]) -> str:
    """Expand query tokens with synonym variants for FTS5 OR matching.

    Quoted phrases (e.g. "gate valve") are passed through to FTS5 verbatim
    for exact-phrase matching and are never synonym-expanded.
    Bare tokens are expanded with OR synonym groups.

    Parts are joined with explicit AND so FTS5 parses them correctly —
    implicit AND (space) does not work between a bare term and a parenthesized
    OR expression in SQLite FTS5.

    Returns an FTS5-compatible query string.
    """
    if not query.strip():
        return query

    raw_parts = _QUERY_TOKEN_RE.findall(query.strip())

    all_parts: list[str] = []
    bare_tokens: list[str] = []

    def _flush() -> None:
        if bare_tokens:
            all_parts.extend(_expand_bare_tokens(bare_tokens, synonyms))
            bare_tokens.clear()

    # Add prefix '*' to the last bare token unless the user already typed one.
    last_is_bare = (
        bool(raw_parts)
        and not raw_parts[-1].startswith('"')
        and not raw_parts[-1].endswith("*")
    )

    for part in raw_parts:
        if part.startswith('"'):
            if bare_tokens:
                all_parts.extend(_expand_bare_tokens(bare_tokens, synonyms, prefix_last=False))
                bare_tokens.clear()
            all_parts.append(part)  # exact phrase, pass through
        else:
            bare_tokens.append(part)

    if bare_tokens:
        all_parts.extend(_expand_bare_tokens(bare_tokens, synonyms, prefix_last=last_is_bare))

    # Explicit AND between parts — required when OR groups are involved
    return " AND ".join(all_parts)


def seed_default_synonyms(conn: sqlite3.Connection) -> None:
    """Upsert DEFAULT_SYNONYM_SEEDS into the synonym table.

    Inserts new entries and leaves user-edited entries untouched (INSERT OR IGNORE).
    """
    added = 0
    for canonical, variants in DEFAULT_SYNONYM_SEEDS.items():
        variants_json = json.dumps(variants, ensure_ascii=False)
        cursor = conn.execute(
            "INSERT OR IGNORE INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            (canonical, variants_json),
        )
        if cursor.rowcount:
            added += 1
    conn.commit()
    if added:
        logger.info("Seeded %d new default synonyms", added)
