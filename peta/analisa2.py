#!/usr/bin/env python3
"""Peta timeframe + uji stabilitas dua paruh untuk 95 pair.

Beda dengan alat/analisa95.py:
  1. Uji stabilitas: tiap strategi dipecah ke paruh_1/paruh_2 memakai SATU batas
     waktu global (median ts_entry seluruh trade), lalu diberi vonis memakai
     gerbang milik modul sendiri: trade >= 200 DAN expectancy_r > 0 DAN kedua
     paruh positif.
  2. Tidak lagi memancarkan Infinity ke JSON (Infinity bukan JSON yang sah).
     Cacat kosmetik ini ditemukan pada keluaran run bt95 sebelumnya.
  3. Blok konsentrasi (strategi dan simbol) untuk mengukur seberapa bergantung
     hasil pada sedikit sumber.

Yang SENGAJA TIDAK dilakukan: mematikan strategi apa pun. Strategi tidak
independen - Backtester melompati bar selagi posisi terbuka. Bukti: pada A/B 4h
perubahan satu fungsi menggeser bar_dievaluasi dari 11550 ke 12683. Karena itu
'matikan strategi X lalu jumlahkan sisanya' bukan eksperimen yang sah dan mudah
berubah jadi curve-fitting. Stabilitas dua paruh menjawab pertanyaan yang sama
tanpa menyentuh registry.

Tidak ada logika strategi yang diubah di berkas ini.
"""
import importlib.util
import json
import os
import sys
import time
import traceback
from collections import defaultdict

AB = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
KELUARAN = os.environ.get("LUX_KELUARAN", "hasil/peta/analisa.json")
KONFIG_NAMA = os.environ.get("LUX_KONFIG", "single_4h")
MAKS_BAR = int(os.environ.get("LUX_MAKS_BAR", "6000") or 0)
BATAS_DETIK = float(os.environ.get("LUX_BATAS_DETIK", "3000"))
SARING = (os.environ.get("LUX_SARING_BIAYA", "1") not in ("0", "false", "False"))
RINGKAS_INV = "hasil/bt95/RINGKAS_INVENTARIS.json"
MIN_SAMPEL = int(os.environ.get("LUX_MIN_SAMPEL", "200"))

t0 = time.time()
out = {
    "perintah": "analisa2",
    "konfig": KONFIG_NAMA,
    "maks_bar": MAKS_BAR,
    "saring_biaya": SARING,
    "min_sampel_gerbang": MIN_SAMPEL,
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
    """Tidak pernah mengembalikan Infinity; JSON standar tidak mengenalnya."""
    if rugi and rugi > 0:
        return bulat(laba / rugi)
    return None


def metrik(rows):
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
        "tanpa_trade_rugi": bool(rugi_b <= 0),
        "biaya_per_trade": bulat(sum(biaya) / n),
        "edge_kotor_per_trade": bulat(sum(kotor) / n),
        "pnl_bersih_per_trade": bulat(sum(pnl) / n),
        "sampel_cukup": n >= MIN_SAMPEL,
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
    urut = sorted(rows, key=lambda r: (r.get("ts_keluar") or 0))
    puncak = 0.0
    kum = 0.0
    dd = 0.0
    for r in urut:
        kum += r["pnl_bersih"]
        puncak = max(puncak, kum)
        dd = max(dd, puncak - kum)
    return bulat(dd)


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

if KONFIG_NAMA not in ab.KONFIG:
    out["galat"]["konfig"] = "konfig tidak dikenal: " + KONFIG_NAMA
    out["konfig_tersedia"] = sorted(ab.KONFIG)
    simpan()
    raise SystemExit(2)

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
out["simbol_tanpa_trade"] = sorted(
    s for s in per_simbol if per_simbol[s].get("trade", 0) == 0
)

# ---------- uji stabilitas dua paruh ----------
ts_urut = sorted(r["ts_entry"] for r in semua if r.get("ts_entry") is not None)
batas_paruh = ts_urut[len(ts_urut) // 2] if ts_urut else None


def pecah(rows):
    p1 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] < batas_paruh]
    p2 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] >= batas_paruh]
    return p1, p2


