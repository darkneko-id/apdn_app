"""Generate Panduan Instalasi & Penggunaan TKDN Finder as PDF."""

from __future__ import annotations

from fpdf import FPDF

# Colour palette
BLUE_DARK  = (31, 78, 121)   # #1F4E79
BLUE_MID   = (41, 105, 176)  # #2969B0
BLUE_LIGHT = (219, 234, 254) # #DBEAFE
YELLOW_BG  = (254, 249, 195) # #FEF9C3
YELLOW_BR  = (202, 138, 4)   # #CA8A04
GREEN_BG   = (220, 252, 231) # #DCFCE7
GREEN_BR   = (22, 101, 52)   # #166534
GRAY_TEXT  = (55, 65, 81)    # #374151
GRAY_LIGHT = (243, 244, 246) # #F3F4F6
GRAY_BORDER= (209, 213, 219) # #D1D5DB
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)


class PanduanPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=20, top=20, right=20)

    # ------------------------------------------------------------------
    # Header / Footer
    # ------------------------------------------------------------------
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_fill_color(*BLUE_DARK)
        self.rect(0, 0, 210, 10, style="F")
        self.set_xy(0, 2)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*WHITE)
        self.cell(210, 5, "TKDN Finder - Panduan Instalasi & Penggunaan", align="C")
        self.set_text_color(*GRAY_TEXT)
        self.ln(12)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*GRAY_BORDER)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(1)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, f"Halaman {self.page_no()}", align="C")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def section_title(self, text: str, margin_top: float = 8) -> None:
        self.ln(margin_top)
        self.set_fill_color(*BLUE_DARK)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, f"  {text}", fill=True, ln=True)
        self.set_text_color(*GRAY_TEXT)
        self.ln(3)

    def subsection(self, text: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BLUE_MID)
        self.cell(0, 6, text, ln=True)
        self.set_text_color(*GRAY_TEXT)

    def body(self, text: str, indent: float = 0) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*GRAY_TEXT)
        x = self.get_x() + indent
        self.set_x(x)
        self.multi_cell(0, 5.5, text)
        self.set_x(20)

    def step_item(self, num: int | str, text: str) -> None:
        """Numbered step with circle badge."""
        y = self.get_y()
        # Circle badge
        self.set_fill_color(*BLUE_MID)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 9)
        self.set_xy(20, y)
        self.cell(7, 7, str(num), fill=True, align="C")
        # Text
        self.set_text_color(*GRAY_TEXT)
        self.set_font("Helvetica", "", 10)
        self.set_xy(30, y)
        self.multi_cell(0, 5.5, text)
        self.ln(1)
        self.set_x(20)

    def bullet(self, text: str, indent: float = 5) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*GRAY_TEXT)
        self.set_x(20 + indent)
        self.cell(5, 5.5, chr(149))  # bullet
        self.multi_cell(0, 5.5, text)
        self.set_x(20)

    def info_box(self, title: str, text: str, bg: tuple = BLUE_LIGHT,
                 border: tuple = BLUE_MID) -> None:
        self.ln(3)
        x, y = self.get_x(), self.get_y()
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        # Draw filled rect (approximate height)
        lines = len(text) // 80 + text.count("\n") + 1
        h = 7 + lines * 5.5
        self.rect(20, y, 170, h, style="DF")
        self.set_xy(24, y + 2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*border)
        self.cell(0, 5, title, ln=True)
        self.set_x(24)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GRAY_TEXT)
        self.multi_cell(162, 5, text)
        self.set_xy(20, y + h + 2)
        self.set_x(20)

    def key_value_row(self, label: str, value: str, last: bool = False) -> None:
        y = self.get_y()
        self.set_fill_color(*GRAY_LIGHT)
        self.set_draw_color(*GRAY_BORDER)
        self.set_xy(20, y)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*GRAY_TEXT)
        self.cell(55, 7, f"  {label}", border=1, fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(115, 7, f"  {value}", border=1)
        self.ln()


# ======================================================================
# COVER PAGE
# ======================================================================
def cover(pdf: PanduanPDF) -> None:
    pdf.add_page()

    # Top banner
    pdf.set_fill_color(*BLUE_DARK)
    pdf.rect(0, 0, 210, 80, style="F")

    # Logo area
    pdf.set_xy(0, 18)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*WHITE)
    pdf.cell(210, 12, "TKDN Finder", align="C", ln=True)

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(180, 210, 250)
    pdf.cell(210, 7, "Alat Pencarian Sertifikat TKDN - Kemenperin P3DN", align="C", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 230, 100)
    pdf.cell(210, 8, "Panduan Instalasi & Penggunaan", align="C", ln=True)

    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(210, 6, "Untuk Pengguna Non-IT", align="C", ln=True)

    # White card
    pdf.set_fill_color(*WHITE)
    pdf.set_draw_color(*GRAY_BORDER)
    pdf.rect(30, 90, 150, 95, style="DF")

    pdf.set_xy(30, 98)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*BLUE_DARK)
    pdf.cell(150, 7, "Daftar Isi", align="C", ln=True)

    toc = [
        ("1", "Persiapan & Instalasi", "3"),
        ("2", "Membuka Aplikasi", "4"),
        ("3", "Cara Pencarian", "5"),
        ("4", "Menggunakan Filter", "6"),
        ("5", "Membaca Hasil Pencarian", "7"),
        ("6", "Unduh Excel", "8"),
        ("7", "Update Tipe Produk", "8"),
        ("8", "Halaman Admin & Update Data", "9"),
        ("9", "Pertanyaan Umum (FAQ)", "10"),
    ]
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY_TEXT)
    for num, title, page in toc:
        pdf.set_x(40)
        pdf.cell(8, 6.5, num + ".")
        pdf.cell(116, 6.5, title)
        pdf.cell(10, 6.5, page, align="R", ln=True)

    # Footer info
    pdf.set_xy(0, 200)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(210, 6, "PT Pertamina Hulu Rokan  |  Pengadaan & Supply Chain", align="C", ln=True)
    pdf.cell(210, 6, "Dokumen ini dibuat otomatis. Data bersumber dari Kemenperin P3DN (publik).", align="C")


