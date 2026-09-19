"""
dataset.py
----------
Memuat dataset resep minuman profesional (sumber: Kaggle -
"Coffee Shop Chain Recipes and Prices" oleh deryae0) dan memanfaatkannya
sebagai REFERENSI (grounding) bagi AI saat meracik resep baru.

Pendekatan ini adalah bentuk sederhana dari Retrieval-Augmented Generation
(RAG): sebelum meminta Gemini membuat resep, sistem terlebih dahulu MENCARI
1-2 resep paling relevan dari dataset asli berdasarkan kemiripan kategori
bahan, lalu menyisipkan contoh nyata itu ke dalam prompt. Dengan begitu,
proporsi/takaran yang disarankan AI tidak murni karangan, tetapi terinspirasi
dari pola resep coffee shop sungguhan.

Struktur dataset asli:
- recipes.csv : drink_type, size, dan puluhan kolom takaran bahan
                (mis. "milk (in cl)", "coffee dose (in number of espressos)")
- prices.csv  : drink_type beserta harga per ukuran
"""

import csv
import os

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
RECIPES_PATH = os.path.join(DATASET_DIR, "recipes.csv")
PRICES_PATH = os.path.join(DATASET_DIR, "prices.csv")

# Kolom bahan di dataset -> kategori bahan (dipakai untuk pencocokan sederhana)
KATEGORI_KOLOM = {
    "milk (in cl)": "susu",
    "coco milk (in cl)": "susu",
    "coffee dose (in number of ristrettos)": "kopi",
    "coffee dose (in number of espressos)": "kopi",
    "cold brew (in cl)": "kopi",
    "filter coffee (in cl)": "kopi",
    "coffee (in grams)": "kopi",
    "chocolate pumps (=30 ml)": "coklat",
    "aroma pumps (=10 ml)": "sirup",
    "natural fruit extract pumps (=10ml)": "buah",
    "apple juice": "buah",
    "freshly pressed orange juice": "buah",
    "fruit packets": "buah",
    "infused black tea (in cl)": "teh",
    "tea bags": "teh",
    "teaspoon powder (= 5ml)": "bubuk",
    "tablespoon powder (= 15ml)": "bubuk",
    "honey (in grams)": "madu",
    "whipped cream": "krim",
    "speculoos (in ml)": "topping",
}

# Kata kunci bahasa sehari-hari (Indonesia/produk minimarket) -> kategori.
# Dipakai untuk mendeteksi kategori dari input bebas pengguna.
KATA_KUNCI_KATEGORI = {
    "susu": ["susu", "milk", "milku", "ultra milk", "frisian", "indomilk", "creamer"],
    "kopi": ["kopi", "coffee", "nescafe", "kapal api", "abc", "espresso", "americano", "good day", "torabika"],
    "coklat": ["coklat", "cokelat", "chocolate", "milo", "vanhoutten", "ovaltine"],
    "sirup": ["sirup", "syrup", "marjan"],
    "buah": ["jus", "juice", "jeruk", "apel", "mangga", "buah"],
    "teh": ["teh", "tea", "sosro", "sariwangi", "tong tji"],
    "bubuk": ["bubuk", "powder", "matcha", "taro"],
    "madu": ["madu", "honey"],
    "krim": ["krim", "cream", "whip"],
}


def _kategori_bahan_user(bahan_input: str) -> set:
    """Deteksi kategori (susu/kopi/coklat/dst) dari teks bebas yang diketik user."""
    teks = bahan_input.lower()
    kategori = set()
    for kat, kata_kunci in KATA_KUNCI_KATEGORI.items():
        if any(k in teks for k in kata_kunci):
            kategori.add(kat)
    return kategori


def _load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _muat_dataset():
    """Gabungkan recipes.csv + prices.csv jadi satu list resep per (nama, ukuran)."""
    resep_rows = _load_csv(RECIPES_PATH)
    price_rows = {r["drink_type"]: r for r in _load_csv(PRICES_PATH)}

    hasil = []
    for row in resep_rows:
        nama = row["drink_type"]
        size = row.get("size (mixed drinks)") or row.get("size (coffee)") or "-"

        bahan = []
        kategori = set()
        for kolom, nilai in row.items():
            if kolom in ("drink_type", "size (mixed drinks)", "size (coffee)"):
                continue
            if nilai and nilai.strip():
                bahan.append(f"{kolom}: {nilai}")
                if kolom in KATEGORI_KOLOM:
                    kategori.add(KATEGORI_KOLOM[kolom])

        harga_row = price_rows.get(nama, {})
        harga = (
            harga_row.get("price_medium")
            or harga_row.get("price_small")
            or harga_row.get("simple")
            or "-"
        )

        hasil.append(
            {
                "nama": nama,
                "size": size,
                "bahan": bahan,
                "kategori": kategori,
                "harga_referensi": harga,
            }
        )
    return hasil


# Cache di memori supaya CSV cuma dibaca sekali per proses server (bukan tiap request)
_DATASET_CACHE = None


def get_dataset():
    global _DATASET_CACHE
    if _DATASET_CACHE is None:
        _DATASET_CACHE = _muat_dataset()
    return _DATASET_CACHE


def cari_referensi(bahan_input: str, n: int = 2):
    """
    Cari sampai n resep dari dataset yang kategorinya paling mirip dengan
    bahan yang dimasukkan user. Hasil ini dipakai sebagai referensi (RAG)
    di dalam prompt yang dikirim ke Gemini.
    """
    kategori_user = _kategori_bahan_user(bahan_input)
    if not kategori_user:
        return []

    dataset = get_dataset()
    skor = []
    for resep in dataset:
        overlap = len(kategori_user & resep["kategori"])
        if overlap > 0:
            skor.append((overlap, resep))

    skor.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in skor[:n]]


def format_referensi_untuk_prompt(daftar_referensi: list) -> str:
    """Ubah hasil cari_referensi() jadi teks siap sisip ke dalam prompt Gemini."""
    if not daftar_referensi:
        return ""

    blok = []
    for r in daftar_referensi:
        bahan_str = "; ".join(r["bahan"]) if r["bahan"] else "-"
        blok.append(
            f"- {r['nama']} (ukuran {r['size']}, harga referensi kafe asli: {r['harga_referensi']}): {bahan_str}"
        )

    return (
        "\n\nSebagai referensi tambahan, berikut proporsi/takaran dari beberapa resep "
        "minuman profesional coffee shop sungguhan yang kategorinya mirip (bersumber dari "
        "dataset asli, bukan karangan). Gunakan ini HANYA sebagai inspirasi pola/rasio "
        "antar bahan, BUKAN untuk ditiru satuannya persis (karena bahan & satuan di dataset "
        "ini beda dengan bahan minimarket yang disebut user):\n" + "\n".join(blok)
    )


def nama_referensi_saja(daftar_referensi: list) -> str:
    """Ambil nama-nama resep referensi saja, dipisah koma (untuk disimpan di riwayat)."""
    return ", ".join(r["nama"] for r in daftar_referensi)
