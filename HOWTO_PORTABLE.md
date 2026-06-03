# Panduan Penggunaan TKDN Finder
### Versi Portable — Tanpa Instalasi

---

## TKDN Finder itu apa?

TKDN Finder adalah alat pencarian sertifikat TKDN (Tingkat Komponen Dalam Negeri) yang diterbitkan oleh Kemenperin. Dengan alat ini, Anda bisa mencari produk beserta nilai TKDN-nya dengan cepat — cukup lewat browser seperti membuka website biasa.

---

## Yang Anda butuhkan

- Komputer Windows 10 atau Windows 11
- Koneksi internet (untuk pertama kali mengunduh data)
- Tidak perlu instal Python, tidak perlu instal apapun

---

## LANGKAH 1 — Ekstrak file ZIP

Setelah mendapatkan file `tkdn-finder-portable.zip`:

1. Klik kanan file ZIP tersebut
2. Pilih **"Extract All…"** (atau "Ekstrak Semua")
3. Pilih lokasi penyimpanan, misalnya di **Desktop** atau folder **Dokumen**
4. Klik **"Extract"**

Setelah selesai, akan muncul folder baru berisi beberapa file.

> **Penting:** Jangan jalankan aplikasi langsung dari dalam file ZIP. Harus diekstrak dulu.

---

## LANGKAH 2 — Jalankan aplikasi

Buka folder hasil ekstrak, lalu **klik dua kali** file bernama **`run.bat`**.

Akan muncul jendela hitam (command prompt) dengan tulisan:

```
Starting TKDN Finder...
Buka browser di http://localhost:8000
```

**Biarkan jendela hitam ini tetap terbuka.** Jangan ditutup selama masih menggunakan aplikasi.

---

### Muncul peringatan dari Windows?

Jika Windows menampilkan pesan seperti ini:

> *"Windows protected your PC"* atau *"Windows melindungi PC Anda"*

Ini normal. Klik **"More info"** (atau "Informasi selengkapnya"), lalu klik **"Run anyway"** (atau "Tetap jalankan").

Pesan ini muncul karena aplikasi ini tidak dijual secara komersial, bukan karena berbahaya.

---

### Antivirus memblokir?

Jika antivirus (seperti Windows Defender, Smadav, dll.) memblokir file `tkdn-finder.exe`:

1. Buka pengaturan antivirus Anda
2. Tambahkan folder TKDN Finder ke daftar **pengecualian** (exclusion / whitelist)
3. Coba jalankan `run.bat` lagi

---

## LANGKAH 3 — Buka di browser

Buka browser Anda (Chrome, Edge, atau Firefox), lalu ketik di kolom alamat:

```
http://localhost:8000
```

Tekan Enter. Halaman TKDN Finder akan muncul.

---

## LANGKAH 4 — Tunggu data selesai diunduh (khusus pertama kali)

Saat **pertama kali** dijalankan, aplikasi akan otomatis mengunduh data TKDN dari website Kemenperin. Proses ini membutuhkan waktu sekitar **5–15 menit** tergantung kecepatan internet.

Selama proses berlangsung, Anda bisa memantau progressnya di halaman **Admin**:

```
http://localhost:8000/admin
```

Setelah selesai, data langsung bisa dicari. Tidak perlu mengunduh lagi di lain waktu kecuali ingin memperbarui data.

---

## Cara mencari sertifikat TKDN

1. Ketik nama produk atau nama perusahaan di kolom pencarian
2. Hasil pencarian muncul otomatis saat Anda mengetik
3. Pencarian tidak harus tepat — typo atau kata dalam bahasa Inggris tetap bisa ditemukan
   - Contoh: ketik **"pompa"** → bisa menemukan "pump", "centrifugal pump"
   - Contoh: ketik **"valve"** → bisa menemukan "katup"

### Filter yang tersedia

| Filter | Fungsi |
|--------|--------|
| **TKDN Min (%)** | Tampilkan hanya produk dengan nilai TKDN di atas angka tertentu |
| **Hanya yang masih berlaku** | Sembunyikan sertifikat yang sudah kadaluarsa |
| **KBLI** | Filter berdasarkan jenis industri |
| **Tahun** | Filter berdasarkan tahun penerbitan sertifikat |

### Arti warna status sertifikat

| Warna | Arti |
|-------|------|
| **Hijau — Berlaku** | Sertifikat masih aktif |
| **Kuning — Segera Berakhir** | Akan habis dalam 60 hari, perlu konfirmasi ke vendor |
| **Merah — Kadaluarsa** | Sudah tidak berlaku |

---

## Cara mengunduh hasil pencarian ke Excel

Setelah melakukan pencarian, klik tombol **"Unduh Excel"**. File `.xlsx` akan otomatis terunduh ke folder Downloads Anda, siap digunakan sebagai lampiran dokumen pengadaan.

---

## Cara memperbarui data TKDN

Data tidak diperbarui otomatis secara default. Untuk mengunduh data terbaru dari Kemenperin:

1. Buka `http://localhost:8000/admin`
2. Klik tombol **"Refresh / Download Data"**
3. Tunggu hingga proses selesai (5–15 menit)

---

## Cara menghentikan aplikasi

Klik jendela hitam (command prompt), lalu tekan **Ctrl + C** pada keyboard. Atau tutup saja jendela hitam tersebut.

Untuk menggunakan kembali, klik dua kali `run.bat` lagi.

---

## Masalah umum

### Browser menampilkan "This site can't be reached"

Pastikan jendela hitam (command prompt) masih terbuka. Jika sudah tertutup, jalankan `run.bat` lagi, lalu refresh browser.

### Data tidak bisa diunduh / error saat download

Jika jaringan kantor menggunakan proxy atau firewall ketat, coba:

1. Di folder yang sama dengan `tkdn-finder.exe`, buat file baru bernama **`config.yaml`**
2. Isi file tersebut dengan teks berikut, lalu simpan:

```
p3dn:
  verify_ssl: false
```

3. Tutup dan jalankan ulang `run.bat`

Jika masih bermasalah, hubungi tim IT kantor untuk meminta akses ke `p3dn.kemenperin.go.id`.

### "Port already in use" atau tidak bisa jalan

Kemungkinan aplikasi sudah berjalan di background. Restart komputer, lalu coba lagi.

---

## Di mana data tersimpan?

Data tersimpan otomatis di folder sistem Windows, **terpisah** dari folder aplikasi:

```
C:\Users\[nama-user]\AppData\Roaming\TKDN-Finder\
```

Artinya jika folder aplikasi dihapus atau dipindah, **data tidak hilang**. Dan jika ingin pindah komputer, cukup salin folder tersebut ke komputer baru.

---

## Cara update ke versi terbaru

1. Unduh file `tkdn-finder-portable.zip` versi terbaru
2. Ekstrak dan **timpa** folder lama
3. Jalankan `run.bat` seperti biasa

Data yang sudah ada tidak akan hilang.

---

*Data bersumber dari [Kemenperin P3DN](https://p3dn.kemenperin.go.id) — dikembangkan oleh Irsan H. Fadjri untuk kebutuhan pengadaan PHR.*
