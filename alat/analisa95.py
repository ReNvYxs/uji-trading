#!/usr/bin/env python3
"""Backtest 95 pair dengan atribusi per-strategi yang BENAR.

Latar belakang (bukti, bukan asumsi):
  - hasil/bt95/bedah_runner.txt: ab95.py baris 412-415 sudah benar menjumlahkan
    kandidat_per_strategi; jadi agregatornya bukan tersangka.
  - hasil/bt95/probe_kandidat.json: Backtester.ringkas() TIDAK memuat kunci
    kandidat_per_strategi sama sekali (ada_kunci_kandidat=false), dan Pipeline
    internal Backtester tidak mengakumulasi StatistikJalan (terakumulasi=false).
    Akibatnya seluruh metrik per-strategi di laporan lama bernilai None.

Cara pemulihan di sini:
  Atribusi HASIL NYATA diambil dari hasil.trades[].strategy_id - nol biaya
  komputasi tambahan, dan denominatornya tepat sama dengan backtest.

Catatan penting soal denominator (jangan dicampur):
  Probe mengukur Backtester bar_dievaluasi=366 sedangkan Pipeline penuh 1220
  pada plane yang sama. Backtester melompati bar selagi posisi terbuka, jadi
  jumlah KANDIDAT dari pass Pipeline TIDAK sebanding langsung dengan jumlah
  TRADE. Karena itu pass Pipeline di sini bersifat diagnostik terpisah dan
  diberi label sendiri, bukan digabung ke metrik trade.

Tidak ada logika strategi yang diubah. Semua yang dihitung di sini adalah
pembacaan ulang atas keluaran modul apa adanya.
"""
import importlib.util
import json
import os
import sys
import time
import traceback
from collections import defaultdict

AB = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
KELUARAN = os.environ.get("LUX_KELUARAN", "hasil/bt95/analisa.json")
KONFIG_NAMA = os.environ.get("LUX_KONFIG", "single_15m")
MAKS_BAR = int(os.environ.get("LUX_MAKS_BAR", "6000") or 0)
BATAS_DETIK = float(os.environ.get("LUX_BATAS_DETIK", "3000"))
SARING = (os.environ.get("LUX_SARING_BIAYA", "1") not in ("0", "false", "False"))
PIPELINE_PASS = os.environ.get("LUX_PIPELINE_PASS", "0") == "1"
PIPELINE_MAKS = int(os.environ.get("LUX_PIPELINE_MAKS", "12"))
RINGKAS_INV = "hasil/bt95/RINGKAS_INVENTARIS.json"

t0 = time.time()
out = {
    "perintah": "analisa95",
    "konfig": KONFIG_NAMA,
    "maks_bar": MAKS_BAR,
    "saring_biaya": SARING,
    "catatan": [],
    "galat": {},
}


def simpan():
    induk = os.path.dirname(KELUARAN)
    if induk:
        os.makedirs(induk, exist_ok=True)
    with open(KELUARAN, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True, default=str)


def bulat(x, n=4):
    if x is None:
        return None
    try:
        if x != x or x in (float("inf"), float("-inf")):
            return None
    except Exception:
        return None
    return round(float(x), n)


def pf(laba, rugi):
    if rugi and rugi > 0:
        return bulat(laba / rugi)
    return None if not laba else float("inf")


def metrik(rows):
    """Metrik dihitung sendiri agar definisinya eksplisit dan bisa diaudit."""
    n = len(rows)
    if n == 0:
        return {"trade": 0}
    pnl = [r["pnl_bersih"] for r in rows]
    kotor = [r["pnl_kotor"] for r in rows]
    biaya = [r["biaya"] for r in rows]
    rr = [r["r_multiple"] for r in rows if isinstance(r.get("r_multiple"), (int, float))]
    menang = sum(1 for x in pnl if x > 0)
    laba_b = sum(x for x in pnl if x > 0)
    rugi_b = -sum(x for x in pnl if x < 0)
    laba_k = sum(x for x in kotor if x > 0)
    rugi_k = -sum(x for x in kotor if x < 0)
    m = {
        "trade": n,
        "menang": menang,
        "win_rate": bulat(menang / n),
        "pnl_bersih": bulat(sum(pnl)),
        "pnl_kotor": bulat(sum(kotor)),
        "biaya": bulat(sum(biaya)),
        "pf_bersih": pf(laba_b, rugi_b),
        "pf_kotor": pf(laba_k, rugi_k),
        "biaya_per_trade": bulat(sum(biaya) / n),
        "edge_kotor_per_trade": bulat(sum(kotor) / n),
        "pnl_bersih_per_trade": bulat(sum(pnl) / n),
        "sampel_cukup": n >= 200,
    }
    if rr:
        m["expectancy_r"] = bulat(sum(rr) / len(rr))
        m["r_menang"] = bulat(
            sum(x for x in rr if x > 0) / max(1, sum(1 for x in rr if x > 0))
        )
        m["r_kalah"] = bulat(
            sum(x for x in rr if x <= 0) / max(1, sum(1 for x in rr if x <= 0))
        )
    return m


