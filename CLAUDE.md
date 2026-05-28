# CLAUDE.md — TKDN Finder

Guide for Claude Code when working on this repository. Read this fully before making any changes. Refer to `PRD.md` for the full product spec.

## 1. Project summary

A Python web app that downloads, parses, deduplicates, and indexes Indonesia's TKDN certificate dataset from Kemenperin P3DN. It exposes a fast typo-tolerant search UI for procurement use at PT Pertamina Hulu Rokan (PHR).

Primary user: procurement analyst doing pra-qualification and BAHP drafting under PTK-007 / Pedoman A7-001.

## 2. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Type hints, async, ecosystem |
| Web framework | FastAPI + Uvicorn | Async, OpenAPI, fast |
| Storage + search | SQLite + FTS5 | Single file, zero ops, 46K rows handled |
| Scheduler | APScheduler (in-process) | No extra service for MVP |
| Frontend | HTMX + Tailwind + Alpine.js | No build pipeline, server-rendered |
| HTML parsing | BeautifulSoup4 | P3DN exports as HTML table (not binary Excel) |
| HTTP client | httpx (async) | Modern, async-native |
| Fuzzy | rapidfuzz | Synonym expansion + result reranking |
| Config | pydantic-settings | Typed config from env + yaml |
| Tests | pytest + pytest-asyncio + respx | Standard |
| Lint/format | ruff + black | Standard |
| Packaging | PyInstaller | Single .exe for Windows, zero Python install |

Do not add new top-level dependencies without updating `pyproject.toml` and explaining the rationale in the PR description.

## 3. Folder layout

```
tkdn-finder/
├── pyproject.toml
├── CLAUDE.md                    # this file
├── PRD.md
├── README.md
├── config.example.yaml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── src/tkdn_finder/
│   ├── __init__.py
│   ├── constants.py             # ALL magic values live here
│   ├── config.py                # pydantic Settings model
│   ├── main.py                  # FastAPI app entry
│   ├── db.py                    # SQLite schema + connection helpers
│   ├── models.py                # Pydantic models for API + internal
│   ├── downloader.py            # P3DN Excel download
│   ├── parser.py                # Excel -> normalized rows
│   ├── merger.py                # Multi-year merge, dedup, upsert
│   ├── search.py                # FTS5 query builder + reranker
│   ├── synonyms.py              # Synonym map load / apply
│   ├── scheduler.py             # APScheduler setup
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── search.py            # GET /search, GET /api/search
│   │   ├── detail.py            # GET /cert/{nomor}
│   │   ├── admin.py             # GET /admin, POST /admin/refresh
│   │   ├── export.py            # GET /export.xlsx
│   │   └── health.py            # GET /health, GET /metrics
│   ├── templates/               # Jinja2 server-rendered
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── results.html         # HTMX partial
│   │   ├── detail.html
│   │   └── admin.html
│   └── static/
│       ├── css/                 # built Tailwind CSS
│       └── js/                  # tiny Alpine helpers if any
├── migrations/
│   └── 001_initial.sql
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_2024.xlsx
│   │   ├── sample_2025.xlsx
│   │   └── sample_2026.xlsx
│   ├── test_downloader.py
│   ├── test_parser.py
│   ├── test_merger.py
│   ├── test_search.py
│   └── test_routes.py
└── data/                        # gitignored, runtime data
    ├── raw/                     # downloaded .xlsx files
    └── tkdn.db                  # SQLite DB
```

## 4. Constants — single source of truth

ALL constants live in `src/tkdn_finder/constants.py`. Do not inline magic strings, paths, defaults, thresholds, column names, or regex patterns anywhere else.

Example shape:

