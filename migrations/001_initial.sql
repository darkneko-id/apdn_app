-- Migration 001: Initial schema
-- Applies idempotently via CREATE IF NOT EXISTS

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tkdn_certificate (
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
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi)
);

CREATE VIRTUAL TABLE IF NOT EXISTS tkdn_search USING fts5(
    nama_perusahaan,
    nama_produk,
    merek,
    spesifikasi,
    kbli,
    kelompok_barang,
    content='tkdn_certificate',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS tkdn_ai AFTER INSERT ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TRIGGER IF NOT EXISTS tkdn_ad AFTER DELETE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
END;

CREATE TRIGGER IF NOT EXISTS tkdn_au AFTER UPDATE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TABLE IF NOT EXISTS download_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label TEXT,
    source_url TEXT,
    status TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    row_count INTEGER,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS synonym (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical TEXT UNIQUE NOT NULL,
    variants TEXT NOT NULL,
    enabled INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
