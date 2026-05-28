# PRD: TKDN Finder

| Field | Value |
|---|---|
| Version | 0.1 (Draft) |
| Author | Irsan H. H. Fadjri (PHR Procurement) |
| Status | Draft, pending review |
| Last updated | 2026-05-27 |

---

## 1. Background

PT Pertamina Hulu Rokan (PHR) and other KKKS operating under PTK-007 / Pedoman A7-001 are required to prioritize procurement from vendors holding valid TKDN certificates. The single source of truth for TKDN certification data is the Kemenperin P3DN portal at `https://p3dn.kemenperin.go.id/`.

Current procurement workflow for verifying TKDN coverage during pra-qualification:

1. Open the P3DN portal
2. Type product keyword into the search form
3. If zero results, manually retry with alternate keywords
4. As a fallback, download three yearly Excel exports, open in Excel, use Ctrl+F or filter

### Problems with the status quo

- Portal search returns zero hits when the input keyword does not match the exact phrasing in the product-name field. No fuzzy matching, no token splitting, no synonyms.
- Excel-based search across three separate yearly files forces manual consolidation every time a check is needed.
- Excel has no relevance ranking, no cross-field search (product + spec + manufacturer simultaneously), no validity-status filter.
- High false-negative rate: procurement may conclude "no Indonesian vendor exists for this item" when in fact one or more do, leading to unnecessary international tender, and a possible PTK-007 / A7-001 compliance gap.
- No quick way to filter "valid as of today" vs "expired."

## 2. Goals

**G1.** Provide a single search interface that returns relevant TKDN-certified products across all available years, with typo tolerance and partial-match support.

**G2.** Eliminate manual download of yearly Excel files. App fetches and consolidates automatically on a schedule.

**G3.** Reduce time from "is there a local vendor with TKDN for X?" to a confident answer. Target under 30 seconds per query.

**G4.** Expose validity period (active vs expired vs expiring soon) so procurement does not cite a lapsed certificate.

**G5.** Allow filtered export to .xlsx for attachment to BAHP and other tender documents.

## 3. Non-goals (out of MVP scope)

