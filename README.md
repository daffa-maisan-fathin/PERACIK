# ☕ AI Barista Anak Kos

Asisten peracik minuman berbasis AI (Google Gemini) yang mengubah bahan-bahan
minimarket/warung jadi resep kreatif ala kafe, lengkap dengan riwayat eksperimen
yang tersimpan di database.

---

## Langkah 1 — Skema Database

Menggunakan **SQLite** (file `barista.db`, dibuat otomatis oleh `database.py`).
Kenapa SQLite untuk proyek ini: tanpa instalasi server terpisah, cukup satu file,
gampang di-*upgrade* ke MySQL/PostgreSQL nanti karena SQL-nya standar.

### Tabel `resep`

| Kolom          | Tipe Data      | Keterangan                                             |
|----------------|----------------|---------------------------------------------------------|
| `id`           | INTEGER (PK)   | Auto increment                                          |
| `bahan_input`  | TEXT           | Input mentah dari user, misal "Nescafe + Milku cokelat" |
| `nama_menu`    | TEXT           | Nama kreatif hasil AI, misal "Kos Mocha Roast"          |
| `deskripsi`    | TEXT           | Deskripsi rasa/vibe singkat                             |
| `bahan_json`   | TEXT (JSON)    | Array bahan + takaran, contoh di bawah                  |
| `langkah_json` | TEXT (JSON)    | Array langkah pembuatan, urut                           |
| `tips`         | TEXT           | Tips tambahan dari "barista"                            |
| `created_at`   | TIMESTAMP      | Default `CURRENT_TIMESTAMP`                             |

Contoh isi `bahan_json`:
```json
[
  {"item": "Nescafe Ice Roast sachet", "takaran": "1 sachet"},
  {"item": "Milku cokelat", "takaran": "180 ml"},
  {"item": "Es batu", "takaran": "secukupnya"}
]
```

> Kolom bahan & langkah disimpan sebagai JSON string di satu kolom TEXT supaya
> skema tetap 1 tabel sederhana tapi tetap fleksibel menampung jumlah item yang
> berbeda-beda tiap resep (tidak semua resep punya jumlah bahan yang sama).

### Query SQL yang dipakai

**Membuat tabel:**
```sql
CREATE TABLE IF NOT EXISTS resep (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bahan_input   TEXT NOT NULL,
    nama_menu     TEXT NOT NULL,
    deskripsi     TEXT,
    bahan_json    TEXT NOT NULL,
    langkah_json  TEXT NOT NULL,
    tips          TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Menyimpan resep baru:**
```sql
INSERT INTO resep (bahan_input, nama_menu, deskripsi, bahan_json, langkah_json, tips)
VALUES (?, ?, ?, ?, ?, ?);
```

**Mengambil riwayat (terbaru dulu):**
```sql
SELECT id, bahan_input, nama_menu, deskripsi, bahan_json, langkah_json, tips, created_at
FROM resep
ORDER BY created_at DESC
LIMIT 50;
```

**Mengambil satu resep spesifik:**
```sql
SELECT * FROM resep WHERE id = ?;
```

Semua query di atas sudah dibungkus rapi di `database.py` lewat fungsi
`init_db()`, `simpan_resep()`, `ambil_riwayat()`, dan `ambil_resep_by_id()` —
jadi `app.py` tidak menulis SQL mentah langsung.

> **Kalau nanti mau pindah ke MySQL:** ganti `sqlite3.connect(...)` di
> `database.py` dengan `mysql.connector.connect(...)` (atau pakai SQLAlchemy),
> lalu ganti placeholder `?` menjadi `%s`. Struktur tabel & query di atas
> hampir tidak berubah.

---

## Langkah 2 — Backend Flask & Gemini API

File utama: **`app.py`** dan **`database.py`**.

Alur singkat:
1. Frontend `POST /api/racik` dengan body `{ "bahan": "..." }`.
2. `buat_prompt()` menyusun prompt dengan persona "barista kreatif anak kos"
   (lihat isi lengkapnya di `app.py`) dan mewajibkan Gemini membalas **JSON murni**.
3. `ekstrak_json()` membersihkan kemungkinan bungkus ```` ```json ```` dan mem-parse
   ke dict Python.
