# TKDN Finder — Detailed Development Plan

**Project Owner:** Irsan H. H. Fadjri (PHR Procurement)
**Start Date:** 2026-05-28
**Target MVP Release:** 2026-06-10 (2 weeks)
**Deployment:** Windows .exe (PyInstaller)

---

## Phase 1: Project Setup & Infrastructure (Day 1)

### 1.1 Repository & Environment
- [ ] Create GitHub repo: `tkdn-finder` (or local git)
- [ ] Initialize Python project structure:
  ```
  tkdn-finder/
  ├── pyproject.toml (Python 3.11, FastAPI, SQLite, BeautifulSoup, etc.)
  ├── src/tkdn_finder/
  ├── tests/
  ├── migrations/
  ├── data/
  └── .gitignore
  ```
- [ ] Create `pyproject.toml` with dependencies:
  ```
  fastapi==0.104+
  uvicorn==0.24+
  sqlalchemy==2.0+ (for migrations, optional for MVP)
  beautifulsoup4==4.12+
  httpx==0.25+
  apscheduler==3.10+
  rapidfuzz==3.5+
  pydantic-settings==2.0+
  pytest==7.4+
  pytest-asyncio==0.21+
  respx==0.20+ (mock HTTP for tests)
  pyinstaller==6.0+
  ```
- [ ] Setup `uv` package manager (or pip venv)
- [ ] Create `.env.example` and `config.example.yaml`

### 1.2 Database & Schema
- [ ] Create `src/tkdn_finder/db.py`:
  - SQLite connection helper
  - Schema initialization (CREATE TABLE if not exists)
  - Migration version tracking
- [ ] Create `migrations/001_initial.sql`:
  ```sql
  CREATE TABLE tkdn_certificate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_perusahaan TEXT NOT NULL,
    nama_produk TEXT NOT NULL,
    spesifikasi TEXT NOT NULL,
    merek TEXT,
    tipe TEXT,
    nilai_tkdn REAL,
    kode_hs TEXT,
    kbli TEXT,
    kelompok_barang TEXT,
    alamat TEXT,
    provinsi TEXT,
    masa_berlaku_akhir DATE,
    tahun_sumber INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_json TEXT,
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi)
  );
  
  CREATE VIRTUAL TABLE tkdn_search USING fts5(
    nama_perusahaan, nama_produk, merek, spesifikasi, kbli,
    tokenize='porter unicode61 remove_diacritics 2'
  );
  
  CREATE TABLE download_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label TEXT,
    source_url TEXT,
    status TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    row_count INTEGER,
    error_message TEXT
  );
  
  CREATE TABLE synonym (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical TEXT UNIQUE,
    variants TEXT,
    enabled BOOLEAN DEFAULT 1
  );
  ```

---

## Phase 2: Core Data Pipeline (Days 2-5)

### 2.1 Constants & Configuration
- [ ] Create `src/tkdn_finder/constants.py`:
  - All magic values (timeouts, retry counts, column maps, etc.)
  - HTML_COLUMN_MAP (12 columns)
  - Date formats, regex patterns
  - Default thresholds (TKDN %, expiring days, etc.)
- [ ] Create `src/tkdn_finder/config.py`:
  - Pydantic Settings model
  - Load from `.env` and `config.yaml`
  - Validate on startup

### 2.2 Scraper Module
- [ ] Create `src/tkdn_finder/scraper.py`:
  - `discover_download_urls()` — scrape P3DN homepage
  - `discover_with_fallback()` — with cache fallback
  - Extract year from link text (regex)
  - Build full URLs (handle relative/absolute)
  - Error handling & logging
- [ ] Create `tests/test_scraper.py`:
  - Test with fixture HTML (P3DN homepage structure)
  - Mock httpx.AsyncClient
  - Test year extraction, URL building, error cases

### 2.3 Downloader Module
- [ ] Create `src/tkdn_finder/downloader.py`:
  - `download_file(url, year)` — async download
  - Rename to `tkdn_{year}.html` (ignore server filename)
  - Retry logic (3x with 5s backoff)
  - Hash-based change detection (skip if content unchanged)
  - Logging per download
