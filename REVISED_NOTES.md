# REVISI BERDASARKAN DATA AKTUAL P3DN

## Key Findings

1. **Format**: P3DN export as HTML table dalam file `.xls`, bukan binary Excel
2. **Columns**: 12 fixed columns (sama di semua tahun)
   - Kode HS, KBLI, Kelompok Barang, Nama Perusahaan, Alamat, Provinsi
   - Produk, Spesifikasi, Tipe, Merk, Nilai TKDN (%), Tanggal Kadaluarsa Sertifikat
3. **Volume**: 46,543 rows total (4.6K + 22K + 19.8K), SQLite FTS5 sufficient
4. **Natural Key**: `(Nama Perusahaan, Produk, Spesifikasi)` ← NO cert number field!
5. **Duplicates**: 3,247 duplikat found, will dedup by natural key
6. **Date Format**: YYYY-MM-DD (consistent, no parse variance)

## Changes to PRD/CLAUDE.md

### Stack changes:
- ✅ BeautifulSoup4 (HTML parsing)
- ❌ Remove openpyxl/pandas (Excel parsing)
- ✅ PyInstaller (instead of Docker)
- ✅ No Dockerfile, no docker-compose

### Data model:
- Natural key = (nama_perusahaan, nama_produk, spesifikasi)
- Remove: nilai_bmp, masa_berlaku_mulai, nomor_sertifikat, bidang_industri
- Add: kode_hs, kelompok_barang, alamat, provinsi

### Parser:
- Use BeautifulSoup to extract HTML table
- 12 column mapping (fixed)
- Date parse: simple YYYY-MM-DD (no variance)
- Dedup by natural key

### UI impact:
- Cert detail URL: show company+product summary (no single cert number to link)
- Export: include all 12 columns

### Deployment:
- PyInstaller build → tkdn-finder.exe (Windows)
- Auto-open browser on startup
- Data folder: %APPDATA%/TKDN-Finder/ (Windows)
- systemd unit for Linux alternative

## Next steps for coding:
1. Update constants.py with actual column map
2. Write parser.py for BeautifulSoup
3. Update db.py schema to match 12-column model
4. Build PyInstaller spec
5. Test with sample HTML files (provided)
