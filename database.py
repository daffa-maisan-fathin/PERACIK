"""
database.py
-----------
Modul untuk mengatur skema & koneksi database SQLite
untuk aplikasi "AI Barista Anak Kos".

Kenapa SQLite?
- Tidak butuh server database terpisah (cocok untuk proyek kecil/skripsi/portofolio).
- File database cukup satu file (barista.db) yang bisa langsung di-commit/di-backup.
- Mudah "naik kelas" ke MySQL/PostgreSQL nanti karena struktur SQL-nya mirip.

Struktur tabel `resep`:
------------------------------------------------------------------
| Kolom          | Tipe Data     | Keterangan                     |
------------------------------------------------------------------
| id             | INTEGER PK    | Auto increment                 |
| bahan_input    | TEXT          | Input mentah dari user          |
| nama_menu      | TEXT          | Nama kreatif hasil racikan AI    |
| deskripsi      | TEXT          | Deskripsi singkat rasa/vibe      |
| bahan_json     | TEXT (JSON)   | List bahan + takaran (array)     |
| langkah_json   | TEXT (JSON)   | List langkah pembuatan (array)   |
| tips           | TEXT          | Tips tambahan dari "barista"     |
| created_at     | TIMESTAMP     | Waktu resep dibuat               |
------------------------------------------------------------------

Kita menyimpan bahan & langkah sebagai JSON string di kolom TEXT
supaya skema tetap simpel (1 tabel) tapi tetap fleksibel menampung
list dengan jumlah item yang berbeda-beda tiap resep.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "barista.db")


def get_connection():
    """Buka koneksi baru ke database SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # supaya hasil query bisa diakses seperti dict
    return conn


def init_db():
    """Inisialisasi tabel jika belum ada. Dipanggil sekali saat app start."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS resep (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            bahan_input       TEXT NOT NULL,
            nama_menu         TEXT NOT NULL,
            deskripsi         TEXT,
            bahan_json        TEXT NOT NULL,
            langkah_json      TEXT NOT NULL,
            tips              TEXT,
            referensi_dataset TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()

    # Migrasi ringan: kalau tabel dibuat sebelum kolom ini ada, tambahkan.
    try:
        cur.execute("ALTER TABLE resep ADD COLUMN referensi_dataset TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah ada, aman diabaikan
    conn.close()


def simpan_resep(bahan_input: str, resep: dict, referensi_dataset: str = "") -> int:
    """
    Simpan satu hasil racikan AI ke database.
    `resep` adalah dict hasil parsing JSON dari Gemini, contoh:
    {
        "nama_menu": "Kos Mocha Roast",
        "deskripsi": "...",
        "bahan": [{"item": "Nescafe Ice Roast sachet", "takaran": "1 sachet"}, ...],
        "langkah": ["...", "..."],
        "tips": "..."
    }
    `referensi_dataset` adalah nama-nama resep dari dataset Kaggle yang
    dipakai sebagai referensi (RAG) saat prompt disusun, dipisah koma.
    Mengembalikan id baris yang baru disimpan.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO resep (bahan_input, nama_menu, deskripsi, bahan_json, langkah_json, tips, referensi_dataset)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bahan_input,
            resep.get("nama_menu", "Menu Tanpa Nama"),
            resep.get("deskripsi", ""),
            json.dumps(resep.get("bahan", []), ensure_ascii=False),
            json.dumps(resep.get("langkah", []), ensure_ascii=False),
            resep.get("tips", ""),
            referensi_dataset,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def ambil_riwayat(limit: int = 50):
    """
    Ambil daftar riwayat resep, terbaru duluan.
    Kolom JSON otomatis di-decode balik jadi list Python
    supaya gampang dipakai backend/frontend.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, bahan_input, nama_menu, deskripsi, bahan_json, langkah_json, tips, referensi_dataset, created_at
        FROM resep
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    hasil = []
    for row in rows:
        hasil.append(
            {
                "id": row["id"],
                "bahan_input": row["bahan_input"],
                "nama_menu": row["nama_menu"],
                "deskripsi": row["deskripsi"],
                "bahan": json.loads(row["bahan_json"]),
                "langkah": json.loads(row["langkah_json"]),
                "tips": row["tips"],
                "referensi_dataset": row["referensi_dataset"],
                "created_at": row["created_at"],
            }
        )
    return hasil


def ambil_resep_by_id(resep_id: int):
    """Ambil satu resep spesifik berdasarkan id (opsional, untuk halaman detail)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resep WHERE id = ?", (resep_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "bahan_input": row["bahan_input"],
        "nama_menu": row["nama_menu"],
        "deskripsi": row["deskripsi"],
        "bahan": json.loads(row["bahan_json"]),
        "langkah": json.loads(row["langkah_json"]),
        "tips": row["tips"],
        "created_at": row["created_at"],
    }