- [ ] Create `tests/test_downloader.py`:
  - Mock HTTP responses
  - Test retry logic
  - Test file naming

### 2.4 Parser Module
- [ ] Create `src/tkdn_finder/parser.py`:
  - `parse_html_export(file_path, year)` — BeautifulSoup
  - Extract HTML table, map columns per HTML_COLUMN_MAP
  - Normalize: whitespace, empty/dash to None, TKDN float, date parse
  - Compute `is_valid_today` from `masa_berlaku_akhir`
  - Error handling (missing required fields, malformed dates)
  - Return list[dict] normalized rows
- [ ] Create `tests/test_parser.py`:
  - Test with real P3DN HTML samples (provided)
  - Test column mapping, normalization
  - Test error cases (missing column, bad date, etc.)

### 2.5 Merger Module
- [ ] Create `src/tkdn_finder/merger.py`:
  - `merge_and_dedupe(rows_list_by_year)` — combine all years
  - Dedupe by (nama_perusahaan, nama_produk, spesifikasi)
  - Keep latest by `tahun_sumber` + `ingested_at`
  - Upsert into DB (INSERT OR REPLACE on UNIQUE constraint)
  - Log stats (total rows, duplicates found, inserted/updated)
- [ ] Create `tests/test_merger.py`:
  - Test dedup logic with sample data
  - Test upsert (new rows, update existing)

---

## Phase 3: Search & Indexing (Days 6-7)

### 3.1 Search Module
- [ ] Create `src/tkdn_finder/search.py`:
  - `search(query, filters)` — multi-stage search
  - Stage 1: FTS5 MATCH query + synonym expansion
  - Stage 2: rapidfuzz rerank (token_set_ratio)
  - Apply filters: TKDN min, validity status, KBLI, year
  - Sort: relevance (default), TKDN% desc, validity desc
  - Pagination support (limit, offset)
  - Return ranked result list with scores
- [ ] Synonym management:
  - Load from DB table `synonym`
  - Bidirectional expansion (canonical ↔ variants)
  - Hot-reload on save (no app restart needed)
  - Default seeds in constants

### 3.2 Search Routes
- [ ] Create `src/tkdn_finder/routes/search.py`:
  - `GET /search` — HTML page (HTMX)
  - `GET /api/search` — JSON API
  - Query param: `q` (search), filters (tkdn_min, validity, kbli, year)
  - Response: paginated results, total count, facets

---

## Phase 4: Web UI & Admin (Days 8-9)

### 4.1 Frontend
- [ ] Create `src/tkdn_finder/templates/base.html`:
  - Layout (header, search bar, footer)
  - Tailwind CSS (CDN or built)
  - Alpine.js for interactivity
- [ ] Create `src/tkdn_finder/templates/index.html`:
  - Search box (debounced 250ms)
  - Filter sidebar (TKDN min, validity, KBLI)
  - Results list (HTMX partial swap)
  - Result row: product name, company, TKDN%, validity badge, expand detail
- [ ] Create `src/tkdn_finder/templates/results.html` (HTMX partial):
  - Result list rows
  - Pagination
  - Empty state guidance
- [ ] Create `src/tkdn_finder/templates/detail.html`:
  - Full cert details (all 12 fields)
  - Validity status + date
  - Raw JSON (collapsible)
  - Copy certificate info button

### 4.2 Admin Page
- [ ] Create `src/tkdn_finder/templates/admin.html`:
  - Last refresh timestamp per year (2024, 2025, 2026)
  - Status: success/failed with error message
  - Row counts per year
  - Next scheduled refresh time
  - Manual "Refresh Now" button
  - Download run history table (last 10 runs)
  - Synonym management (edit, reload)
- [ ] Create `src/tkdn_finder/routes/admin.py`:
  - `GET /admin` — admin page
  - `POST /admin/refresh` — trigger manual refresh
  - `GET /admin/api/status` — JSON status
  - `POST /admin/api/synonyms` — update synonyms