```python
# src/tkdn_finder/constants.py

P3DN_BASE_URL = "https://p3dn.kemenperin.go.id"
DEFAULT_USER_AGENT = "TKDN-Finder/0.1 (procurement tooling)"

DOWNLOAD_TIMEOUT_SECONDS = 60
DOWNLOAD_RETRY_COUNT = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 5
RAW_RETENTION_COUNT = 7

# Source column header (from P3DN HTML) -> internal field name.
# P3DN exports 12 columns, order fixed. When headers change, edit ONLY here.
HTML_COLUMN_MAP = {
    "Kode HS": "kode_hs",
    "KBLI": "kbli",
    "Kelompok Barang": "kelompok_barang",
    "Nama Perusahaan": "nama_perusahaan",
    "Alamat": "alamat",
    "Provinsi": "provinsi",
    "Produk": "nama_produk",
    "Spesifikasi": "spesifikasi",
    "Tipe": "tipe",
    "Merk": "merek",
    "Nilai TKDN (%)": "nilai_tkdn",
    "Tanggal Kadaluarsa Sertifikat": "masa_berlaku_akhir",
}

REQUIRED_FIELDS = ("nama_perusahaan", "nama_produk", "spesifikasi")

DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")

FTS_TOKENIZER = "porter unicode61 remove_diacritics 2"

VALIDITY_EXPIRING_SOON_DAYS = 60
TKDN_DEFAULT_MIN_FILTER = 0.0

SEARCH_RESULT_LIMIT_DEFAULT = 50
SEARCH_RESULT_LIMIT_MAX = 500
SEARCH_DEBOUNCE_MS = 250

# Static synonym seeds; admin can override via the synonym table at runtime
DEFAULT_SYNONYM_SEEDS = {
    "valve": ["katup", "valv"],
    "pipe": ["pipa"],
    "transformer": ["trafo"],
    "electric motor": ["motor listrik"],
    "cable": ["kabel"],
    "pump": ["pompa"],
}
```

Rule of thumb: if you find yourself typing a literal value in business logic, stop and add it to `constants.py` first.

## 5. Configuration

User-tunable settings live in `config.yaml` and environment variables. Precedence: env > yaml > defaults.

Loaded by `config.py` using `pydantic-settings`. Do not hardcode URLs, schedules, or paths in code. Read them from a `Settings` instance passed via FastAPI dependencies.

The three P3DN download URLs are part of config, not constants. They will need updating when Kemenperin rotates tokens. See `config.example.yaml` for the canonical shape.

## 6. Domain glossary

| Term | Meaning |
|---|---|
| TKDN | Tingkat Komponen Dalam Negeri. Local content percentage of a product. |
| BMP | Bobot Manfaat Perusahaan. Company-benefit weight. |
| TKDN + BMP | Composite score used in tender preferences. |
| P3DN | Pusat P3DN, the Kemenperin unit publishing the dataset. |
| KBLI | Klasifikasi Baku Lapangan Usaha Indonesia. Industry classification. |
| Praqual | Pra-qualification, vendor screening stage. |
| BAHP | Berita Acara Hasil Pelelangan. Tender result minutes. |
| PTK-007 | BPMA procurement regulation for KKKS oil-and-gas operators. |
| A7-001 | Pertamina-internal procurement guideline (Pedoman A7-001). |
| APDN | Aplikasi Produk Dalam Negeri, the P3DN frontend. Often referred to interchangeably with P3DN portal. |
| Masa berlaku | Validity period of the certificate. |

## 7. Coding conventions

- Type hints required on all functions and methods. Run `mypy --strict src/tkdn_finder` clean.
- Pydantic models for any data crossing module boundaries.
- Async for I/O (downloader, routes). Sync for CPU work (parsing, merging).
- Errors are not swallowed. Use `logger.exception(...)` with structured `extra={...}` context.
- One responsibility per module. If `parser.py` grows HTTP calls, refactor.
- SQL stays in `db.py` or query-builder helpers. No raw SQL strings inside route handlers.
- No business logic in templates. Pass prepared dataclasses or dicts.
- f-strings for formatting. Never `%` or `.format()` in new code.
- Avoid global mutable state. Use FastAPI dependencies for DB connection, settings, etc.

### Naming

- snake_case for Python.
- Indonesian domain terms keep their Indonesian spelling in DB columns and internal field names (`nomor_sertifikat`, `nama_produsen`). Do not anglicize. They match the source data and PRD glossary.
- Function names in English (`parse_excel`, `dedupe_by_certificate`).

### Logging