def vonis(rows):
    m = metrik(rows)
    p1, p2 = pecah(rows)
    m1, m2 = metrik(p1), metrik(p2)
    pnl1 = m1.get("pnl_bersih") or 0.0
    pnl2 = m2.get("pnl_bersih") or 0.0
    dua_positif = bool(pnl1 > 0 and pnl2 > 0)
    expr = m.get("expectancy_r")
    return {
        "penuh": m,
        "paruh_1": m1,
        "paruh_2": m2,
        "kedua_paruh_positif": dua_positif,
        "sampel_cukup": bool(m.get("trade", 0) >= MIN_SAMPEL),
        "strategi_layak": bool(
            m.get("trade", 0) >= MIN_SAMPEL and (expr or 0) > 0 and dua_positif
        ),
    }


if batas_paruh is not None:
    grup_s = defaultdict(list)
    for r in semua:
        grup_s[str(r.get("strategy_id"))].append(r)
    stab = {}
    for sid, lst in sorted(grup_s.items(), key=lambda kv: -len(kv[1])):
        stab[sid] = vonis(lst)
    out["batas_paruh_ts"] = batas_paruh
    out["stabilitas_per_strategi"] = stab
    out["stabilitas_total"] = vonis(semua)
    out["daftar_strategi_layak"] = sorted(
        s for s, v in stab.items() if v["strategi_layak"]
    )
    out["daftar_strategi_rugi_dua_paruh"] = sorted(
        s
        for s, v in stab.items()
        if (v["paruh_1"].get("pnl_bersih") or 0) < 0
        and (v["paruh_2"].get("pnl_bersih") or 0) < 0
        and v["sampel_cukup"]
    )
    out["catatan"].append(
        "batas paruh = median ts_entry seluruh trade, sama untuk semua strategi"
    )

# ---------- konsentrasi ----------
kontrib = {
    sid: (m.get("pnl_bersih") or 0.0) for sid, m in out.get("per_strategi", {}).items()
}
net = total.get("pnl_bersih") or 0.0
jum_abs = sum(abs(v) for v in kontrib.values()) or 1.0
urut_simbol = sorted(
    ((s, m.get("pnl_bersih") or 0.0) for s, m in per_simbol.items()),
    key=lambda kv: kv[1],
)
out["konsentrasi"] = {
    "peringatan": (
        "net_tanpa_strategi_naif adalah pengurangan aritmetik, BUKAN prediksi "
        "hasil bila strategi dimatikan. Strategi tidak independen: Backtester "
        "melompati bar selagi posisi terbuka, sehingga mematikan satu strategi "
        "mengubah okupansi posisi dan membuka peluang bagi strategi lain. "
        "Bukti: A/B 4h menggeser bar_dievaluasi 11550 menjadi 12683."
    ),
    "net_total": bulat(net),
    "net_tanpa_strategi_naif": {
        sid: bulat(net - v) for sid, v in sorted(kontrib.items(), key=lambda kv: -abs(kv[1]))
    },
    "pangsa_absolut": {
        sid: bulat(abs(v) / jum_abs)
        for sid, v in sorted(kontrib.items(), key=lambda kv: -abs(kv[1]))
    },
    "simbol_terburuk_5": [[s, bulat(v)] for s, v in urut_simbol[:5]],
    "simbol_terbaik_5": [[s, bulat(v)] for s, v in urut_simbol[-5:][::-1]],
}

out["detik"] = round(time.time() - t0, 1)
simpan()

cetak = {
    k: out[k]
    for k in (
        "konfig",
        "varian",
        "entry_tf",
        "context_tfs",
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
        "daftar_strategi_layak",
        "daftar_strategi_rugi_dua_paruh",
    )
    if k in out
}
cetak["stabilitas_ringkas"] = {
    sid: {
        "trade": v["penuh"].get("trade"),
        "pf": v["penuh"].get("pf_bersih"),
        "expR": v["penuh"].get("expectancy_r"),
        "pnl": v["penuh"].get("pnl_bersih"),
        "p1_pnl": v["paruh_1"].get("pnl_bersih"),
        "p2_pnl": v["paruh_2"].get("pnl_bersih"),
        "layak": v["strategi_layak"],
    }
    for sid, v in list(out.get("stabilitas_per_strategi", {}).items())[:14]
}
print(json.dumps(cetak, indent=1, ensure_ascii=False, default=str)[:9000])
print("keluaran: " + os.path.abspath(KELUARAN))
