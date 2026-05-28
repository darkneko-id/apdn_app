# src/tkdn_finder/constants.py
"""All magic values live here. Never inline constants in business logic."""

P3DN_HOMEPAGE_URL = "https://p3dn.kemenperin.go.id/rekap.php"
EXPORT_LINK_HREF_PATTERN = r"export_excel\.php"
YEAR_EXTRACTION_PATTERN = r"(\d{4})"
DEFAULT_USER_AGENT = "TKDN-Finder/0.1 (procurement tooling)"

SCRAPER_TIMEOUT_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 120
DOWNLOAD_RETRY_COUNT = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 5
RAW_RETENTION_COUNT = 7

# Source column header (from P3DN HTML) -> internal field name.
# P3DN exports 12 columns, order fixed. When headers change, edit ONLY here.
HTML_COLUMN_MAP: dict[str, str] = {
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

REQUIRED_FIELDS: tuple[str, ...] = ("nama_perusahaan", "nama_produk", "spesifikasi")
DATE_FORMAT = "%Y-%m-%d"

FTS_TOKENIZER = "porter unicode61 remove_diacritics 2"

VALIDITY_EXPIRING_SOON_DAYS = 60
TKDN_DEFAULT_MIN_FILTER = 0.0

SEARCH_RESULT_LIMIT_DEFAULT = 50
SEARCH_RESULT_LIMIT_MAX = 500
SEARCH_DEBOUNCE_MS = 250

RERANK_WEIGHT_FUZZY = 0.50
RERANK_WEIGHT_TKDN = 0.20
RERANK_WEIGHT_RECENCY = 0.15
RERANK_WEIGHT_VALIDITY = 0.15
FTS_CANDIDATE_LIMIT = 500

# TKDN value sentinel meaning "not applicable" in the source data
TKDN_SENTINEL_VALUE = 999.99

DEFAULT_SYNONYM_SEEDS: dict[str, list[str]] = {
    "valve": ["katup", "valv"],
    "pipe": ["pipa"],
    "transformer": ["trafo"],
    "electric motor": ["motor listrik"],
    "cable": ["kabel"],
    "pump": ["pompa"],
}
