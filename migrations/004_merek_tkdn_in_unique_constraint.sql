-- Migration 004: Replace masa_berlaku_akhir in unique constraint with merek
-- and nilai_tkdn. This allows rows that share (company, product, spec, tipe)
-- but differ in brand or TKDN value to coexist — which is the real-world case
-- for certificates like PT Nandya where tipe is empty from the P3DN bulk export
-- but merek and nilai_tkdn differ across rows.
--
-- New key: (nama_perusahaan, nama_produk, spesifikasi, tipe, merek, nilai_tkdn)
-- merek is also coerced to NOT NULL DEFAULT '' in merger before insert.

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
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi, tipe, merek, nilai_tkdn)
);

INSERT INTO tkdn_certificate_new
    SELECT id, nama_perusahaan, nama_produk,
           COALESCE(spesifikasi, ''),
           COALESCE(merek, ''),
           COALESCE(tipe, ''),
           nilai_tkdn, kode_hs, kbli, kelompok_barang,
           alamat, provinsi, masa_berlaku_akhir,
           tahun_sumber, ingested_at
    FROM tkdn_certificate;

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

INSERT OR IGNORE INTO schema_version (version) VALUES (4);

COMMIT;
PRAGMA foreign_keys=ON;
