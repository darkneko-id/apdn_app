# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project summary

A Python web app that downloads, parses, deduplicates, and indexes Indonesia's TKDN certificate dataset from Kemenperin P3DN. It exposes a fast typo-tolerant search UI for procurement use at PT Pertamina Hulu Rokan (PHR).

Primary user: procurement analyst doing pra-qualification and BAHP drafting under PTK-007 / Pedoman A7-001.

Refer to `PRD.md` for the full product spec.

## Stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Storage + search | SQLite + FTS5 |
| Scheduler | APScheduler (in-process) |
| Frontend | HTMX + Tailwind + Alpine.js (no build pipeline, server-rendered) |
| HTML parsing | BeautifulSoup4 — P3DN exports HTML tables disguised as `.xls` files |
| HTTP client | httpx (async) |
| Fuzzy | rapidfuzz — synonym expansion + result reranking |
| Config | pydantic-settings — env > yaml > defaults |

Do not add top-level dependencies without updating `pyproject.toml`.

## Common commands

```bash
# Install (preferred: uv)
uv sync

# Run dev server
uvicorn tkdn_finder.main:app --reload --port 8000

# Format + lint
ruff check --fix . && black .

# Type check
mypy --strict src/tkdn_finder

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_parser.py
pytest tests/test_search.py::test_synonym_hit -v

# Coverage
pytest --cov=src/tkdn_finder --cov-report=term-missing

# Build Tailwind CSS (one-time for prod)
npx tailwindcss -i src/tkdn_finder/static/css/input.css -o src/tkdn_finder/static/css/app.css --minify

# Build Windows .exe
pyinstaller build.spec
```

## Architecture: data pipeline

Two external sources feed the local SQLite database:

**Source 1 — P3DN bulk exports** (`rekap.php`):
1. `scraper.py` — scrapes `https://p3dn.kemenperin.go.id/rekap.php`, finds `export_excel.php` links, returns `{year: url}` dict. Falls back to cached URLs from `download_run` table on failure.
2. `downloader.py` — downloads each year's HTML-disguised-as-XLS file to `data/raw/`.
3. `parser.py` — `parse_html_export()` reads the file as UTF-8 text via BeautifulSoup, maps columns via `HTML_COLUMN_MAP` in `constants.py`, and normalises values. **Tipe column is systematically empty in this source.**
4. `merger.py` — calls `db.upsert_certificate()` for each row. Dedup key: `(nama_perusahaan, nama_produk, spesifikasi, tipe)`.
5. `scheduler.py` — APScheduler runs `refresh_all_years` on cron from config. Progress is tracked in the module-level `refresh_state.py` singleton.

**Source 2 — TKDN Kemenperin search** (`tkdn.kemenperin.go.id/search.php`):
- `tipe_enricher.py` — scrapes the secondary government site per company name to backfill the `tipe` column that is absent from bulk exports. Triggered via `POST /enrich-tipe` in `routes/search.py`. Matches scraped rows to DB rows by `(nama_produk, spesifikasi, nilai_tkdn ±0.1)`, then either updates empty-tipe rows or inserts new rows for distinct tipe variants.

## Architecture: search

Two-stage pipeline in `search.py`:
1. **FTS5 candidate retrieval** — MATCH query with porter/unicode61 tokenizer. Query tokens are expanded with synonyms from the `synonym` table at query time (not index time). Filters for validity/TKDN%/KBLI/year pushed to SQL WHERE. Returns top 500 candidates by FTS5 rank.
2. **Rerank** — `rapidfuzz.fuzz.token_set_ratio` against the original query. Final score: fuzzy 50% + TKDN% 20% + recency 15% + validity-active 15%. Weights live in `constants.py`.

The FTS5 columns are: `nama_perusahaan`, `nama_produk`, `merek`, `tipe`, `spesifikasi`, `kbli`, `kelompok_barang`.

## Architecture: web layer

Routes in `src/tkdn_finder/routes/`:
- `GET /` — main search page (full HTML)
- `GET /search` — HTMX partial (`results.html`), includes column sort via `_SORT_KEYS`
- `GET /api/search` — JSON API, same parameters as `/search`
- `POST /enrich-tipe` — triggers Tipe enrichment for companies in current search results
- `GET /cert/{id}` — certificate detail page
- `GET /export.xlsx` — export current search as Excel
- `GET /admin`, `POST /admin/refresh` — admin UI, download run history, synonym CRUD
- `GET /health`, `GET /metrics` — health check and stats

