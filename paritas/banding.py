#!/usr/bin/env python3
"""Uji paritas: modul dasar lawan modul gabungan lux-trading.

Standar penyelesaian yang diminta menuntut bukti bahwa penggabungan TIDAK
membawa regresi dan tidak menyelipkan perbedaan implementasi yang tidak
disengaja. Membandingkan angka agregat saja tidak cukup, sebab dua jalur kode
yang berbeda bisa kebetulan menghasilkan total yang mirip. Karena itu tiap
lengan menghitung sidik jari md5 atas SELURUH trade secara berurutan, lengkap
dengan simbol, strategi, arah, waktu masuk, waktu keluar, alasan keluar, dan
tiga angka PnL. Sidik jari yang sama berarti paritas perilaku yang sebenarnya.

Catatan penting untuk membaca hasil. Perbedaan INVENTARIS berkas adalah
wajar dan memang diharapkan, karena lux-trading menambahkan lapisan
eksekusi_aman yang tidak ada di modul dasar. Yang tidak boleh berbeda adalah
PERILAKU lapis strategi dan backtest.
"""
import json
import os
import subprocess
import sys
import time

KELUAR = "hasil/paritas"
LENGAN = os.path.join("paritas", "lengan.py")
AKAR_A = os.environ.get("PAR_AKAR_A", "klon_modul")
AKAR_B = os.environ.get("PAR_AKAR_B", "/tmp/klon_lux")
LABEL_A = os.environ.get("PAR_LABEL_A", "a_modul_dasar")
LABEL_B = os.environ.get("PAR_LABEL_B", "b_lux_trading")
BATAS_PROSES = float(os.environ.get("PAR_BATAS_PROSES", "3000"))

KUNCI_TOTAL = ["trade", "menang", "pnl_bersih", "pnl_kotor", "biaya", "pf_bersih"]
KUNCI_MESIN = [
    "bar_dievaluasi",
    "entry_batal_gap",
    "entry_ditolak_biaya",
    "entry_ditolak_sizing",
    "jumlah_trade",
    "kalah",
    "menang",
]

out = {"perintah": "paritas", "catatan": []}


def tulis():
    os.makedirs(KELUAR, exist_ok=True)
    fh = open(os.path.join(KELUAR, "PARITAS.json"), "w", encoding="utf-8")
    json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True, default=str)
    fh.close()


def ekor(x):
    if x is None:
        return ""
    return str(x)[-1800:]


def jalankan(label, akar, berkas):
    env = dict(os.environ)
    env["PAR_AKAR"] = akar
    env["PAR_LABEL"] = label
    env["PAR_KELUARAN"] = berkas
    env["LUX_AKAR"] = akar
    env["AB95_PATH"] = os.path.join(akar, "scripts", "ab95.py")
    t = time.time()
    try:
        p = subprocess.run(
            [sys.executable, LENGAN],
            env=env,
            capture_output=True,
            text=True,
            timeout=BATAS_PROSES,
        )
        return {
            "label": label,
            "akar": akar,
            "rc": p.returncode,
            "detik": round(time.time() - t, 1),
            "stdout_ekor": ekor(p.stdout),
            "stderr_ekor": ekor(p.stderr),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "label": label,
            "akar": akar,
            "rc": -9,
            "detik": round(time.time() - t, 1),
            "stdout_ekor": ekor(getattr(e, "stdout", "")),
            "stderr_ekor": "TIMEOUT proses lengan",
        }


def baca(jalur):
    if not os.path.exists(jalur):
        return None
    try:
        fh = open(jalur, "r", encoding="utf-8")
        data = json.load(fh)
        fh.close()
        return data
    except Exception:
        return None


def beda_peta(a, b):
    a = a or {}
    b = b or {}
    ka = set(a)
    kb = set(b)
    beda = []
    for k in sorted(ka & kb):
        if a[k] != b[k]:
            beda.append(k)
    return {
        "hanya_di_a": sorted(ka - kb),
        "hanya_di_b": sorted(kb - ka),
        "beda_isi": beda,
        "identik": len(ka & kb) - len(beda),
    }


def beda_angka(a, b, kunci, tol=1e-6):
    a = a or {}
    b = b or {}
    keluar = {}
    for k in sorted(set(a) & set(b)):
        pa = a.get(k) or {}
        pb = b.get(k) or {}
        d = {}
        for f in kunci:
            va = pa.get(f)
            vb = pb.get(f)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                if abs(float(va) - float(vb)) > tol:
                    d[f] = [va, vb, round(float(vb) - float(va), 6)]
            elif va != vb:
                d[f] = [va, vb, None]
        if d:
            keluar[k] = d
    hanya = {"hanya_di_a": sorted(set(a) - set(b)), "hanya_di_b": sorted(set(b) - set(a))}
    return keluar, hanya


os.makedirs(KELUAR, exist_ok=True)
BERKAS_A = os.path.join(KELUAR, "lengan_a.json")
BERKAS_B = os.path.join(KELUAR, "lengan_b.json")

out["proses"] = {}
out["proses"]["a"] = jalankan(LABEL_A, AKAR_A, BERKAS_A)
tulis()
out["proses"]["b"] = jalankan(LABEL_B, AKAR_B, BERKAS_B)
tulis()

