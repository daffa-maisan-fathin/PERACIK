"""
app.py
------
Backend Flask untuk "AI Barista Anak Kos".

Alur:
1. Frontend kirim POST /api/racik dengan { "bahan": "Nescafe Ice Roast sachet + Milku cokelat" }
2. Backend bikin prompt khusus (persona barista kreatif anak kos) lalu kirim ke Gemini API.
3. Gemini diminta balas STRICT JSON supaya gampang di-parse & disimpan ke DB.
4. Hasilnya disimpan ke SQLite via database.py, lalu dikirim balik ke frontend.
5. Frontend juga bisa GET /api/riwayat untuk menampilkan daftar eksperimen sebelumnya.
"""

import os
import json
import re

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import google.generativeai as genai

import database

# ----------------------------------------------------------------------------
# Setup awal
# ----------------------------------------------------------------------------
load_dotenv()  # baca file .env untuk GEMINI_API_KEY

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY belum di-set. Isi file .env terlebih dahulu.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-3.6-flash"  # model Flash terbaru yang tersedia (per Sep 2026)
model = genai.GenerativeModel(MODEL_NAME) if GEMINI_API_KEY else None

app = Flask(__name__)

# Inisialisasi database saat app pertama kali jalan
database.init_db()


# ----------------------------------------------------------------------------
# Prompt Engineering: persona "Barista Kreatif Anak Kos"
# ----------------------------------------------------------------------------
def buat_prompt(bahan_input: str) -> str:
    """
    Merancang prompt supaya Gemini berperan sebagai barista kreatif
    yang paham banget isi minimarket/warung Indonesia, dan SELALU
    membalas dalam format JSON murni (tanpa markdown/basa-basi)
    supaya bisa langsung di-parse oleh backend.
    """
    return f"""
Kamu adalah "Kang/Mbak Barista", seorang barista jenius yang biasa meracik
minuman kelas kafe hanya dari bahan-bahan yang dijual di minimarket dan
warung dekat kos-kosan (contoh: sachet kopi instan seperti Nescafe/Kapal Api/ABC,
susu kotak/UHT seperti Milku/Ultra Milk/Frisian Flag, creamer, teh celup,
sirup, air mineral, es batu, dsb).

Karaktermu:
- Kreatif tapi tetap realistis: takaran dan alat yang kamu sebut harus benar-benar
  bisa dilakukan di kamar kos dengan gelas, sendok, shaker/botol bekas, dan air panas/dingin.
- Ramah dan relate ke anak kos yang budget terbatas (hemat, praktis, tidak butuh alat mahal).
- Suka kasih nama menu yang catchy dan estetik ala kafe kekinian.

Tugasmu sekarang:
Bahan-bahan yang tersedia (ditulis bebas oleh user, boleh typo/singkatan): 
"{bahan_input}"

Buatkan SATU resep minuman kreatif dari bahan-bahan tersebut (boleh menambahkan
bahan dasar yang hampir pasti ada di kos seperti air, es batu, gula, air panas —
tapi JANGAN menambahkan bahan yang tidak umum/mahal).

WAJIB balas HANYA dalam format JSON valid seperti contoh di bawah ini,
TANPA markdown code fence, TANPA penjelasan tambahan di luar JSON:

{{
  "nama_menu": "Nama menu kreatif & estetik",
  "deskripsi": "1-2 kalimat menggambarkan rasa dan vibe minuman ini",
  "bahan": [
    {{"item": "Nama bahan persis seperti input atau turunannya", "takaran": "takaran jelas, misal '1 sachet' atau '150 ml'"}}
  ],
  "langkah": [
    "Langkah 1 ...",
    "Langkah 2 ..."
  ],
  "tips": "1 tips tambahan singkat (misal cara bikin lebih creamy, lebih dingin, atau substitusi bahan)"
}}

Pastikan field "bahan" mencakup semua bahan input user (dan tambahan dasar jika perlu),
dan "langkah" minimal 3 langkah, urut, dan mudah diikuti anak kos yang baru belajar bikin minuman.
""".strip()


def ekstrak_json(teks: str) -> dict:
    """
    Gemini kadang tetap membungkus JSON dengan ```json ... ``` walau sudah
    diminta tidak. Fungsi ini membersihkan itu dan mem-parse JSON dengan aman.
    """
    bersih = teks.strip()
    bersih = re.sub(r"^```(json)?", "", bersih.strip(), flags=re.IGNORECASE).strip()
    bersih = re.sub(r"```$", "", bersih.strip()).strip()

    # Ambil bagian dari '{' pertama sampai '}' terakhir sebagai jaring pengaman
    start = bersih.find("{")
    end = bersih.rfind("}")
    if start != -1 and end != -1:
        bersih = bersih[start : end + 1]

    return json.loads(bersih)


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/racik", methods=["POST"])
def racik():
    data = request.get_json(silent=True) or {}
    bahan_input = (data.get("bahan") or "").strip()

    if not bahan_input:
        return jsonify({"error": "Bahan tidak boleh kosong. Coba tulis dulu isi kulkas/lacimu!"}), 400

    if model is None:
        return jsonify({
            "error": "GEMINI_API_KEY belum di-set di server. Cek file .env sesuai README."
        }), 500

    prompt = buat_prompt(bahan_input)

    try:
        response = model.generate_content(prompt)
        teks_mentah = response.text
        resep = ekstrak_json(teks_mentah)
    except json.JSONDecodeError:
        return jsonify({
            "error": "AI membalas format yang tidak terbaca. Coba racik ulang dengan bahan yang lebih spesifik."
        }), 502
    except Exception as e:
        return jsonify({"error": f"Gagal menghubungi AI Engine: {str(e)}"}), 502

    # Simpan ke database
    new_id = database.simpan_resep(bahan_input, resep)
    resep["id"] = new_id

    return jsonify(resep), 200


@app.route("/api/riwayat", methods=["GET"])
def riwayat():
    limit = request.args.get("limit", default=50, type=int)
    daftar = database.ambil_riwayat(limit=limit)
    return jsonify(daftar), 200


@app.route("/api/riwayat/<int:resep_id>", methods=["GET"])
def detail_riwayat(resep_id):
    resep = database.ambil_resep_by_id(resep_id)
    if not resep:
        return jsonify({"error": "Resep tidak ditemukan"}), 404
    return jsonify(resep), 200


if __name__ == "__main__":
    # debug=True hanya untuk pengembangan lokal, matikan saat deploy production
    app.run(debug=True, port=5000)