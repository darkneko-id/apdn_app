-- Migration 009: Add tipe back to UNIQUE constraint.
--
-- Problem (migration 005 side-effect): UNIQUE(company, produk, spec, merek, nilai_tkdn)
-- without tipe means the enricher cannot INSERT multiple tipe variants (T1, T2, T3)
-- for the same product when they share the same nilai_tkdn — INSERT OR IGNORE silently
-- drops T2 and T3 after T1 is already present.
--
-- Fix: UNIQUE(company, produk, spec, merek, nilai_tkdn, tipe) lets each tipe variant
-- live as its own row. The merger gains a pre-check: when P3DN re-imports with tipe='',
-- if enriched variants already exist for the same (company, produk, spec, merek,
-- nilai_tkdn), it updates their metadata in-place instead of inserting a redundant
-- tipe='' row. See merger.py for the corresponding Python change.

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
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn, tipe)
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
    tipe,
    spesifikasi,
    kbli,
    kelompok_barang,
    content='tkdn_certificate',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    SELECT id, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang
    FROM tkdn_certificate;

CREATE TRIGGER tkdn_ai AFTER INSERT ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.tipe, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TRIGGER tkdn_ad AFTER DELETE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.tipe, old.spesifikasi, old.kbli, old.kelompok_barang);
END;

CREATE TRIGGER tkdn_au AFTER UPDATE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.tipe, old.spesifikasi, old.kbli, old.kelompok_barang);
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.tipe, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

INSERT OR IGNORE INTO schema_version (version) VALUES (9);

COMMIT;
PRAGMA foreign_keys=ON;