A = baca(BERKAS_A)
B = baca(BERKAS_B)
if not A or not B:
    out["vonis"] = "TIDAK_LENGKAP"
    out["catatan"].append("salah satu lengan tidak menghasilkan JSON")
    tulis()
    print("PARITAS=TIDAK_LENGKAP")
    print(json.dumps(out["proses"], indent=1, ensure_ascii=False)[:5000])
    sys.exit(1)

out["lengan"] = {
    "a": {
        "label": A.get("label"),
        "akar": A.get("akar"),
        "lux_modul_file": A.get("lux_modul_file"),
        "berkas_py": A.get("jumlah_berkas_py"),
        "detik": A.get("detik"),
        "galat": A.get("galat"),
    },
    "b": {
        "label": B.get("label"),
        "akar": B.get("akar"),
        "lux_modul_file": B.get("lux_modul_file"),
        "berkas_py": B.get("jumlah_berkas_py"),
        "detik": B.get("detik"),
        "galat": B.get("galat"),
    },
}

out["inventaris"] = beda_peta(A.get("inventaris"), B.get("inventaris"))
out["registry_sama"] = A.get("registry_id") == B.get("registry_id")
out["registry_selisih"] = sorted(
    set(A.get("registry_id") or []) ^ set(B.get("registry_id") or [])
)
out["modal_awal"] = {"a": A.get("modal_awal"), "b": B.get("modal_awal")}
out["simbol_sama"] = A.get("simbol_diproses") == B.get("simbol_diproses")
out["simbol_jumlah"] = {
    "a": len(A.get("simbol_diproses") or []),
    "b": len(B.get("simbol_diproses") or []),
}
out["bar_tersedia"] = {"a": A.get("bar_tersedia"), "b": B.get("bar_tersedia")}
out["total"] = {"a": A.get("total"), "b": B.get("total")}

t_beda, _ = beda_angka({"total": A.get("total")}, {"total": B.get("total")}, KUNCI_TOTAL)
out["total_beda"] = t_beda

m_beda, _ = beda_angka({"mesin": A.get("mesin")}, {"mesin": B.get("mesin")}, KUNCI_MESIN)
out["mesin"] = {"a": A.get("mesin"), "b": B.get("mesin")}
out["mesin_beda"] = m_beda

s_beda, s_hanya = beda_angka(
    A.get("per_simbol"), B.get("per_simbol"), ["trade", "pnl_bersih"]
)
out["per_simbol_beda"] = s_beda
out["per_simbol_hanya"] = s_hanya

st_beda, st_hanya = beda_angka(
    A.get("per_strategi"), B.get("per_strategi"), ["trade", "pnl_bersih"]
)
out["per_strategi_beda"] = st_beda
out["per_strategi_hanya"] = st_hanya

out["sidik_trade"] = {"a": A.get("sidik_trade"), "b": B.get("sidik_trade")}
out["sidik_cocok"] = A.get("sidik_trade") == B.get("sidik_trade")

perilaku_identik = bool(
    out["sidik_cocok"]
    and out["simbol_sama"]
    and out["registry_sama"]
    and not out["total_beda"]
    and not out["mesin_beda"]
    and not out["per_simbol_beda"]
    and not out["per_strategi_beda"]
    and not s_hanya["hanya_di_a"]
    and not s_hanya["hanya_di_b"]
    and not st_hanya["hanya_di_a"]
    and not st_hanya["hanya_di_b"]
)
out["vonis"] = "IDENTIK" if perilaku_identik else "BEDA"
out["catatan"].append(
    "perbedaan inventaris berkas wajar karena lux-trading menambah lapisan eksekusi_aman; yang diuji di sini adalah paritas perilaku lapis strategi dan backtest"
)
tulis()

ringkas = {
    "vonis": out["vonis"],
    "sidik_cocok": out["sidik_cocok"],
    "sidik_trade": out["sidik_trade"],
    "registry_sama": out["registry_sama"],
    "registry_selisih": out["registry_selisih"],
    "simbol_sama": out["simbol_sama"],
    "simbol_jumlah": out["simbol_jumlah"],
    "bar_tersedia": out["bar_tersedia"],
    "total": out["total"],
    "total_beda": out["total_beda"],
    "mesin": out["mesin"],
    "mesin_beda": out["mesin_beda"],
    "jumlah_simbol_beda": len(out["per_simbol_beda"]),
    "jumlah_strategi_beda": len(out["per_strategi_beda"]),
    "inventaris": {
        "identik": out["inventaris"]["identik"],
        "hanya_di_a": out["inventaris"]["hanya_di_a"][:40],
        "hanya_di_b": out["inventaris"]["hanya_di_b"][:40],
        "beda_isi": out["inventaris"]["beda_isi"][:40],
    },
    "lengan": out["lengan"],
    "proses_rc": {"a": out["proses"]["a"]["rc"], "b": out["proses"]["b"]["rc"]},
}
print(json.dumps(ringkas, indent=1, ensure_ascii=False, default=str)[:7000])

if out["per_simbol_beda"]:
    print("--- 10 simbol paling berbeda ---")
    urut = sorted(
        out["per_simbol_beda"].items(),
        key=lambda kv: abs((kv[1].get("pnl_bersih") or [0, 0, 0])[2] or 0),
        reverse=True,
    )
    for nama, d in urut[:10]:
        print(nama + " -> " + json.dumps(d, ensure_ascii=False))

print("keluaran: " + os.path.abspath(os.path.join(KELUAR, "PARITAS.json")))
sys.exit(0 if perilaku_identik else 1)
