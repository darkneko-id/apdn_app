# src/tkdn_finder/search.py
"""Two-stage FTS5 search with rapidfuzz reranking."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import date
from typing import Any

from rapidfuzz import fuzz

from .constants import (
    FTS_CANDIDATE_LIMIT,
    RERANK_WEIGHT_FUZZY,
    RERANK_WEIGHT_RECENCY,
    RERANK_WEIGHT_TKDN,
    RERANK_WEIGHT_VALIDITY,
    SEARCH_RESULT_LIMIT_DEFAULT,
    SEARCH_RESULT_LIMIT_MAX,
    TKDN_DEFAULT_MIN_FILTER,
    VALIDITY_EXPIRING_SOON_DAYS,
)
from .synonyms import expand_query, load_synonyms

logger = logging.getLogger(__name__)


def _build_fts_query(query: str, synonyms: dict[str, list[str]]) -> str:
    """Build an FTS5 MATCH query string with synonym expansion."""
    expanded = expand_query(query, synonyms)
    # FTS5 needs each bare token quoted if it contains special chars
    # Simple approach: use the expanded string as-is (tokens and OR groups)
    return expanded


def _compute_score(
    row: dict[str, Any],
    query: str,
    today: date,
    max_tahun: int,
    min_tahun: int,
) -> float:
    """Compute composite relevance score for a candidate row."""
    # Fuzzy match score (0-100 normalized to 0-1)
    search_text = " ".join(
        filter(
            None,
            [
                row.get("nama_produk") or "",
                row.get("nama_perusahaan") or "",
                row.get("spesifikasi") or "",
                row.get("merek") or "",
            ],
        )
    )
    fuzzy_score = fuzz.token_set_ratio(query.lower(), search_text.lower()) / 100.0

    # TKDN score (normalize to 0-1 capped at 100%)
    nilai_tkdn = row.get("nilai_tkdn") or 0.0
    tkdn_score = min(nilai_tkdn / 100.0, 1.0)

    # Recency score (normalize year within range)
    tahun = row.get("tahun_sumber") or min_tahun
    year_range = max(max_tahun - min_tahun, 1)
    recency_score = (tahun - min_tahun) / year_range

    # Validity score
    masa_str = row.get("masa_berlaku_akhir")
    if masa_str:
        try:
            masa_date = date.fromisoformat(str(masa_str))
            days_remaining = (masa_date - today).days
            if days_remaining > VALIDITY_EXPIRING_SOON_DAYS:
                validity_score = 1.0
            elif days_remaining > 0:
                validity_score = 0.5
            else:
                validity_score = 0.0
        except ValueError:
            validity_score = 0.0
    else:
        validity_score = 0.0

    total = (
        RERANK_WEIGHT_FUZZY * fuzzy_score
        + RERANK_WEIGHT_TKDN * tkdn_score
        + RERANK_WEIGHT_RECENCY * recency_score
        + RERANK_WEIGHT_VALIDITY * validity_score
    )
    return total


def search(
    conn: sqlite3.Connection,
    query: str,
    tkdn_min: float = TKDN_DEFAULT_MIN_FILTER,
    validity_only: bool = False,
    kbli: str | None = None,
    year: int | None = None,
    limit: int = SEARCH_RESULT_LIMIT_DEFAULT,
    offset: int = 0,
) -> dict[str, Any]:
    """Perform two-stage FTS5 + rapidfuzz search.

    Stage 1: FTS5 candidate retrieval with synonym expansion.
    Stage 2: rapidfuzz reranking with composite score.

    Returns:
        Dict with "results" (list of dicts), "total" (int), "query_time_ms" (float).
    """
    limit = min(limit, SEARCH_RESULT_LIMIT_MAX)
    start_time = time.perf_counter()
    today = date.today()

    synonyms = load_synonyms(conn)

    # --- Stage 1: FTS5 candidate retrieval ---
    where_clauses: list[str] = []
    params: list[Any] = []

    if query.strip():
        fts_query = _build_fts_query(query.strip(), synonyms)
        # Use FTS5 subquery to get matching rowids
        where_clauses.append(
            "c.id IN (SELECT rowid FROM tkdn_search WHERE tkdn_search MATCH ?)"
        )
        params.append(fts_query)

    if tkdn_min > 0:
        where_clauses.append("(c.nilai_tkdn IS NOT NULL AND c.nilai_tkdn >= ?)")
        params.append(tkdn_min)

    if validity_only:
        where_clauses.append("c.masa_berlaku_akhir >= ?")
        params.append(today.isoformat())

    if kbli:
        where_clauses.append("c.kbli = ?")
        params.append(kbli)

    if year:
        where_clauses.append("c.tahun_sumber = ?")
        params.append(year)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    candidate_sql = f"""
        SELECT c.*
        FROM tkdn_certificate c
        {where_sql}
        LIMIT {FTS_CANDIDATE_LIMIT}
    """

    try:
        cursor = conn.execute(candidate_sql, params)
        candidates = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as exc:
        logger.warning("FTS5 query failed, falling back to LIKE search: %s", exc)
        # Fallback: simple LIKE search
        if query.strip():
            like_val = f"%{query.strip()}%"
            where_clauses = [
                "(c.nama_produk LIKE ? OR c.nama_perusahaan LIKE ? OR c.spesifikasi LIKE ?)"
            ]
            params = [like_val, like_val, like_val]
            where_sql = "WHERE " + " AND ".join(where_clauses)
        else:
            where_sql = ""
            params = []

        candidate_sql = f"""
            SELECT c.*
            FROM tkdn_certificate c
            {where_sql}
            LIMIT {FTS_CANDIDATE_LIMIT}
        """
        cursor = conn.execute(candidate_sql, params)
        candidates = [dict(row) for row in cursor.fetchall()]

    if not candidates:
        elapsed = (time.perf_counter() - start_time) * 1000
        return {"results": [], "total": 0, "query_time_ms": round(elapsed, 2)}

    # --- Stage 2: Rerank ---
    years = [c.get("tahun_sumber") or 0 for c in candidates]
    max_tahun = max(years) if years else 0
    min_tahun = min(years) if years else 0

    if query.strip():
        for candidate in candidates:
            candidate["_score"] = _compute_score(candidate, query, today, max_tahun, min_tahun)
        candidates.sort(key=lambda x: x["_score"], reverse=True)
    # If no query, maintain DB order (implicit recency from ID)

    total = len(candidates)
    page_candidates = candidates[offset : offset + limit]

    # Clean up internal score field and add to result
    results = []
    for c in page_candidates:
        score = c.pop("_score", None)
        c["score"] = score
        results.append(c)

    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Search complete: query=%r total=%d returned=%d latency_ms=%.1f",
        query,
        total,
        len(results),
        elapsed,
    )

    return {
        "results": results,
        "total": total,
        "query_time_ms": round(elapsed, 2),
    }
