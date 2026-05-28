# tests/conftest.py
"""Shared pytest fixtures for TKDN Finder tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tkdn_finder.db import get_connection, init_db

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Return an in-memory-equivalent SQLite connection with schema applied."""
    db_path = str(tmp_path / "test_tkdn.db")
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    """Return a path to an initialized SQLite database."""
    path = str(tmp_path / "test_tkdn.db")
    init_db(path)
    return path


@pytest.fixture()
def sample_2024_path() -> str:
    """Path to the 2024 HTML fixture file."""
    return str(FIXTURES_DIR / "sample_2024.html")


@pytest.fixture()
def sample_2025_path() -> str:
    """Path to the 2025 HTML fixture file."""
    return str(FIXTURES_DIR / "sample_2025.html")


@pytest.fixture()
def sample_2026_path() -> str:
    """Path to the 2026 HTML fixture file."""
    return str(FIXTURES_DIR / "sample_2026.html")


@pytest.fixture()
def seeded_db_conn(db_conn: sqlite3.Connection, sample_2026_path: str) -> sqlite3.Connection:
    """Return a DB connection pre-seeded with 2026 fixture data."""
    from tkdn_finder.merger import merge_and_upsert
    from tkdn_finder.parser import parse_html_export
    from tkdn_finder.synonyms import seed_default_synonyms

    rows = parse_html_export(sample_2026_path, "2026")
    merge_and_upsert(db_conn, rows)
    seed_default_synonyms(db_conn)
    return db_conn