def dd_maks(rows):
    """Drawdown pada kurva PnL kumulatif berurutan waktu."""
    urut = sorted(rows, key=lambda r: (r.get("ts_keluar") or 0))
    puncak = 0.0
    kum = 0.0
    dd = 0.0
    for r in urut:
        kum += r["pnl_bersih"]
        puncak = max(puncak, kum)
        dd = max(dd, puncak - kum)
    return bulat(dd)


# ---------- muat runner ----------
try:
    spec = importlib.util.spec_from_file_location("ab95_mod", AB)
    ab = importlib.util.module_from_spec(spec)
    sys.modules["ab95_mod"] = ab
    spec.loader.exec_module(ab)
except Exception:
    out["galat"]["impor_ab95"] = traceback.format_exc()[-1500:]
    simpan()
    raise SystemExit(1)

try:
    out["varian"] = ab.terapkan_varian()
except Exception:
    out["galat"]["varian"] = traceback.format_exc()[-1500:]

entry_tf, ctx = ab.KONFIG[KONFIG_NAMA]
tfs = (entry_tf,) + tuple(ctx)
TFPlan = getattr(ab, "TFPlan")
tfplan = TFPlan(entry_tf=entry_tf, context_tfs=tuple(ctx))
out["entry_tf"] = entry_tf
out["context_tfs"] = list(ctx)
out["modal_awal_per_simbol"] = ab.MODAL_AWAL
out["metodologi"] = (
    "tiap simbol = akun terpisah bermodal sama; angka gabungan adalah agregat "
    "statistik lintas simbol untuk mengukur edge, bukan kurva ekuitas satu akun"
)

# ---------- segmentasi higiene dataset ----------
seg_saham, seg_pendek = set(), set()
try:
    with open(RINGKAS_INV, encoding="utf-8") as fh:
        inv = json.load(fh)
    seg_saham = set((inv.get("simbol_dengan_volume_nol") or {}).get("rinci", {}))
    seg_pendek = set((inv.get("riwayat_pendek") or {}).get("simbol", []))
    out["catatan"].append("segmentasi dibaca dari " + RINGKAS_INV)
except Exception:
    out["catatan"].append("RINGKAS_INVENTARIS.json tidak terbaca; segmentasi kosong")


def kelas_simbol(s):
    if s in seg_pendek:
        return "riwayat_pendek"
    if s in seg_saham:
        return "mirip_saham"
    return "kripto_24_7"


out["segmentasi"] = {
    "mirip_saham": sorted(seg_saham),
    "riwayat_pendek": sorted(seg_pendek),
    "catatan": (
        "tidak ada simbol yang dibuang; segmentasi hanya membuat pencemaran "
        "dataset terlihat. riwayat_pendek diprioritaskan karena warmup strategi "
        "mencapai 280 bar sehingga riwayat sangat pendek tidak bisa menghasilkan "
        "sinyal sah"
    ),
}

# ---------- jalankan ----------
simbol_list = ab.daftar_simbol(tfs)
out["simbol_tersedia"] = len(simbol_list)

semua = []
per_simbol = {}
gagal = {}
bar_total = 0
tolak_biaya = 0
batal_gap = 0
tolak_kode = defaultdict(int)
diproses = 0
terpotong = False

for simbol in simbol_list:
    if time.time() - t0 > BATAS_DETIK:
        terpotong = True
        break
    try:
        plane = ab.muat_plane(simbol, tfs, MAKS_BAR)
        bt = ab.buat_backtester(plane, tfplan, SARING)
        hasil = bt.jalankan()
    except Exception as e:
        gagal[simbol] = str(e)[:200]
        continue
    diproses += 1
    r = hasil.ringkas() or {}
    bar_total += r.get("bar_dievaluasi", 0) or 0
    tolak_biaya += r.get("entry_ditolak_biaya", 0) or 0
    batal_gap += r.get("entry_batal_gap", 0) or 0
    for k, v in (r.get("tolak_biaya_per_kode") or {}).items():
        tolak_kode[k] += v
    lokal = []
    for t in hasil.trades:
        rec = {
            "simbol": simbol,
            "kelas": kelas_simbol(simbol),
            "strategy_id": getattr(t, "strategy_id", None),
            "kelompok": getattr(t, "kelompok", None),
            "arah": getattr(t, "arah", None),
            "ts_entry": getattr(t, "ts_entry", None),
            "ts_keluar": getattr(t, "ts_keluar", None),
            "alasan_keluar": getattr(t, "alasan_keluar", None),
            "pnl_bersih": float(getattr(t, "pnl_bersih", 0.0) or 0.0),
            "pnl_kotor": float(getattr(t, "pnl_kotor", 0.0) or 0.0),
            "biaya": float(getattr(t, "biaya", 0.0) or 0.0),
            "r_multiple": getattr(t, "r_multiple", None),
        }
        lokal.append(rec)
        semua.append(rec)
    m = metrik(lokal)
    m["kelas"] = kelas_simbol(simbol)
    m["bar_dievaluasi"] = r.get("bar_dievaluasi")
    m["max_drawdown"] = dd_maks(lokal)
    per_simbol[simbol] = m