# ======================================================================
# PAGE: Instalasi
# ======================================================================
def page_instalasi(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("1. Persiapan & Instalasi", margin_top=0)

    pdf.body(
        "TKDN Finder adalah aplikasi web ringan yang berjalan di komputer Anda. "
        "Tidak memerlukan koneksi internet untuk pencarian (kecuali saat update data). "
        "Ikuti langkah berikut untuk menginstal pertama kali."
    )
    pdf.ln(4)

    pdf.subsection("Langkah Instalasi (Windows)")
    pdf.ln(2)

    pdf.step_item(1, "Unduh file instalasi (ZIP) dari tautan yang diberikan oleh tim IT.")
    pdf.step_item(2,
        "Klik kanan file ZIP yang sudah diunduh, lalu pilih \"Extract All...\" "
        "atau \"Ekstrak Semua...\". Pilih folder tujuan, misalnya C:\\TKDN-Finder."
    )
    pdf.step_item(3,
        "Buka folder hasil ekstrak. Anda akan melihat beberapa file di dalamnya, "
        "termasuk file run.bat."
    )
    pdf.step_item(4,
        "Klik dua kali (double-click) pada file run.bat untuk menjalankan aplikasi. "
        "Jika muncul peringatan Windows SmartScreen, klik \"More info\" lalu "
        "\"Run anyway\"."
    )
    pdf.step_item(5,
        "Sebuah jendela Command Prompt (layar hitam) akan terbuka dan tetap berjalan "
        "selama aplikasi aktif. Jangan ditutup."
    )
    pdf.step_item(6,
        "Browser akan terbuka secara otomatis. Jika tidak, buka browser secara manual "
        "dan ketik alamat: http://localhost:8000"
    )

    pdf.info_box(
        "Pertama Kali Dijalankan",
        "Saat pertama kali dijalankan, aplikasi akan otomatis mengunduh data TKDN "
        "dari situs Kemenperin P3DN. Proses ini membutuhkan koneksi internet dan "
        "memakan waktu sekitar 2-5 menit tergantung kecepatan koneksi.\n"
        "Jangan tutup aplikasi selama proses ini berlangsung. "
        "Progress dapat dipantau di halaman Admin.",
        bg=BLUE_LIGHT, border=BLUE_MID
    )

    pdf.ln(4)
    pdf.subsection("Kebutuhan Sistem")
    pdf.ln(2)
    pdf.key_value_row("Sistem Operasi", "Windows 10 / 11 (64-bit)")
    pdf.key_value_row("RAM", "Minimal 2 GB (disarankan 4 GB)")
    pdf.key_value_row("Penyimpanan", "Minimal 500 MB ruang kosong")
    pdf.key_value_row("Browser", "Google Chrome, Edge, atau Firefox (versi terbaru)")
    pdf.key_value_row("Internet", "Diperlukan hanya saat update data dari P3DN", last=True)

    pdf.ln(5)
    pdf.info_box(
        "Menutup Aplikasi",
        "Untuk menutup aplikasi, tutup jendela Command Prompt (layar hitam) "
        "atau tekan Ctrl+C di dalamnya. Browser dapat ditutup kapan saja "
        "tanpa memengaruhi data.",
        bg=YELLOW_BG, border=YELLOW_BR
    )


# ======================================================================
# PAGE: Membuka Aplikasi
# ======================================================================
def page_membuka(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("2. Membuka Aplikasi Setelah Instalasi", margin_top=0)

    pdf.body(
        "Setelah instalasi pertama selesai, Anda tidak perlu menginstal ulang. "
        "Cukup ikuti langkah berikut setiap kali ingin menggunakan TKDN Finder."
    )
    pdf.ln(4)

    pdf.step_item(1, "Buka folder TKDN Finder (misalnya C:\\TKDN-Finder).")
    pdf.step_item(2, "Klik dua kali file run.bat.")
    pdf.step_item(3, "Tunggu hingga muncul tulisan di layar hitam: \"Application startup complete\".")
    pdf.step_item(4, "Buka browser dan ketik: http://localhost:8000")
    pdf.step_item(5, "Halaman pencarian TKDN Finder akan muncul.")

    pdf.ln(4)
    pdf.info_box(
        "Informasi Terakhir Update Data",
        "Di bawah judul halaman pencarian, terdapat keterangan:\n"
        "\"Data P3DN terakhir diperbarui: DD Mon YYYY HH:MM WIB\"\n"
        "Ini menunjukkan kapan data terakhir diunduh dari Kemenperin P3DN. "
        "Pastikan tanggal ini tidak terlalu lama (lebih dari 1 bulan) agar data tetap akurat.",
        bg=BLUE_LIGHT, border=BLUE_MID
    )

    pdf.ln(5)
    pdf.subsection("Penjelasan Tampilan Utama")
    pdf.ln(2)

    items = [
        ("Kolom Pencarian", "Tempat mengetik kata kunci pencarian produk atau perusahaan."),
        ("TKDN Min (%)", "Filter nilai TKDN minimum. Isi dengan angka, misalnya 25 atau 40."),
        ("KBLI", "Filter berdasarkan kode klasifikasi industri (5 digit)."),
        ("Tahun", "Filter berdasarkan tahun penerbitan sertifikat."),
        ("Hanya berlaku", "Centang untuk menyembunyikan sertifikat yang sudah kadaluarsa."),
        ("Unduh Excel", "Tombol untuk mengunduh hasil pencarian dalam format Excel."),
        ("Update Tipe", "Tombol untuk mengisi data Tipe produk dari sumber kedua Kemenperin."),
    ]
    for label, desc in items:
        y = pdf.get_y()
        pdf.set_xy(20, y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*BLUE_MID)
        pdf.cell(45, 6, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.multi_cell(0, 6, desc)
        pdf.set_x(20)


# ======================================================================
# PAGE: Pencarian
# ======================================================================
def page_pencarian(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("3. Cara Pencarian", margin_top=0)

    pdf.body(
        "TKDN Finder mendukung pencarian cerdas dengan toleransi typo dan sinonim "
        "dua bahasa (Indonesia-Inggris). Anda tidak perlu mengetik kata yang sempurna."
    )
    pdf.ln(4)

    pdf.subsection("Contoh Pencarian")
    pdf.ln(2)

    examples = [
        ("pompa", "Menemukan: pompa, pump, centrifugal pump, pompa sentrifugal, dll."),
        ("pump", "Menemukan: pump, pompa, pompa industri, dll."),
        ("valve", "Menemukan: valve, katup, katup gate, gate valve, ball valve, dll."),
        ("katup", "Menemukan: katup, valve, ball valve, gate valve, dll."),
        ("kompresor", "Menemukan: kompresor, compressor, kompresor udara, dll."),
        ("pipa seamless", "Menemukan: pipa seamless, seamless pipe, pipa baja tanpa kampuh, dll."),
        ("PT Maju Jaya", "Mencari berdasarkan nama perusahaan."),
        ("28101", "Mencari berdasarkan kode KBLI."),
    ]
    for query, desc in examples:
        pdf.set_x(20)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*BLUE_DARK)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_fill_color(*GRAY_LIGHT)
        pdf.set_draw_color(*GRAY_BORDER)
        pdf.cell(45, 6, f'  "{query}"', border=1, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(0, 6, f"  {desc}", border=1, ln=True)

    pdf.ln(4)
    pdf.info_box(
        "Tips Pencarian",
        "- Ketik minimal 2-3 huruf; hasil muncul otomatis saat mengetik.\n"
        "- Tidak perlu huruf kapital - pencarian tidak peka huruf besar/kecil.\n"
        "- Jika hasil terlalu banyak, tambahkan filter TKDN Min atau centang "
        "\"Hanya berlaku\".\n"
        "- Untuk mencari produk tertentu, coba ketik nama produk + spesifikasi, "
        "misalnya: \"gate valve 6 inch\".",
        bg=GREEN_BG, border=GREEN_BR
    )

    pdf.ln(5)
    pdf.subsection("Mengurutkan Hasil")
    pdf.ln(2)
    pdf.body(
        "Klik pada header kolom tabel untuk mengurutkan hasil:"
    )
    pdf.ln(1)
    pdf.bullet("Klik \"Perusahaan\" untuk urut berdasarkan nama perusahaan (A-Z atau Z-A).")
    pdf.bullet("Klik \"Nilai TKDN\" untuk urut berdasarkan persentase TKDN (kecil ke besar atau sebaliknya).")
    pdf.bullet("Klik \"Masa Berlaku\" untuk urut berdasarkan tanggal kadaluarsa sertifikat.")
    pdf.ln(2)
    pdf.body("Klik kolom yang sama dua kali untuk membalik urutan.")


# ======================================================================
# PAGE: Filter
# ======================================================================
def page_filter(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("4. Menggunakan Filter", margin_top=0)

    pdf.body(
        "Filter membantu mempersempit hasil pencarian sesuai kebutuhan pengadaan. "
        "Semua filter dapat dikombinasikan."
    )
    pdf.ln(4)

    filters = [
        (
            "TKDN Min (%)",
            "Tampilkan hanya sertifikat dengan nilai TKDN lebih besar atau sama dengan "
            "angka yang diisi. Contoh: isi 25 untuk menyaring produk TKDN >= 25%.\n"
            "Untuk keperluan pengadaan KKKS, ambang batas umum adalah 25% atau 40% "
            "sesuai ketentuan PTK-007.",
        ),
        (
            "Hanya berlaku",
            "Centang kotak ini untuk menyembunyikan sertifikat yang sudah kadaluarsa "
            "atau hampir kadaluarsa. Sangat disarankan dicentang saat menyusun dokumen "
            "BAHP untuk memastikan hanya sertifikat aktif yang masuk.",
        ),
        (
            "KBLI",
            "Filter berdasarkan Klasifikasi Baku Lapangan Usaha Indonesia (5 digit). "
            "Pilih dari daftar yang tersedia. Gunakan filter ini jika Anda mengetahui "
            "kode KBLI produk yang dicari.",
        ),
        (
            "Tahun",
            "Filter berdasarkan tahun penerbitan sertifikat. Berguna untuk melihat "
            "sertifikat yang terbit pada tahun tertentu. Kosongkan untuk melihat "
            "semua tahun.",
        ),
    ]

    for title, desc in filters:
        pdf.subsection(title)
        pdf.body(desc)
        pdf.ln(3)

    pdf.info_box(
        "Rekomendasi untuk Penyusunan BAHP",
        "Untuk keperluan pra-kualifikasi dan BAHP:\n"
        "1. Aktifkan filter \"Hanya berlaku\" - pastikan sertifikat masih aktif.\n"
        "2. Set TKDN Min sesuai persyaratan spesifikasi teknis (biasanya 25% atau 40%).\n"
        "3. Unduh hasil sebagai Excel untuk dilampirkan pada dokumen BAHP.\n"
        "   File Excel mencantumkan tanggal ekspor dan tanggal update data P3DN "
        "sebagai bukti audit.",
        bg=BLUE_LIGHT, border=BLUE_MID
    )


# ======================================================================
# PAGE: Membaca Hasil
# ======================================================================
def page_hasil(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("5. Membaca Hasil Pencarian", margin_top=0)

    pdf.body(
        "Setiap baris hasil pencarian menampilkan informasi ringkas sertifikat TKDN. "
        "Klik baris untuk melihat detail lengkap."
    )
    pdf.ln(4)

    pdf.subsection("Kolom Tabel Hasil")
    pdf.ln(2)

    cols = [
        ("Perusahaan", "Nama produsen pemilik sertifikat TKDN."),
        ("Produk", "Nama produk yang bersertifikat."),
        ("Spesifikasi", "Spesifikasi teknis produk."),
        ("Merek/Tipe", "Merek dagang dan tipe/varian produk (jika tersedia)."),
        ("Nilai TKDN", "Persentase Tingkat Komponen Dalam Negeri (0-100%)."),
        ("Masa Berlaku", "Tanggal kadaluarsa sertifikat TKDN."),
        ("Status", "Status validitas sertifikat (lihat penjelasan di bawah)."),
    ]
    for col, desc in cols:
        y = pdf.get_y()
        pdf.set_xy(20, y)
        pdf.set_fill_color(*GRAY_LIGHT)
        pdf.set_draw_color(*GRAY_BORDER)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(38, 6.5, f"  {col}", border=1, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6.5, f"  {desc}", border=1, ln=True)

    pdf.ln(5)
    pdf.subsection("Status Sertifikat")
    pdf.ln(2)

    statuses = [
        (GREEN_BG, GREEN_BR, "Berlaku",
         "Sertifikat aktif. Masa berlaku lebih dari 60 hari ke depan."),
        (YELLOW_BG, YELLOW_BR, "Segera Berakhir",
         "Sertifikat masih aktif tetapi akan berakhir dalam 60 hari ke depan. "
         "Sebaiknya konfirmasi ke vendor apakah sertifikat akan diperpanjang."),
        ((254, 226, 226), (185, 28, 28), "Kadaluarsa",
         "Sertifikat sudah tidak berlaku. Tidak dapat digunakan untuk dokumen pengadaan resmi."),
        (GRAY_LIGHT, (107, 114, 128), "Tidak Diketahui",
         "Tanggal kadaluarsa tidak tersedia di sumber data P3DN."),
    ]
    for bg, br, label, desc in statuses:
        pdf.set_x(20)
        y = pdf.get_y()
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*br)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*br)
        pdf.cell(38, 7, f"  {label}", border=1, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(0, 7, f"  {desc}", border=1, ln=True)

    pdf.ln(5)
    pdf.subsection("Melihat Detail Sertifikat")
    pdf.body(
        "Klik pada salah satu baris hasil pencarian untuk membuka halaman detail "
        "yang menampilkan informasi lengkap, termasuk: Kode HS, KBLI, Kelompok Barang, "
        "Alamat perusahaan, Provinsi, Merek, dan Tipe produk."
    )


# ======================================================================
# PAGE: Excel & Tipe
# ======================================================================
def page_excel_tipe(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("6. Unduh Excel", margin_top=0)

    pdf.body(
        "Hasil pencarian dapat diunduh sebagai file Excel (.xlsx) untuk keperluan "
        "dokumentasi, lampiran BAHP, atau referensi pengadaan."
    )
    pdf.ln(4)

    pdf.step_item(1, "Lakukan pencarian dan atur filter sesuai kebutuhan.")
    pdf.step_item(2, "Klik tombol \"Unduh Excel\" di bagian atas hasil pencarian.")
    pdf.step_item(3,
        "File Excel akan diunduh secara otomatis dengan nama "
        "tkdn_export_YYYYMMDD_HHMMSS.xlsx (tanggal dan waktu ekspor)."
    )
    pdf.step_item(4,
        "Buka file Excel. Terdapat dua sheet:\n"
        "- Sheet \"Info\": berisi parameter pencarian, tanggal ekspor, dan tanggal "
        "terakhir update data P3DN (untuk keperluan audit).\n"
        "- Sheet \"Data TKDN\": berisi seluruh hasil pencarian (maks. 500 baris)."
    )

    pdf.info_box(
        "Catatan untuk Audit",
        "Sheet \"Info\" pada file Excel secara otomatis mencantumkan:\n"
        "- Tanggal dan waktu file diekspor (WIB)\n"
        "- Tanggal terakhir data P3DN diperbarui (WIB)\n"
        "- Parameter pencarian yang digunakan\n\n"
        "Informasi ini dapat digunakan sebagai bukti bahwa data diverifikasi "
        "dari sumber resmi Kemenperin pada tanggal tertentu.",
        bg=GREEN_BG, border=GREEN_BR
    )

    pdf.section_title("7. Update Tipe Produk")

    pdf.body(
        "Data ekspor bulk dari P3DN tidak menyertakan kolom Tipe produk (misalnya "
        "\"Tipe A\", \"Tipe C\", \"Cable Ladder SLHD\"). Fitur Update Tipe mengambil "
        "data ini dari portal tkdn.kemenperin.go.id."
    )
    pdf.ln(4)

    pdf.step_item(1, "Cari produk yang ingin diisi data Tipe-nya.")
    pdf.step_item(2,
        "Klik tombol \"Update Tipe\" di bagian atas hasil pencarian. "
        "Tombol ini akan memproses semua perusahaan yang muncul di hasil saat itu."
    )
    pdf.step_item(3,
        "Tunggu beberapa detik hingga muncul notifikasi berapa baris yang "
        "berhasil diperbarui."
    )
    pdf.step_item(4,
        "Refresh hasil pencarian untuk melihat data Tipe yang baru diisi. "
        "Tekan tombol Cari atau ubah filter untuk me-refresh."
    )

    pdf.info_box(
        "Perlu Koneksi Internet",
        "Fitur Update Tipe memerlukan koneksi internet karena mengambil data "
        "secara langsung dari tkdn.kemenperin.go.id. "
        "Pastikan komputer terhubung ke internet sebelum menggunakan fitur ini.",
        bg=YELLOW_BG, border=YELLOW_BR
    )


# ======================================================================
# PAGE: Admin
# ======================================================================
def page_admin(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("8. Halaman Admin & Update Data", margin_top=0)

    pdf.body(
        "Halaman Admin dapat diakses melalui menu di pojok kanan atas, "
        "atau langsung ke alamat: http://localhost:8000/admin"
    )
    pdf.ln(4)

    pdf.subsection("Refresh / Download Data")
    pdf.body(
        "Klik tombol \"Refresh / Download Data\" untuk mengunduh ulang seluruh data "
        "TKDN dari situs P3DN Kemenperin. Lakukan ini secara berkala (misalnya setiap "
        "bulan) agar data selalu terkini."
    )
    pdf.ln(2)

    pdf.info_box(
        "Kapan Perlu Update Data?",
        "- Data P3DN biasanya diperbarui Kemenperin setiap bulan.\n"
        "- Cek tanggal \"Data P3DN terakhir diperbarui\" di halaman pencarian.\n"
        "- Jika sudah lebih dari 30 hari, sebaiknya lakukan Refresh Data.\n"
        "- Proses download membutuhkan waktu 2-5 menit dan koneksi internet.",
        bg=BLUE_LIGHT, border=BLUE_MID
    )

    pdf.ln(4)
    pdf.subsection("Riwayat Download")
    pdf.body(
        "Tabel riwayat download menampilkan history setiap kali data diunduh, termasuk:"
    )
    pdf.ln(1)
    pdf.bullet("Tahun data yang diunduh.")
    pdf.bullet("Status (Berhasil / Gagal).")
    pdf.bullet("Waktu mulai dan selesai.")
    pdf.bullet("Jumlah baris total, berapa yang baru (+), diperbarui (~), atau dilewati.")
    pdf.ln(2)

    pdf.subsection("Manajemen Sinonim")
    pdf.body(
        "Sinonim memungkinkan pencarian menemukan produk dengan kata yang berbeda. "
        "Misalnya, mencari \"pompa\" akan menemukan \"pump\", dan sebaliknya."
    )
    pdf.ln(2)
    pdf.body("Untuk menambah sinonim baru:")
    pdf.ln(1)
    pdf.step_item(1, "Isi kolom \"Kata Kanonik\" dengan kata utama (misalnya: valve).")
    pdf.step_item(2,
        "Isi kolom \"Varian\" dengan kata-kata lain yang setara, "
        "dipisahkan dengan koma (misalnya: katup, klep, valve industri)."
    )
    pdf.step_item(3, "Klik \"Tambah / Perbarui\". Sinonim langsung aktif tanpa restart.")

    pdf.info_box(
        "Catatan",
        "Sinonim yang sudah ada secara default mencakup ratusan kata teknis "
        "bidang minyak & gas (pompa, katup, pipa, kompresor, dll.). "
        "Hubungi tim IT jika diperlukan penambahan sinonim secara massal.",
        bg=GRAY_LIGHT, border=(107, 114, 128)
    )


# ======================================================================
# PAGE: FAQ
# ======================================================================
def page_faq(pdf: PanduanPDF) -> None:
    pdf.add_page()
    pdf.section_title("9. Pertanyaan Umum (FAQ)", margin_top=0)

    faqs = [
        (
            "Aplikasi tidak bisa dibuka / browser tidak muncul.",
            "Pastikan file run.bat sudah diklik dan jendela Command Prompt (layar hitam) "
            "masih terbuka. Coba buka browser secara manual dan ketik http://localhost:8000. "
            "Jika tetap tidak bisa, coba restart komputer dan jalankan run.bat lagi."
        ),
        (
            "Muncul pesan \"localhost refused to connect\".",
            "Artinya aplikasi belum berjalan. Jalankan run.bat terlebih dahulu, "
            "tunggu hingga muncul tulisan \"Application startup complete\" di layar hitam, "
            "baru buka browser."
        ),
        (
            "Hasil pencarian kosong padahal produk ada.",
            "Coba hapus atau longgarkan filter (misalnya kurangi TKDN Min, hapus centang "
            "\"Hanya berlaku\"). Coba juga variasi kata kunci - misalnya jika \"pompa\" "
            "tidak ditemukan, coba \"pump\" atau sebaliknya."
        ),
        (
            "Data terlihat lama / tidak update.",
            "Buka halaman Admin (http://localhost:8000/admin) dan klik \"Refresh / "
            "Download Data\". Pastikan komputer terhubung ke internet. "
            "Proses membutuhkan 2-5 menit."
        ),
        (
            "Kolom Tipe kosong di semua hasil.",
            "Data Tipe tidak tersedia di ekspor bulk P3DN. Gunakan fitur \"Update Tipe\" "
            "di hasil pencarian untuk mengambil data Tipe dari portal tkdn.kemenperin.go.id."
        ),
        (
            "File Excel tidak bisa dibuka.",
            "Pastikan Microsoft Excel atau aplikasi kompatibel (LibreOffice Calc) "
            "sudah terinstal. File berformat .xlsx standar."
        ),
        (
            "Apakah data saya aman? Apakah ada yang dikirim ke internet?",
            "TKDN Finder hanya terhubung ke internet untuk mengunduh data dari "
            "Kemenperin P3DN (situs resmi pemerintah). Tidak ada data pencarian Anda "
            "yang dikirim ke pihak luar. Semua data tersimpan di komputer lokal."
        ),
        (
            "Bagaimana cara menutup aplikasi dengan benar?",
            "Tutup jendela Command Prompt (layar hitam) atau klik di dalam jendela "
            "tersebut lalu tekan Ctrl+C. Browser dapat ditutup kapan saja tanpa "
            "memengaruhi data."
        ),
        (
            "Apakah bisa digunakan di beberapa komputer sekaligus?",
            "Instalasi standar hanya untuk satu komputer. Untuk penggunaan bersama "
            "(server), hubungi tim IT untuk konfigurasi jaringan."
        ),
    ]

    for i, (q, a) in enumerate(faqs):
        pdf.ln(2)
        y = pdf.get_y()
        # Question
        pdf.set_x(20)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*BLUE_DARK)
        pdf.multi_cell(0, 5.5, f"T: {q}")
        # Answer
        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.multi_cell(0, 5.5, f"J: {a}")
        if i < len(faqs) - 1:
            pdf.set_draw_color(*GRAY_BORDER)
            pdf.line(20, pdf.get_y() + 1, 190, pdf.get_y() + 1)

    pdf.ln(8)
    pdf.set_fill_color(*BLUE_DARK)
    pdf.rect(20, pdf.get_y(), 170, 18, style="F")
    pdf.set_xy(20, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(170, 5, "Butuh bantuan lebih lanjut?", align="C", ln=True)
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(170, 5, "Hubungi tim IT atau kirim email ke: irsan.hf@gmail.com", align="C")


# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    import os

    pdf = PanduanPDF()
    pdf.set_title("TKDN Finder - Panduan Instalasi & Penggunaan")
    pdf.set_author("PT Pertamina Hulu Rokan")
    pdf.set_subject("Panduan non-IT untuk instalasi dan penggunaan TKDN Finder")

    cover(pdf)
    page_instalasi(pdf)
    page_membuka(pdf)
    page_pencarian(pdf)
    page_filter(pdf)
    page_hasil(pdf)
    page_excel_tipe(pdf)
    page_admin(pdf)
    page_faq(pdf)

    out = "TKDN_Finder_Panduan.pdf"
    pdf.output(out)
    print(f"PDF saved: {os.path.abspath(out)}")