### 4.3 Export
- [ ] Create `src/tkdn_finder/routes/export.py`:
  - `GET /export.xlsx` — export filtered results
  - Build Excel file with openpyxl or pandas
  - Header sheet: search query, filters, timestamp, app version
  - Data sheet: results with all columns
  - Response: file download

---

## Phase 5: Scheduling & Automation (Day 10)

### 5.1 Scheduler
- [ ] Create `src/tkdn_finder/scheduler.py`:
  - APScheduler setup
  - Job: `refresh_all_years()` — full pipeline
  - Cron: "0 2 * * *" (daily 02:00 WIB)
  - Error handling: log, persist to DB, surface in admin UI
  - Do NOT crash app on failure; use cached URLs if available
  - Manual trigger endpoint
- [ ] Job flow:
  1. Call scraper → discover URLs (or use cache)
  2. For each year: download → parse → dedupe
  3. Log each step (started, finished, counts, errors)
  4. Alert admin if any step fails

### 5.2 Health & Monitoring
- [ ] Create `src/tkdn_finder/routes/health.py`:
  - `GET /health` — app health status
  - Check: DB connection, last refresh time, error count
  - Response: 200 if OK, 503 if issues
  - `GET /metrics` — Prometheus format (optional)

---

## Phase 6: Main App & Integration (Day 11)

### 6.1 FastAPI App
- [ ] Create `src/tkdn_finder/main.py`:
  - FastAPI app initialization
  - CORS config (allow localhost)
  - Database initialization on startup
  - Scheduler start on startup
  - Mount static files (CSS, JS)
  - Include routes (search, admin, export, health)
  - Auto-open browser on startup (webbrowser.open)
  - Exception handlers (404, 500, etc.)

### 6.2 Models
- [ ] Create `src/tkdn_finder/models.py`:
  - Pydantic models for API I/O
  - SearchRequest, SearchResponse
  - CertDetail, AdminStatus, DownloadRun
  - Validation, serialization

---

## Phase 7: Testing & QA (Day 12)

### 7.1 Unit Tests
- [ ] Scraper: 100% coverage (discover URLs, error cases, fallback)
- [ ] Parser: 100% coverage (column mapping, normalization, errors)
- [ ] Merger: 90%+ coverage (dedup, upsert logic)
- [ ] Search: 80%+ coverage (FTS5, filtering, reranking)

### 7.2 Integration Tests
- [ ] End-to-end: scrape → download → parse → merge → search
- [ ] Test with real P3DN HTML samples (provided)
- [ ] Test all error cases (network failure, bad data, etc.)

### 7.3 Manual Testing
- [ ] Search functionality: typo, partial match, multi-keyword, filters
- [ ] Admin page: manual refresh, status display
- [ ] Export: Excel file generation with correct data
- [ ] UI responsiveness: desktop + mobile (380px)

---

## Phase 8: Packaging & Deployment (Day 13)

### 8.1 PyInstaller Build
- [ ] Create `build.spec`:
  - Entry point: `src/tkdn_finder/main.py`
  - One-file: True
  - Console: False (GUI, no console)
  - Hidden imports: FastAPI, Uvicorn, SQLite, etc.
  - Bundle icon (optional)
  - Output: `dist/tkdn-finder.exe`
- [ ] Build & test locally:
  ```bash
  pyinstaller build.spec
  ./dist/tkdn-finder.exe
  ```

### 8.2 Windows Shortcut
- [ ] Create `.bat` file for easy launch:
  ```batch
  @echo off
  start "" "%~dp0dist\tkdn-finder.exe"
  ```

### 8.3 Data Folder Setup
- [ ] Create `%APPDATA%/TKDN-Finder/` on first run
- [ ] Store DB, config, logs there
- [ ] Document path in README

---

## Phase 9: Documentation (Day 14)

### 9.1 README
- [ ] Project overview
- [ ] Quick start (download .exe, double-click)
- [ ] Features list
- [ ] FAQ (common questions)
- [ ] Support/contact

### 9.2 User Guide (optional, post-MVP)
- [ ] How to search
- [ ] Filters explanation
- [ ] Export usage
- [ ] Troubleshooting

---

