# src/tkdn_finder/synonyms.py
"""Synonym management: load from DB, expand queries, seed defaults."""

from __future__ import annotations

import json
import logging
import sqlite3

from .constants import DEFAULT_SYNONYM_SEEDS

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


def expand_query(query: str, synonyms: dict[str, list[str]]) -> str:
    """Expand query tokens with synonym variants for FTS5 OR matching.

    For each recognized term, appends synonym variants as OR alternatives.
    Returns an FTS5-compatible query string.
    """
    if not query.strip():
        return query

    tokens = query.strip().split()
    expanded_parts: list[str] = []

    i = 0
    while i < len(tokens):
        matched = False
        # Try multi-word matches (longest first)
        for length in range(min(4, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i : i + length])
            phrase_lower = phrase.lower()
            if phrase_lower in synonyms:
                variants = synonyms[phrase_lower]
                all_forms = [phrase] + variants
                # Build OR group: (term OR variant1 OR variant2)
                or_group = " OR ".join(f'"{v}"' if " " in v else v for v in all_forms)
                expanded_parts.append(f"({or_group})")
                i += length
                matched = True
                break
        if not matched:
            expanded_parts.append(tokens[i])
            i += 1

    return " ".join(expanded_parts)


def seed_default_synonyms(conn: sqlite3.Connection) -> None:
    """Insert DEFAULT_SYNONYM_SEEDS into the synonym table if it's empty."""
    count = conn.execute("SELECT COUNT(*) FROM synonym").fetchone()[0]
    if count > 0:
        logger.debug("Synonym table already seeded (%d rows), skipping", count)
        return

    for canonical, variants in DEFAULT_SYNONYM_SEEDS.items():
        variants_json = json.dumps(variants, ensure_ascii=False)
        conn.execute(
            "INSERT OR IGNORE INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            (canonical, variants_json),
        )
    conn.commit()
    logger.info("Seeded %d default synonyms", len(DEFAULT_SYNONYM_SEEDS))