DB connections are opened per-request (not pooled). `get_connection()` always enables WAL mode. All SQL lives in `db.py` — no raw SQL strings in route handlers.

Templates use a custom Jinja2 filter `wib` (registered in `main.py`) to convert UTC timestamps to WIB (UTC+7) for display.

## Database schema

Migrations applied sequentially from `migrations/NNN_*.sql` by `db._apply_migrations()`. Versions tracked in `schema_version` table.

Key tables:
- `tkdn_certificate` — main data, UNIQUE on `(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn)` (migration 005 removed `tipe` from key — tipe is always '' from P3DN bulk export; including it caused re-downloads to create duplicate empty-tipe rows after enrichment). Merger preserves enriched tipe on re-download via `CASE WHEN excluded.tipe != '' THEN excluded.tipe ELSE tipe END`.
- `tkdn_search` — FTS5 virtual table, content-table backed by `tkdn_certificate.id`, kept in sync via triggers `tkdn_ai`/`tkdn_au`/`tkdn_ad`
- `download_run` — history of scrape+download runs, used to surface errors in admin UI and cache last-known URLs
- `synonym` — editable synonym map; `seeds_default_synonyms()` populates defaults at startup without overwriting existing entries

When changing the schema: add `migrations/NNN_description.sql`, update `db.py` helpers, update `models.py`, update `HTML_COLUMN_MAP` in `constants.py` if source columns changed, run `pytest`.

## Constants

ALL magic values live in `src/tkdn_finder/constants.py`. Never inline literals in business logic.

Key groups: URL/regex patterns, timeouts, `HTML_COLUMN_MAP` (P3DN column headers → internal field names), rerank weights, FTS candidate limit, synonym seeds.

## Configuration

Settings loaded by `config.py` (pydantic-settings). Precedence: env vars > `.env` file > YAML > defaults.

```
TKDN_DATA_DIR          # data directory (Linux/Mac); Windows uses %APPDATA%/TKDN-Finder/
TKDN_LOG_LEVEL
TKDN_P3DN__HOMEPAGE_URL
TKDN_P3DN__VERIFY_SSL  # set False only when P3DN cert is untrusted; logs a MITM warning
TKDN_SCHEDULE__CRON    # default: "0 2 * * *"
```

See `config.example.yaml` for the full YAML shape. The `get_settings()` function is `@lru_cache` — call it directly anywhere; it returns the same singleton.

## Coding conventions

- Type hints on all functions. `mypy --strict` must pass.
- Pydantic models for data crossing module boundaries.
- Async for I/O (scraper, downloader, routes). Sync for CPU work (parser, merger).
- `logger.exception(...)` with structured `extra={...}` — never swallow errors.
- SQL stays in `db.py`. No raw SQL in route handlers.
- f-strings only — no `%` or `.format()`.
- Indonesian domain terms keep Indonesian spelling in DB columns (`nama_perusahaan`, `masa_berlaku_akhir`). Function names are English.
- Log the `thn=` token from P3DN URLs at DEBUG only; redact at INFO.

## Domain glossary

| Term | Meaning |
|---|---|
| TKDN | Tingkat Komponen Dalam Negeri — local content percentage |
| BMP | Bobot Manfaat Perusahaan — company-benefit weight |
| P3DN / APDN | Pusat P3DN, Kemenperin unit publishing the dataset |
| KBLI | Klasifikasi Baku Lapangan Usaha Indonesia — industry classification |
| Tipe | Product type/variant — absent from P3DN bulk export, enriched from secondary source |
| Merk / Merek | Brand name |
| Masa berlaku | Certificate validity period |
| BAHP | Berita Acara Hasil Pelelangan — tender result minutes |
| PTK-007 | BPMA procurement regulation for KKKS operators |

## Anti-patterns

- Do not use an ORM for FTS5 queries — raw SQL is clearer and FTS5 syntax is non-standard.
- Do not skip schema-drift detection in parser — P3DN may rename columns; log warning, do not silently drop.
- Do not delete raw downloaded files immediately — keep last `RAW_RETENTION_COUNT` runs.
- Do not introduce Redis, Celery, or a message queue — APScheduler in-process is sufficient for MVP.
- Do not hardcode the cron string — it lives in config.
- Do not call external LLMs for reranking — rapidfuzz handles the cases that matter.

## Known unknowns

| Item | Status |
|---|---|
| Are P3DN `thn=...` tokens stable across months? | Open |
| Does P3DN expose a per-cert detail URL pattern? | Open |
| P3DN ToS regarding automated download | Open |
| Notification channel (Telegram bot?) | Open |