## Dependencies Checklist

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.104+ | Web framework |
| uvicorn | 0.24+ | ASGI server |
| sqlalchemy | 2.0+ | ORM (migrations) |
| beautifulsoup4 | 4.12+ | HTML parsing |
| httpx | 0.25+ | Async HTTP |
| apscheduler | 3.10+ | Scheduling |
| rapidfuzz | 3.5+ | Fuzzy matching |
| pydantic-settings | 2.0+ | Config management |
| jinja2 | 3.1+ | Template rendering |
| pytest | 7.4+ | Testing |
| pytest-asyncio | 0.21+ | Async test support |
| respx | 0.20+ | HTTP mocking |
| pyinstaller | 6.0+ | Executable packaging |
| python-dateutil | 2.8+ | Date utilities |
| openpyxl | 3.1+ | Excel file creation (export) |

---

## Daily Standup Checklist

### Day 1 (Setup)
- [ ] Project structure created
- [ ] Dependencies installed
- [ ] DB schema designed & tested
- [ ] git repo initialized

### Day 2-5 (Pipeline)
- [ ] Scraper working (mock + real test)
- [ ] Downloader working (file rename, retry)
- [ ] Parser working (all 12 columns, normalization)
- [ ] Merger working (dedup, upsert)

### Day 6-7 (Search)
- [ ] FTS5 index built
- [ ] Search API returning results
- [ ] Filters working
- [ ] Ranking/relevance tuned

### Day 8-9 (UI)
- [ ] Search page responsive
- [ ] Admin page shows status
- [ ] Export generates Excel
- [ ] Mobile responsive

### Day 10 (Scheduler)
- [ ] APScheduler running
- [ ] Manual trigger working
- [ ] Error handling graceful
- [ ] Fallback cache tested

### Day 11 (Integration)
- [ ] All routes wired
- [ ] App starts without errors
- [ ] Browser auto-opens
- [ ] Static files served

### Day 12 (Testing)
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing complete
- [ ] Coverage 80%+

### Day 13 (Packaging)
- [ ] .exe builds successfully
- [ ] .exe runs standalone (no Python install needed)
- [ ] Data folder setup works
- [ ] Shortcut/launcher ready

### Day 14 (Polish & Release)
- [ ] README complete
- [ ] All docs finalized
- [ ] MVP ready for use
- [ ] Deployment to lo's Windows PC

---

## Git Commit Strategy

Commit per feature, descriptive messages:

```
feat: add scraper module for P3DN URL discovery
feat: add HTML parser for TKDN export
feat: add FTS5 search with synonym support
feat: add admin UI with refresh status
feat: add PyInstaller build spec
docs: add README and user guide
```

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Scraper breaks (P3DN changes page) | Fallback to cached URLs from previous run |
| Download fails (network, 404) | Retry 3x with backoff, use previous data |
| Parser schema drift | Validate columns on every parse, log unknown columns |
| FTS5 ranking insufficient | Add rapidfuzz second-pass rerank; can upgrade to Meilisearch later |
| Windows .exe large | Compress with UPX or accept (typical 150-200MB) |
| User trusts expired cert | Validity badge prominent, default filter excludes expired |

---

## Success Criteria (MVP)

✅ App auto-downloads & indexes 46.5K TKDN certificates
✅ Search returns results in <500ms (p95)
✅ Typo tolerance ("trasnformer" → "transformer")
✅ Filter by TKDN %, validity status, KBLI
✅ Export to Excel with audit header
✅ Admin sees refresh status
✅ Runs as single .exe, no Python install needed
✅ Daily auto-refresh at 02:00 WIB
✅ Graceful error handling (no crashes)

---

## Post-MVP (v0.2+)

- Telegram bot interface
- Watchlist & diff alerts
- Multi-user with auth
- API for n8n integration
- PostgreSQL + Meilisearch (if volume grows)

---

## Contact & Support

**Project Owner:** Irsan H. H. Fadjri
**Email:** irsan@phr.pertamina.com
**Deployment:** Windows PC (PHR)
**Data:** 46,543 TKDN certificates (2024-2026)