- Submitting TKDN applications on behalf of vendors
- Computing TKDN values (the verifier's responsibility)
- Real-time integration into PHR ERP or iProc systems
- Multi-tenant SaaS with billing
- Audit log of who searched what (deferred; may be added if compliance requests it)
- OCR or PDF cert parsing (P3DN already structures the data)

## 4. Personas

| Persona | Role | Primary need |
|---|---|---|
| Procurement Analyst (Irsan) | Praqual evaluation, BAHP drafting | Quick "does X exist in TKDN db?" lookup |
| Panitia Tender Member | Tender committee | Verify vendor's claimed certificate exists and is valid |
| User Requester | End-user of goods | Sanity check whether local alternative exists before specifying foreign brand |

## 5. User stories

| ID | Story |
|---|---|
| US-1 | As an analyst, I type "valve gate" and see all gate-valve products with TKDN, ranked by relevance and TKDN%, showing manufacturer, spec, cert number, and validity. |
| US-2 | As a panitia member, I paste a certificate number from a vendor submission and confirm it exists in P3DN and is valid on tender opening date. |
| US-3 | As a requester, I search by manufacturer "PT Krakatau" and see all their TKDN-certified products. |
| US-4 | As an analyst, I filter results to "TKDN ≥ 25%" and "valid today" to match PHR's threshold. |
| US-5 | As admin, I trigger a manual refresh after Kemenperin publishes new data, and see download/parse status per year. |
| US-6 | As an analyst, I export the filtered result set to .xlsx for attachment to BAHP. |
| US-7 | As an analyst, I bookmark a search URL so I can re-run the same query in one click. |

## 6. Functional requirements

### 6.1 Data ingestion

- **FR-1.1** App discovers download URLs by scraping `https://p3dn.kemenperin.go.id/` homepage. Extracts all `export_excel.php?thn=...` links, infers year from link text ("Download TKDN LVI 2024" → 2024). No hardcoded tokens.
- **FR-1.2** Downloads run on a configurable schedule (default: daily at 02:00 WIB).
- **FR-1.3** Manual refresh endpoint for ad-hoc trigger after Kemenperin announces new data.
- **FR-1.4** On download failure (network error, HTTP 4xx/5xx, scraper fails to find links), app logs the error with context, retains the previous successful dataset, and surfaces the failure on the admin page.
- **FR-1.5** Fallback: if scraper fails to discover URLs, app uses cached URLs from the last successful run. If no cache, alert admin and pause downloads until manual intervention.
- **FR-1.6** Raw downloaded files retained for the last N successful runs (default 7) for forensics.

### 6.2 Data processing

- **FR-2.1** Parse all configured sources as HTML tables (P3DN exports as HTML despite `.xls` filename).
- **FR-2.2** Extract 12 standard columns: Kode HS, KBLI, Kelompok Barang, Nama Perusahaan, Alamat, Provinsi, Produk, Spesifikasi, Tipe, Merk, Nilai TKDN (%), Tanggal Kadaluarsa Sertifikat.
- **FR-2.3** Normalize text: collapse whitespace, empty/"-" brand to NULL, lowercase for search index, preserve original for display.
- **FR-2.4** Parse date `Tanggal Kadaluarsa Sertifikat` as `masa_berlaku_akhir` (format YYYY-MM-DD, no parsing variance expected).
- **FR-2.5** Deduplicate by natural key `(nama_perusahaan, nama_produk, spesifikasi)`. When duplicates exist across years, latest source wins, but all historical rows retained in raw_json for audit.
- **FR-2.6** Compute `is_valid_today` from validity end date vs today.

### 6.3 Search

- **FR-3.1** Full-text search across: product name, manufacturer, brand, type/model, specification, certificate number, KBLI label.
- **FR-3.2** Typo tolerance: "trasnformer" returns "transformer" results.
- **FR-3.3** Partial / substring match: "valv" matches "valve."
- **FR-3.4** Multi-keyword AND-by-default: "gate valve 6 inch" requires all tokens to appear (across any indexed field).
- **FR-3.5** Filters: TKDN min %, BMP min %, validity status (active / expired / expiring within 60 days), source year, KBLI.
- **FR-3.6** Sort options: relevance (default), TKDN% desc, validity-end desc, manufacturer A-Z.
- **FR-3.7** Synonym map (Indonesian/English), admin-editable, hot-reload on save. Examples: katup↔valve, pipa↔pipe, motor listrik↔electric motor.
- **FR-3.8** Search response p95 latency under 500ms for a dataset of 100k records.
- **FR-3.9** Empty-state guidance: if zero results, suggest broader keywords and offer to relax filters automatically.

### 6.4 UI

- **FR-4.1** Single search box on landing page. Results stream below as user types (debounced 250ms).
- **FR-4.2** Result row contents: product name, manufacturer, TKDN% badge, BMP% badge, validity badge, cert number, expand-for-detail.
- **FR-4.3** Detail view: full spec, cert number, validity period, KBLI, BMP, raw source row (collapsible JSON), deep-link to P3DN per-cert page if URL pattern is known.
- **FR-4.4** Filter sidebar persistent during search session.
- **FR-4.5** Mobile-responsive (tested at 380px viewport for phone use during meetings).
- **FR-4.6** Indonesian UI labels. No i18n framework needed for MVP.
- **FR-4.7** Search query and active filters reflected in URL query string (shareable / bookmarkable).

### 6.5 Scheduling

- **FR-5.1** Cron-style schedule, configurable. Default daily 02:00 WIB.
- **FR-5.2** Admin page shows per-year: last successful refresh timestamp, row count, last error message, next scheduled run.
- **FR-5.3** Manual "refresh now" button on admin page, runs the same pipeline ad-hoc.

### 6.6 Export

- **FR-6.1** Export current filtered result set to `.xlsx` with same column order as the P3DN original.
- **FR-6.2** Export file includes a header sheet recording: search query string, active filters, export timestamp, app version. For audit traceability when attached to BAHP.

## 7. Non-functional requirements

| Category | Target |
|---|---|
| Availability | Best-effort, single instance. Restart on crash via systemd or Docker `restart=always`. |
| Data freshness | At most 24h behind P3DN under normal conditions. |
| Search latency | p95 under 500ms. |
| Storage footprint | Under 2 GB total (raw .xlsx + SQLite DB). |
| Memory footprint | Under 512 MB resident. |
| Backup | Daily SQLite snapshot rsync'd to homelab NAS. |
| Auth | None for MVP (LAN-only). Add basic auth before any external exposure. |
| Logging | Structured JSON to stdout. Rotation via Docker logging driver. |
| Observability | `/health` and `/metrics` (Prometheus format) endpoints. |

## 8. Technical architecture

### 8.1 Stack

- Backend: Python 3.11+, FastAPI, Uvicorn
- Storage and search: SQLite with FTS5 (single file, zero ops, sufficient for expected volume)
- Optional upgrade path: Meilisearch if FTS5 ranking is found insufficient after MVP usage
- Scheduler: APScheduler in-process for MVP, can migrate to external cron later
- Frontend: HTMX + Tailwind CSS + Alpine.js. No build pipeline. Tailwind via CDN in dev, CLI build in prod.
- Excel parsing: openpyxl for streaming reads; pandas only if data shape requires it
- HTTP client: httpx (async)
- Fuzzy matching: rapidfuzz for synonym expansion and result reranking
- Config: pydantic-settings, reads from `.env` + `config.yaml`
- Containerization: single Dockerfile, `docker compose` for local + deploy
- Deploy target: Proxmox LXC on Irsan's homelab

### 8.2 Component flow

```
[Scheduler]
    └─ triggers ─> [Downloader] ──saves raw .xlsx──> [Parser] ──> [Merger]
                                                                     │
                                                                     ▼
                                                          [SQLite + FTS5]
                                                                     ▲
                                                              [Search service]
                                                                     ▲
                                                              [FastAPI routes]
                                                                     ▲
                                                              [HTMX frontend]
```

### 8.3 Data model

`tkdn_certificate` (canonical record):

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Internal |
| nama_perusahaan | TEXT | Manufacturer / Company |
| nama_produk | TEXT | Product |
| merek | TEXT | Brand (often "-" or empty) |
| tipe | TEXT | Type/model (often empty) |
| spesifikasi | TEXT | Full spec, often long |
| nilai_tkdn | REAL | Percentage |
| kode_hs | TEXT | HS code for tariff classification |
| kbli | TEXT | KBLI industry code |
| kelompok_barang | TEXT | Commodity group |
| alamat | TEXT | Company address |
| provinsi | TEXT | Province |
| masa_berlaku_akhir | DATE | Validity end (from "Tanggal Kadaluarsa Sertifikat") |
| tahun_sumber | INTEGER | Year of the source file (2024/2025/2026) |
| ingested_at | TIMESTAMP | When this row was last upserted |
| raw_json | TEXT | Original row as JSON, for forensics |

**Natural key (unique constraint):** `(nama_perusahaan, nama_produk, spesifikasi)`. Note: no "Nomor Sertifikat" field in P3DN export; this combination identifies unique cert records.

`tkdn_search` (FTS5 virtual table): mirrors the searchable text columns above using porter tokenizer + unicode61 + diacritic removal. Kept in sync with `tkdn_certificate` via triggers.

`download_run`:

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| year_label | TEXT | e.g. "2024" |
| source_url | TEXT | |
| status | TEXT | success / failed / partial |
| started_at | TIMESTAMP | |
| finished_at | TIMESTAMP | |
| row_count | INTEGER | Parsed rows |
| error_message | TEXT | Nullable |

`synonym` (admin-editable):

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| canonical | TEXT | |
| variants | TEXT | JSON array |
| enabled | BOOLEAN | |

### 8.4 Configuration (example)

```yaml
p3dn:
  homepage_url: "https://p3dn.kemenperin.go.id/"
  user_agent: "TKDN-Finder/0.1 (procurement tooling; contact: irsan@phr.pertamina.com)"
  download_timeout_seconds: 60
  retry_count: 3
  retry_backoff_seconds: 5
  # Download URLs discovered automatically by scraper; no hardcoded tokens needed
schedule:
  cron: "0 2 * * *"  # daily 2 AM
storage:
  data_dir: "/data"
  retain_raw_runs: 7
search:
  result_limit_default: 50
  result_limit_max: 500
  expiring_soon_days: 60
```

## 9. Open questions and assumptions

### Open questions (need decision from Irsan)

1. **Vendor lookup mode**: Should the app accept a manufacturer NPWP or NIB and surface all their certificates? Useful for praqual but adds scope.
2. **Cert detail deep-link**: Does P3DN expose a per-cert URL pattern (e.g. `cert/{nomor}`)? If yes, link out from detail view.
3. **Multi-user**: Will Pak Iqbal or other panitia members use this? If yes, add auth in MVP.
4. **Notifications**: Want Telegram bot alerts on (a) download failure, (b) new certificates added in a watched KBLI category?
5. **Scraper rate limit**: Once per day (02:00) is safe? Or can be more frequent?

### Assumptions

| ID | Assumption | Validation plan |
|---|---|---|
| A1 | P3DN exports as HTML table files despite .xls extension. | ✓ Confirmed: 46K+ rows, 12 columns, HTML table structure |
| A2 | Column layout stable across years (2024/2025/2026). | ✓ Confirmed: identical 12 columns across all three files |
| A3 | Date format is consistent YYYY-MM-DD. | ✓ Confirmed: all dates in format 2031-01-08 style |
| A4 | Natural key is `(company, product, spec)` (no cert number field). | ✓ Confirmed: 3,247 duplicates found, will dedupe by this key |
| A5 | Total volume is manageable (tens of thousands). | ✓ Confirmed: 46.5K rows total, SQLite FTS5 sufficient |
| A6 | Public dataset is complete for procurement screening. | Assumption, needs validation post-MVP |

## 10. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| P3DN changes page layout (scraper breaks) | Low | High | Schema-drift detection on scraper; alert admin if no URLs found; fallback to cached URLs from last run. |
| Kemenperin blocks scraper IP | Low | High | Polite User-Agent identifying tool and contact; rate limit (1 req/day); exponential backoff on failure. |
| Schema drift in yearly HTML table | Low | Medium | Schema validation on parse, log unknown columns, fail loudly rather than silently. |
| FTS5 ranking insufficient for fuzzy needs | Medium | Medium | Add rapidfuzz second-pass rerank; migrate to Meilisearch if user feedback demands it. |
| User trusts an expired cert as still valid | Low | High | Validity badge prominent; default filter excludes expired; export marks status clearly. |
| Public dataset is incomplete (some certs not exported) | Medium | Medium | Document this limitation in UI footer; recommend cross-check with portal for high-value tenders. |
| Single-instance crash means no data when needed | Medium | Medium | systemd restart=always; health check; daily DB snapshot. |

## 11. MVP scope vs future

### MVP (v0.1)

- Download, parse, merge 3 configured Excel URLs
- SQLite FTS5 search with admin-editable synonym map
- Single-page HTMX UI with search, filter, result list, detail view
- Daily scheduled refresh + manual trigger
- .xlsx export of filtered results with audit header sheet
- Dockerized, runs on homelab LXC, no auth (LAN only)
- Admin page with run history and error log

### v0.2

- Telegram bot interface (`/tkdn valve gate 6 inch` returns top 5)
- Watchlist with diff alerts ("3 new certificates added in KBLI 28140 since last week")
- Cert detail deep-link to P3DN portal
- Basic auth wrapper for external exposure

### v0.3 and beyond

- Multi-user with SSO or local accounts
- API key for integration with PHR procurement tooling
- Migration to PostgreSQL + Meilisearch if data volume or search complexity demands it
- Read-only API for n8n workflows

## 12. Success metrics

| Metric | Target | Measurement |
|---|---|---|
| Time per TKDN lookup | Under 30s (down from 5-15 min) | Self-report after 1 month of use |
| False-negative reduction | At least 5 cases/month where app finds a vendor the portal search missed | Manual track in a spreadsheet |
| Refresh reliability | At least 95% of scheduled runs succeed | Admin dashboard derived from `download_run` |
| Search latency | p95 under 500ms | Server access logs |
| User adoption (if shared) | All 3 panitia members use at least weekly | Self-report |