- One structured log line per significant event: download start, download finish, parse start, parse finish (with counts), dedup result, search query (with latency and result count).
- Levels: DEBUG for verbose internals, INFO for normal lifecycle events, WARNING for recoverable anomalies (schema drift, missing field), ERROR for failures.
- Never log full row contents at INFO. Use DEBUG for that.
- Never log secrets or full URLs containing tokens at INFO. Redact the `thn=...` query parameter.

## 8. Database

SQLite file at `{data_dir}/tkdn.db`. Initial schema in `migrations/001_initial.sql`. Apply via a simple version-tracking helper in `db.py`. Alembic is overkill for MVP.

FTS5 virtual table mirrors searchable columns of `tkdn_certificate`. Kept in sync via SQLite triggers, defined in the initial migration.

When changing the schema:

1. Add a new migration file `migrations/NNN_description.sql`.
2. Update DDL helpers in `db.py`.
3. Update `models.py`.
4. Update `constants.EXCEL_COLUMN_MAP` if source columns added or renamed.
5. Update tests, including a fixture that exercises the new field.
6. Run `pytest` clean before committing.

WAL mode enabled for concurrent read-during-write (admin refresh while user searches).

## 9. Parser implementation notes

P3DN exports HTML tables disguised as `.xls` files. Key behavior:

```python
# src/tkdn_finder/parser.py
from bs4 import BeautifulSoup

def parse_html_export(file_path: str, year: str) -> list[dict]:
    """
    Parse P3DN HTML table export.
    
    1. Read file as UTF-8 text
    2. Parse with BeautifulSoup
    3. Find <table>, extract <tbody> or all <tr> after header
    4. Map columns per HTML_COLUMN_MAP
    5. Normalize: strip whitespace, "-" and empty -> None, TKDN parse as float
    6. Compute is_valid_today from masa_berlaku_akhir
    7. Return list of normalized dicts
    """
```

**Data normalization:**
- Whitespace collapse: `.strip()`
- Brand/Type empty/"-" → None
- TKDN parse: `float(nilai_tkdn)` (already in % format)
- Date parse: `datetime.strptime(masa_berlaku_akhir, "%Y-%m-%d").date()` (no variance)
- Company/product/spec: preserve original case for display, lowercase copy for search index

**Dedup key:** `(nama_perusahaan, nama_produk, spesifikasi)` — in database, add UNIQUE constraint on this combo.

**Error handling:**
- Missing required field → skip row, log warning with context
- Malformed date → skip row, log error
- Unknown columns → log warning, do not fail

## 10. Search behavior

Two-stage:

1. **FTS5 candidate retrieval**. MATCH query with the configured tokenizer. Query expansion: input tokens augmented with synonym variants from the `synonym` table. Return top N = 500 by FTS5 rank.
2. **Rerank**. `rapidfuzz.fuzz.token_set_ratio` against the original query. Final score combines: rerank score (50%) + TKDN% (20%) + recency boost (15%) + validity-active boost (15%). Weights live in `constants.py`.

Synonyms are expanded at query time, not index time. This keeps the index small and synonym edits cheap (no re-indexing).

Filter pushdown: WHERE clauses on validity, TKDN%, KBLI applied at the SQL level before rerank, not in Python.

## 10. Scheduler

APScheduler in-process. One job: `refresh_all_years` running on the cron from `config.schedule.cron`.

Stagger downloads with a small sleep (default 5s) to avoid hammering P3DN.

On failure:

- Log with full context.
- Persist the error in `download_run`.
- Surface on admin UI.
- Do not crash the app. Continue serving searches against the previous successful dataset.

## 11. Testing

- `pytest` + `pytest-asyncio`.
- Fixtures in `tests/fixtures/` include real but anonymized Excel samples per year. Hand-craft if scrubbing real data is sensitive.
- Mock HTTP via `respx` (httpx-compatible).
- Coverage target: 80% on `parser.py`, `merger.py`, `search.py`. Routes can be lower.
- Each parser test should exercise: happy path, missing required field, extra unknown column, malformed date, duplicate cert number across years.
- Each search test should exercise: typo, partial match, multi-token AND, synonym hit, filter combinations, empty result.