out["simbol_diproses"] = diproses
out["simbol_gagal"] = gagal
out["terpotong_batas_waktu"] = terpotong
out["detik"] = round(time.time() - t0, 1)


def kelompokkan(kunci, minimal=1):
    grup = defaultdict(list)
    for r in semua:
        grup[r.get(kunci)].append(r)
    hasil_g = {}
    for k, lst in sorted(grup.items(), key=lambda kv: -len(kv[1])):
        if len(lst) < minimal:
            continue
        hasil_g[str(k)] = metrik(lst)
    return hasil_g


total = metrik(semua)
total["bar_dievaluasi"] = bar_total
total["entry_ditolak_biaya"] = tolak_biaya
total["entry_batal_gap"] = batal_gap
total["tolak_biaya_per_kode"] = dict(sorted(tolak_kode.items()))
out["total"] = total

alasan = defaultdict(int)
for r in semua:
    alasan[str(r.get("alasan_keluar"))] += 1
out["alasan_keluar"] = dict(sorted(alasan.items()))

# INI yang hilang di laporan lama:
out["per_strategi"] = kelompokkan("strategy_id")
out["per_kelompok"] = kelompokkan("kelompok")
out["per_arah"] = kelompokkan("arah")
out["per_kelas_dataset"] = kelompokkan("kelas")
out["per_simbol"] = per_simbol

pair_trade = [s for s, m in per_simbol.items() if m.get("trade", 0) > 0]
pair_profit = [s for s, m in per_simbol.items() if (m.get("pnl_bersih") or 0) > 0]
out["pair_dengan_trade"] = len(pair_trade)
out["pair_profit"] = len(pair_profit)
out["breadth_pair_profit"] = bulat(
    len(pair_profit) / len(pair_trade) if pair_trade else None
)
out["simbol_tanpa_trade"] = sorted(s for s in per_simbol if per_simbol[s].get("trade", 0) == 0)

# ---------- pass Pipeline diagnostik (opsional, denominator BERBEDA) ----------
if PIPELINE_PASS:
    kand = defaultdict(int)
    menang_arb = defaultdict(int)
    dipakai = []
    try:
        for simbol in simbol_list[:PIPELINE_MAKS]:
            if time.time() - t0 > BATAS_DETIK:
                break
            plane = ab.muat_plane(simbol, tfs, MAKS_BAR)
            pipe = ab.buat_pipeline(plane, tfplan, SARING)
            hp = pipe.jalankan_rentang()
            stat = None
            if isinstance(hp, tuple):
                for x in hp:
                    if hasattr(x, "ringkas"):
                        stat = x
            elif hasattr(hp, "ringkas"):
                stat = hp
            rp = (stat.ringkas() if stat is not None else {}) or {}
            for k, v in (rp.get("kandidat_per_strategi") or {}).items():
                kand[k] += v
            for k, v in (rp.get("menang_per_strategi") or {}).items():
                menang_arb[k] += v
            dipakai.append(simbol)
    except Exception:
        out["galat"]["pipeline_pass"] = traceback.format_exc()[-1500:]
    out["diagnostik_pipeline"] = {
        "peringatan": (
            "denominator BERBEDA dari metrik trade: Backtester melompati bar "
            "selagi posisi terbuka, Pipeline mengevaluasi semua bar. Jangan "
            "membagi trade dengan kandidat seolah-olah sebanding."
        ),
        "simbol": dipakai,
        "kandidat_per_strategi": dict(sorted(kand.items(), key=lambda kv: -kv[1])),
        "menang_arbiter_per_strategi": dict(
            sorted(menang_arb.items(), key=lambda kv: -kv[1])
        ),
        "strategi_nol_kandidat": sorted(
            s for s in getattr(ab, "DAFTAR_ID", []) or [] if s not in kand
        ),
    }

out["detik"] = round(time.time() - t0, 1)
simpan()

ringkas_cetak = {
    k: out[k]
    for k in (
        "konfig",
        "varian",
        "entry_tf",
        "simbol_tersedia",
        "simbol_diproses",
        "terpotong_batas_waktu",
        "detik",
        "total",
        "per_arah",
        "per_kelas_dataset",
        "alasan_keluar",
        "pair_dengan_trade",
        "pair_profit",
        "breadth_pair_profit",
    )
    if k in out
}
ringkas_cetak["per_strategi_ringkas"] = {
    k: {
        "trade": v.get("trade"),
        "pf_bersih": v.get("pf_bersih"),
        "expectancy_r": v.get("expectancy_r"),
        "pnl_bersih": v.get("pnl_bersih"),
    }
    for k, v in out.get("per_strategi", {}).items()
}
print(json.dumps(ringkas_cetak, indent=1, ensure_ascii=False, default=str)[:8000])
print("keluaran: " + os.path.abspath(KELUARAN))
