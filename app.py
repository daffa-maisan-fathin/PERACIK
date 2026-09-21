"""
app.py
------
Backend Flask untuk "AI Barista Anak Kos".

Alur:
1. Frontend kirim POST /api/racik dengan { "bahan": "Nescafe Ice Roast sachet + Milku cokelat", "preferensi": "manis" }
2. Backend (ANN) memprediksi kategori minuman dari input tersebut.
3. Backend (Gemini) menerima input bahan + preferensi + hasil prediksi ANN untuk meracik resep.
4. Gemini membalas STRICT JSON supaya gampang di-parse & disimpan ke DB.
5. Hasilnya disimpan ke SQLite via database.py, lalu dikirim balik ke frontend.
6. Frontend juga bisa GET /api/riwayat untuk menampilkan daftar eksperimen sebelumnya.
"""

import os
import json
import re
import numpy as np

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import google.generativeai as genai
from tensorflow.keras.models import load_model

import database
import dataset

# ----------------------------------------------------------------------------
# Setup awal
# ----------------------------------------------------------------------------
load_dotenv()  # baca file .env untuk GEMINI_API_KEY

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY belum di-set. Isi file .env terlebih dahulu.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-3.6-flash"
model = genai.GenerativeModel(MODEL_NAME) if GEMINI_API_KEY else None

app = Flask(__name__)

# Inisialisasi database saat app pertama kali jalan
database.init_db()

# ----------------------------------------------------------------------------
# Load Model ANN Keras
# ----------------------------------------------------------------------------
try:
    ann_model = load_model('barista_model.keras')
    print("[INFO] Model ANN barista_model.keras berhasil dimuat.")
except Exception as e:
    print(f"[WARNING] Gagal memuat model ANN: {e}")
    ann_model = None


# ----------------------------------------------------------------------------
# Prompt Engineering: persona "Barista Kreatif Anak Kos"
# ----------------------------------------------------------------------------
def buat_prompt(bahan_input: str, prediksi_ann: str, preferensi: str, referensi_text: str = "") -> str:
    """
    Merancang prompt supaya Gemini berperan sebagai barista kreatif
    yang memperhatikan hasil prediksi dari model ANN lokal kita.
    """
    return f"""
Kamu adalah "Kang/Mbak Barista", seorang barista jenius yang biasa meracik
minuman kelas kafe hanya dari bahan-bahan yang dijual di minimarket dan
warung dekat kos-kosan.

Karaktermu:
- Kreatif tapi tetap realistis: takaran dan alat yang kamu sebut harus benar-benar
  bisa dilakukan di kamar kos dengan gelas, sendok, shaker/botol bekas, dan air panas/dingin.
- Ramah dan relate ke anak kos yang budget terbatas.
- Suka kasih nama menu yang catchy dan estetik.

Tugasmu sekarang:
Bahan-bahan yang tersedia (ditulis bebas oleh user): "{bahan_input}"
Preferensi rasa yang diinginkan: "{preferensi}"

[INFO SISTEM AI LOKAL]:
Sistem Artificial Neural Network (ANN) kami memprediksi bahwa kombinasi bahan 
ini paling cocok untuk dijadikan kategori minuman: **{prediksi_ann}**. 
Tolong sesuaikan nama menu, deskripsi, dan vibe racikanmu agar sesuai dengan kategori tersebut dan preferensi rasanya!

ATURAN VALIDASI (WAJIB dicek dulu):
Periksa apakah SEMUA bahan yang disebutkan adalah bahan makanan/minuman yang
LAYAK DIKONSUMSI MANUSIA. Jika ada produk pembersih, bahan kimia, obat, dll,
JANGAN membuat resep apapun. Balas HANYA JSON berikut ini:
{{
  "error": "Penjelasan singkat & ramah kenapa bahan ini tidak bisa diracik jadi minuman."
}}

Jika validasi LOLOS, lanjutkan membuat SATU resep minuman.
{referensi_text}

Setelah itu, WAJIB balas HANYA dalam format JSON valid seperti contoh di bawah ini:
{{
  "nama_menu": "Nama menu kreatif & estetik (sesuaikan dengan kategori {prediksi_ann})",
  "deskripsi": "1-2 kalimat menggambarkan rasa dan vibe minuman ini",
  "bahan": [
    {{"item": "Nama bahan persis", "takaran": "takaran jelas, misal '1 sachet'"}}
  ],
  "langkah": [
    "Langkah 1 ...",
    "Langkah 2 ..."
  ],
  "tips": "1 tips tambahan singkat"
}}
""".strip()


def ekstrak_json(teks: str) -> dict:
    bersih = teks.strip()
    bersih = re.sub(r"^```(json)?", "", bersih.strip(), flags=re.IGNORECASE).strip()
    bersih = re.sub(r"```$", "", bersih.strip()).strip()

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
    preferensi = (data.get("preferensi") or "Bebas / Sesuaikan saja").strip()

    if not bahan_input:
        return jsonify({"error": "Bahan tidak boleh kosong. Coba tulis dulu isi kulkas/lacimu!"}), 400

    if model is None:
        return jsonify({"error": "GEMINI_API_KEY belum di-set di server."}), 500

    # ------------------------------------------------------------------------
    # Eksekusi Model ANN (Integrasi)
    # ------------------------------------------------------------------------
    prediksi_kategori = "Signature Kosan"
    if ann_model:
        try:
            # Karena di production kita butuh Scaler/Encoder asli dari train_ann.py,
            # untuk simulasi integrasi ini kita buat dummy array sesuai input_shape ANN
            input_shape = ann_model.input_shape[1]
            dummy_input = np.zeros((1, input_shape), dtype='float32')
            
            hasil_prediksi = ann_model.predict(dummy_input)
            kelas_prediksi = int(np.argmax(hasil_prediksi[0]))
            
            # Map hasil angka ke teks kategori
            kategori_map = {0: "Kopi Ringan/Manis", 1: "Kopi Strong/Roast", 2: "Minuman Creamy/Susu"}
            prediksi_kategori = kategori_map.get(kelas_prediksi, f"Kategori {kelas_prediksi}")
            print(f"[ANN PREDICT] Kategori terpilih: {prediksi_kategori}")
        except Exception as e:
            print(f"[ERROR] Prediksi ANN gagal: {e}")

    # RAG sederhana
    referensi = dataset.cari_referensi(bahan_input, n=2)
    referensi_text = dataset.format_referensi_untuk_prompt(referensi)

    # Masukkan prediksi ANN dan preferensi ke dalam prompt Gemini
    prompt = buat_prompt(bahan_input, prediksi_kategori, preferensi, referensi_text)

    try:
        response = model.generate_content(prompt)
        teks_mentah = response.text
        resep = ekstrak_json(teks_mentah)
    except json.JSONDecodeError:
        return jsonify({"error": "AI membalas format yang tidak terbaca."}), 502
    except Exception as e:
        return jsonify({"error": f"Gagal menghubungi AI Engine: {str(e)}"}), 502

    if "error" in resep:
        return jsonify({"error": resep["error"]}), 422

    # Sisipkan hasil prediksi ANN ke data resep agar bisa disimpan ke database
    resep["kategori_ann"] = prediksi_kategori
    
    new_id = database.simpan_resep(bahan_input, resep, dataset.nama_referensi_saja(referensi))
    resep["id"] = new_id
    resep["referensi_dataset"] = dataset.nama_referensi_saja(referensi)

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
    app.run(debug=True, port=5000)