4. `database.simpan_resep()` menyimpan hasil ke SQLite.
5. Response JSON dikirim balik ke frontend.

Endpoint yang tersedia:

| Method | Endpoint              | Fungsi                                  |
|--------|-----------------------|------------------------------------------|
| GET    | `/`                    | Menampilkan halaman utama (`index.html`) |
| POST   | `/api/racik`           | Racik resep baru dari bahan input        |
| GET    | `/api/riwayat`         | Ambil daftar riwayat resep                |
| GET    | `/api/riwayat/<id>`    | Ambil detail satu resep                  |

---

## Langkah 3 — Frontend

File: `templates/index.html`, `static/style.css`, `static/script.js`
(HTML/CSS/JS standar sesuai request — simpel, tanpa build step Next.js,
supaya langsung bisa jalan dari Flask).

Bagian yang tersedia sesuai spesifikasi:
1. **Kolom input bebas** — `<textarea id="bahan-input">`.
2. **Tombol "Racik Menu!"** — `#btn-racik`, memanggil `racikMenu()` di `script.js`.
3. **Area hasil resep** — nama menu, deskripsi, daftar bahan, dan langkah,
   di-render oleh `renderResep()`.
4. **Riwayat Eksperimen** — daftar resep dari `/api/riwayat`, tiap item bisa
   diklik untuk menampilkan ulang detailnya (`renderRiwayat()`).

---

## Langkah 4 — Integrasi & Menjalankan Secara Lokal

Karena frontend di-*serve* langsung oleh Flask (`render_template` + folder
`static/`), **tidak perlu server frontend terpisah** — cukup satu server Flask.

### 1. Siapkan environment

```bash
cd ai-barista-anak-kos
python -m venv venv

# Aktifkan virtual environment
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Isi API key Gemini

```bash
cp .env.example .env
```

Buka file `.env`, isi dengan API key dari
[Google AI Studio](https://aistudio.google.com/app/apikey):

```
GEMINI_API_KEY=AIzaSy...api_key_asli_kamu
```

### 3. Jalankan server

```bash
python app.py
```

Server akan jalan di `http://127.0.0.1:5000`. Buka URL tersebut di browser —
frontend, backend, dan database sudah otomatis terhubung karena semuanya
disajikan oleh proses Flask yang sama (`database.init_db()` dipanggil otomatis
saat `app.py` dijalankan, jadi `barista.db` akan langsung dibuat).

### 4. Cara pakai

1. Ketik bahan yang kamu punya, contoh: `Nescafe Ice Roast sachet + Milku cokelat`.
2. Klik **"Racik Menu!"**.
3. Tunggu beberapa detik — hasil resep (nama, bahan+takaran, langkah, tips)
   akan muncul dan otomatis tersimpan.
4. Scroll ke bawah untuk melihat **Riwayat Eksperimen**; klik salah satu untuk
   membuka lagi detailnya tanpa perlu request ulang ke AI.

### Troubleshooting singkat

| Gejala                                             | Penyebab umum                                       |
|-----------------------------------------------------|------------------------------------------------------|
| `GEMINI_API_KEY belum di-set`                       | File `.env` belum dibuat/diisi, atau salah nama var  |
| Error 502 "AI membalas format yang tidak terbaca"    | Model kadang menambah teks di luar JSON — coba lagi  |
| Riwayat tidak muncul                                 | Cek `barista.db` sudah terbuat di folder proyek      |
| `ModuleNotFoundError`                                | Virtual environment belum diaktifkan / lupa `pip install` |

---

## Struktur folder

```
ai-barista-anak-kos/
├── app.py                 # Flask app + integrasi Gemini + routes
├── database.py            # Skema & helper SQLite
├── requirements.txt
├── .env.example
├── barista.db              # dibuat otomatis saat pertama run
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```
