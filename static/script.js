const el = (id) => document.getElementById(id);

const bahanInput = el("bahan-input");
const btnRacik = el("btn-racik");
const btnText = el("btn-text");
const pesanError = el("pesan-error");
const hasilResep = el("hasil-resep");
const riwayatList = el("riwayat-list");
const btnRefresh = el("btn-refresh");

function tampilkanError(pesan) {
  pesanError.textContent = pesan;
  pesanError.hidden = false;
}

function sembunyikanError() {
  pesanError.hidden = true;
  pesanError.textContent = "";
}

function formatWaktu(iso) {
  try {
    const d = new Date(iso.replace(" ", "T") + "Z");
    return d.toLocaleString("id-ID", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
  } catch (e) {
    return iso;
  }
}

function renderResep(resep) {
  el("hasil-nama").textContent = resep.nama_menu;
  el("hasil-deskripsi").textContent = resep.deskripsi || "";

  const ulBahan = el("hasil-bahan");
  ulBahan.innerHTML = "";
  (resep.bahan || []).forEach((b) => {
    const li = document.createElement("li");
    li.textContent = `${b.item} — ${b.takaran}`;
    ulBahan.appendChild(li);
  });

  const olLangkah = el("hasil-langkah");
  olLangkah.innerHTML = "";
  (resep.langkah || []).forEach((l) => {
    const li = document.createElement("li");
    li.textContent = l;
    olLangkah.appendChild(li);
  });

  const tipsWrap = el("hasil-tips-wrap");
  if (resep.tips) {
    el("hasil-tips").textContent = resep.tips;
    tipsWrap.hidden = false;
  } else {
    tipsWrap.hidden = true;
  }

  const referensiWrap = el("hasil-referensi-wrap");
  if (resep.referensi_dataset) {
    el("hasil-referensi").textContent =
      `Racikan ini terinspirasi dari pola resep: ${resep.referensi_dataset} (dataset Coffee Shop Chain Recipes, Kaggle).`;
    referensiWrap.hidden = false;
  } else {
    referensiWrap.hidden = true;
  }

  hasilResep.hidden = false;
  hasilResep.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRiwayat(daftar) {
  riwayatList.innerHTML = "";

  if (!daftar || daftar.length === 0) {
    riwayatList.innerHTML = `<p class="riwayat-kosong">belum ada eksperimen. racik menu pertamamu di atas!</p>`;
    return;
  }

  daftar.forEach((r) => {
    const item = document.createElement("div");
    item.className = "riwayat-item";
    item.innerHTML = `
      <p class="riwayat-nama">${r.nama_menu}</p>
      <p class="riwayat-meta">dari: ${r.bahan_input}</p>
      <p class="riwayat-meta">${formatWaktu(r.created_at)}</p>
    `;
    item.addEventListener("click", () => renderResep(r));
    riwayatList.appendChild(item);
  });
}

async function muatRiwayat() {
  try {
    const res = await fetch("/api/riwayat");
    if (!res.ok) throw new Error("gagal memuat riwayat");
    const data = await res.json();
    renderRiwayat(data);
  } catch (e) {
    riwayatList.innerHTML = `<p class="riwayat-kosong">gagal memuat riwayat. cek koneksi ke server.</p>`;
  }
}

async function racikMenu() {
  const bahan = bahanInput.value.trim();
  sembunyikanError();

  if (!bahan) {
    tampilkanError("tulis dulu bahan yang kamu punya, ya!");
    return;
  }

  btnRacik.disabled = true;
  btnText.textContent = "lagi diracik...";

  try {
    const res = await fetch("/api/racik", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bahan }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "terjadi kesalahan di server");
    }

    renderResep(data);
    muatRiwayat();
  } catch (e) {
    tampilkanError(e.message);
  } finally {
    btnRacik.disabled = false;
    btnText.textContent = "Racik Menu!";
  }
}

btnRacik.addEventListener("click", racikMenu);
btnRefresh.addEventListener("click", muatRiwayat);
bahanInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) racikMenu();
});

// muat riwayat begitu halaman dibuka
muatRiwayat();
