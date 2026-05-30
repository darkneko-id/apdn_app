-- Migration 005: Remove tipe from unique constraint.
--
-- Problem: tipe is always '' in P3DN bulk export. After tipe enrichment updates
-- a row's tipe to a real value (e.g. 'Cable Ladder SLHD'), the row's dedup key
-- changes. A subsequent P3DN re-download then inserts a new tipe='' row instead
-- of updating the enriched row, creating duplicates.
--
-- Fix: dedup key becomes (nama_perusahaan, nama_produk, spesifikasi, merek,
-- nilai_tkdn). Tipe is a plain column updated freely by the enricher.
-- The merger preserves enriched tipe on re-download via CASE in DO UPDATE.

PRAGMA foreign_keys=OFF;
BEGIN;

CREATE TABLE tkdn_certificate_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_perusahaan     TEXT NOT NULL,
    nama_produk         TEXT NOT NULL,
    spesifikasi         TEXT NOT NULL DEFAULT '',
    merek               TEXT NOT NULL DEFAULT '',
    tipe                TEXT NOT NULL DEFAULT '',
    nilai_tkdn          REAL,
    kode_hs             TEXT,
    kbli                TEXT,
    kelompok_barang     TEXT,
    alamat              TEXT,
    provinsi            TEXT,
    masa_berlaku_akhir  DATE,
    tahun_sumber        INTEGER,
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn)
);

INSERT OR IGNORE INTO tkdn_certificate_new
    SELECT id, nama_perusahaan, nama_produk,
           COALESCE(spesifikasi, ''),
           COALESCE(merek, ''),
           COALESCE(tipe, ''),
           nilai_tkdn, kode_hs, kbli, kelompok_barang,
           alamat, provinsi, masa_berlaku_akhir,
           tahun_sumber, ingested_at
    FROM tkdn_certificate
    ORDER BY id;

DROP TRIGGER IF EXISTS tkdn_ai;
DROP TRIGGER IF EXISTS tkdn_ad;
DROP TRIGGER IF EXISTS tkdn_au;
DROP TABLE IF EXISTS tkdn_search;
DROP TABLE tkdn_certificate;
ALTER TABLE tkdn_certificate_new RENAME TO tkdn_certificate;

CREATE VIRTUAL TABLE tkdn_search USING fts5(
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

INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    SELECT id, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang
    FROM tkdn_certificate;

CREATE TRIGGER tkdn_ai AFTER INSERT ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TRIGGER tkdn_ad AFTER DELETE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
END;

CREATE TRIGGER tkdn_au AFTER UPDATE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

INSERT OR IGNORE INTO schema_version (version) VALUES (5);

COMMIT;
PRAGMA foreign_keys=ON;
