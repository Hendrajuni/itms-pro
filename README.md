# ITMS Pro (Sistem Manajemen Aset IT)

**ITMS Pro** adalah solusi Manajemen Aset IT tingkat enterprise yang komprehensif, dirancang untuk merampingkan operasional IT, mulai dari melacak perangkat keras dan lisensi hingga mengelola pemeliharaan dan insiden. Dibangun menggunakan **Django 6** dan **PostgreSQL**, sistem ini menawarkan keamanan, skalabilitas, dan kemudahan penggunaan.

<img width="600" height="900" alt="image" src="https://github.com/user-attachments/assets/96d93b5a-ea4e-4f6b-b650-071bd8baa186" />


## 🚀 Fitur Utama (Real Capabilities)

### 📦 Manajemen Aset Terintegrasi
*   **Aset Fisik & Hardware**: Pencatatan lengkap mulai dari Laptop, Server, hingga furnitur dengan status (Digunakan, Rusak, Disposal).
*   **Lisensi Software**: Monitoring masa berlaku lisensi agar tidak ada yang *expired* tanpa ketahuan.
*   **Riwayat Komponen**: Melacak upgrade RAM/SSD pada setiap aset, sehingga history perubahan spesifikasi terlihat jelas.
*   **Cetak Label QR**: Generator QR Code bawaan untuk label aset fisik.

### 🛠 Operasional & Pemeliharaan (Maintenance)
*   **Jadwal Rutin (Preventive)**: Fitur "Next 7 Days Maintenance" yang memberi tahu teknisi apa yang harus dikerjakan minggu ini.
*   **Checklist Maintenance**: Teknisi tidak hanya "klik selesai", tapi harus mencentang checklist (misal: "Cek Suhu", "Bersihkan Debu") sebelum menutup tugas.
*   **Manajemen Perbaikan (Breakdown)**: Pencatatan perbaikan aset rusak (Service Luar/Dalam) beserta biayanya.

### 📊 Produktivitas & Pelaporan
*   **Sistem Tiket Helpdesk**: User melapor masalah, teknisi mengambil tiket, dan waktu penyelesaian ("SLA") tercatat.
*   **Daily Activity Log**: *Fitur Unggulan*. Laporan harian teknisi yang otomatis menarik data dari Tiket dan Maintenance yang dikerjakan hari itu. Tidak perlu input ganda.
*   **Workload Analysis**: Manajer bisa melihat beban kerja tim (siapa yang *overload*, siapa yang *idle*) secara *real-time*.

### 🛡 Keamanan & Tata Kelola
*   **Backup Database Manual**: Fitur satu klik untuk download backup seluruh data sistem (JSON) demi keamanan data.
*   **Audit Trail Lengkap**: Mencatat "Siapa mengubah apa". Jika spek laptop berubah, sistem mencatat usernya dan waktu perubahannya.
*   **Role-Based Access**: Dasbor terpisah antara Administrator, Manajer, Teknisi, dan User Biasa.
*   **Manajemen Proyek**: Board Kanban sederhana untuk memantau proyek IT jangka panjang.
*   **Pemantauan Jaringan (Simple NMS)**: Pengecekan status *Ping/ICMP* ke server/router vital dengan notifikasi status.

---

## 💎 Versi Free vs Pro

ITMS tersedia dalam dua edisi untuk memenuhi kebutuhan skala bisnis yang berbeda.

| Fitur | Free | Pro) |
| :--- | :---: | :---: |
| **Lokasi / Cabang** | Max **1** (Single Site) | **Unlimited** |
| **Admin User** | Max **1** (Single Admin) | **Unlimited** |
| **Limit Aset** | **Unlimited** | **Unlimited** |
| **Software & Contracts** | ✅ | ✅ |
| **Knowledge Base** | ❌ (Dikunci) | ✅ |
| **Dashboard Intelligence** | ❌ (Terbatas) | ✅ (Full - Expiry Alerts, Health Overview) |
| **Manajemen User** | ✅ (Basic) | ✅ (Full + Activity Logs) |
| **Cetak Laporan & QR** | ❌ | ✅ |
| **Integrasi Pihak Ketiga** | ❌ | ✅ |
| **Akses Django Admin** | ❌ (Hidden) | ✅ (Full Access) |

*Untuk detail teknis perbandingan, lihat file [EDITION_COMPARISON.md](EDITION_COMPARISON.md).*

## ✨ Pembaruan Terkini (v2.1)

*   **Sistem Lisensi CLI**: Aktivasi lisensi Enterprise yang aman melalui command line (`python manage.py activate_license`).
*   **User Management Baru**: Antarmuka manajemen pengguna yang sepenuhnya kustom (Add/Edit/Delete) tanpa bergantung pada Django Admin.
*   **Limitasi Cerdas**: Penegakan batasan kuota (Lokasi/Aset) secara otomatis pada level backend dan UI.
*   **Perbaikan UI/UX**: Tampilan Sidebar dan Tree View lokasi yang lebih responsif dan bersih.

---

## 💻 Teknologi (Tech Stack)

*   **Backend**: Python 3.10+, Django 6.0
*   **Database**: PostgreSQL 14+
*   **Frontend**: Bootstrap 5, HTMX (untuk interaksi dinamis)
*   **Charts**: Chart.js / ApexCharts
*   **Notifikasi**: Telegram Bot API, Integrasi WhatsApp Gateway
*   **Utilitas**: `weasyprint` (PDF), `django-import-export` (Excel), `django-simple-history` (Audit)

---

## 🔧 Instalasi

1.  **Clone repositori**
    ```bash
    git clone https://github.com/hendrajuni/itms-pro.git
    cd itms-pro
    ```

2.  **Buat Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Di Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment**
    Salin `.env.example` menjadi `.env` dan perbarui kredensial database Anda.

5.  **Jalankan Migrasi & Server**
    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
    ```

## 📄 Lisensi
(LICENSE) © 2026 Hendra Juniansyah.
