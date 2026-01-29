# ITMS Pro (Sistem Manajemen Aset IT)

**ITMS Pro** adalah solusi Manajemen Aset IT tingkat enterprise yang komprehensif, dirancang untuk merampingkan operasional IT, mulai dari melacak perangkat keras dan lisensi hingga mengelola pemeliharaan dan insiden. Dibangun menggunakan **Django 6** dan **PostgreSQL**, sistem ini menawarkan keamanan, skalabilitas, dan kemudahan penggunaan.

<img width="600" height="900" alt="image" src="https://github.com/user-attachments/assets/96d93b5a-ea4e-4f6b-b650-071bd8baa186" />



## 🚀 Fitur Utama

### 📦 Siklus Hidup Aset Lengkap
*   **Pelacakan Hardware**: Inventaris detail untuk Laptop, Server, dan Printer dengan dukungan barcode/QR.
*   **Software & Lisensi**: Melacak masa berlaku lisensi dan jumlah pengguna (seats).
*   **Cetak Label**: Cetak label QR Code secara massal untuk penandaan fisik.

### 📡 Visualisasi Infrastruktur
*   **Tata Letak Fisik**: Visualisasi Rak Server dan tata letak Data Center.
*   **Pemantauan Jaringan (NMS)**: Pelacakan status *real-time* (Up/Down) node kritis via ICMP/SNMP.
*   **Peringatan Downtime**: Notifikasi instan via **Telegram/WhatsApp** ketika beberapa node gagal.
*   **Manajemen IP Address (IPAM)**: Mengatur Subnet dan penggunaan IP.

### 🛠 Operasional & Helpdesk
*   **Sistem Tiket**: Helpdesk internal untuk pelaporan masalah.
*   **Pemeliharaan Preventif**: Menjadwalkan tugas pemeliharaan berulang untuk memperpanjang umur aset.
*   **Knowledge Base**: Artikel mandiri untuk solusi masalah umum.

### 🛡 Tata Kelola & Keamanan
*   **Role-Based Access Control (RBAC)**: Akses aman untuk Admin, Manajer, IT Support, dan Pengguna Akhir.
*   **Activity Logs**: Jejak audit (*Audit Trail*) anti-manipulasi untuk setiap perubahan sistem.
*   **Manajemen Proyek**: Melacak inisiatif IT, anggaran, dan lini masa (Kanban/Gantt).

---

## 💻 Teknologi (Tech Stack)

*   **Backend**: Python 3.10+, Django 6.0
*   **Database**: PostgreSQL 14+
*   **Frontend**: Bootstrap 5, HTMX (untuk interaksi dinamis)
*   **Charts**: Chart.js / ApexCharts
*   **Notifikasi**: Telegram Bot API, Integrasi WhatsApp Gateway
*   **Utilitas**: `weasyprint` (PDF), `django-import-export` (Excel), `django-simple-history` (Audit)

---

## 📸 Tangkapan Layar

| Dashboard | Detail Aset |
|-----------|--------------|
| ![Dashboard](https://via.placeholder.com/600x400?text=IT+Dashboard) | ![Asset](https://via.placeholder.com/600x400?text=Asset+Lifecycle) |

| Peta Jaringan | Kanban Proyek |
|-------------|----------------|
| ![Network](https://via.placeholder.com/600x400?text=Network+Map) | ![Kanban](https://via.placeholder.com/600x400?text=Kanban+Board) |

---

## 🔧 Instalasi

1.  **Clone repositori**
    ```bash
    git clone https://github.com/usernameanda/itms-pro.git
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

## 🤝 Kontribusi
Kontribusi, masalah (issues), dan permintaan fitur sangat diterima!

## 📄 Lisensi
(LICENSE) © 2026 Hendra Juniansyah.