Run:

```bash
pytest
pytest --cov=src/tkdn_finder --cov-report=term-missing
```

## 12. Common commands

```bash
# install (preferred: uv)
uv sync

# or pip
pip install -e ".[dev]"

# run dev server
uvicorn tkdn_finder.main:app --reload --port 8000

# build Tailwind CSS (one-time for prod)
npx tailwindcss -i src/tkdn_finder/static/css/input.css -o src/tkdn_finder/static/css/app.css --minify

# format + lint
ruff check --fix .
black .

# type check
mypy --strict src/tkdn_finder

# test
pytest

# build PyInstaller .exe (Windows)
pyinstaller build.spec
# → output in dist/tkdn-finder.exe

# run built .exe
./dist/tkdn-finder.exe
```

## 13. Packaging and deployment

**MVP target: Windows .exe (PyInstaller)**

```bash
# Install build dependencies
pip install pyinstaller

# Build (creates tkdn-finder.exe in dist/)
pyinstaller build.spec

# Run
./dist/tkdn-finder.exe
  → Auto-opens http://localhost:8000 in default browser
  → Data stored in %APPDATA%/TKDN-Finder/
  → Logs in %APPDATA%/TKDN-Finder/logs/

# Optionally: create Windows shortcut to dist/tkdn-finder.exe
```

**Alternative for Linux:**

systemd service wrapping the Python venv or standalone PyInstaller build:

```ini
# /etc/systemd/system/tkdn-finder.service
[Unit]
Description=TKDN Finder
After=network.target

[Service]
Type=simple
User=tkdn
ExecStart=/home/tkdn/tkdn-finder/dist/tkdn-finder
Restart=on-failure
Environment="TKDN_DATA_DIR=/home/tkdn/.tkdn-finder"

[Install]
WantedBy=multi-user.target
```

Then `systemctl start tkdn-finder && systemctl enable tkdn-finder`

**build.spec** (PyInstaller config):
- Bundle: FastAPI, Uvicorn, SQLite, BeautifulSoup, all deps
- Hidden imports: `['openpyxl', 'starlette.datastructures']` (FastAPI internals)
- One-file: yes (single .exe)
- Console: no (GUI-ish, but CLI logs hidden)
- Icon: optional (tkdn.ico if exists)
- Runtime tmpdir: use temp, not roaming profile## 14. Anti-patterns and what not to do

- Do not call external LLMs for search reranking in MVP. Adds latency, cost, complexity. rapidfuzz handles the cases that matter.
- Do not use an ORM for FTS5 queries. Raw SQL is clearer and the FTS5 syntax is non-standard.
- Do not skip schema-drift detection on parse. P3DN may rename columns without notice. Fail loud, do not silently drop.
- Do not delete raw downloaded files immediately after a successful parse. Keep the last N runs.
- Do not log full download URLs at INFO. Redact the `thn=` token. Treat it as a low-sensitivity credential.
- Do not store search queries with personally identifying content. None are expected, but the policy stays.
- Do not introduce a background message queue, Redis, or Celery in MVP. APScheduler in-process is enough.
- Do not write the cron string as a literal in code. It lives in config.

## 15. Workflow when extending features

1. Re-read the relevant PRD section.
2. Add or update values in `constants.py`.
3. Update the data model and migration if the schema changes.
4. Write tests first: parser test with a sample Excel row, search test with a seeded DB.
5. Implement.
6. Run `ruff`, `black`, `mypy`, `pytest`. All must be clean.
7. Update `README.md` if anything is user-facing.
8. Update this `CLAUDE.md` if conventions changed.
9. Open PR with a description that explains: what changed, why, what was tested.

## 16. Known unknowns (track until resolved)

| Item | Owner | Status |
|---|---|---|
| Are P3DN `thn=...` tokens stable across months? | Irsan to test | Open |
| Does P3DN expose a per-cert detail URL pattern? | Irsan to verify | Open |
| Total record volume across 3 years | Measure on first ingest | Open |
| P3DN ToS regarding automated download | Irsan to review | Open |
| Notification channel (Telegram bot?) | Irsan decision | Open |
