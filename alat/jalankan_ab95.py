#!/usr/bin/env python3
"""Pembungkus runner ab95.

Tujuan SATU-SATUNYA: memperbaiki *serialisasi* JSON.

Bukti masalahnya: runner asli menyelesaikan seluruh komputasi inventaris lalu
gagal tepat pada langkah tulis dengan
`TypeError: Object of type int64 is not JSON serializable`
(ab95.py baris 724, di dalam `tulis()`).

Pembungkus ini HANYA mengubah cara angka ditulis ke JSON (numpy int64 -> int,
float64 -> float). Ia TIDAK menyentuh logika strategi, sinyal, sizing, maupun
eksekusi. Setiap konversi dihitung per tipe dan dicatat ke berkas
`AB95_JEJAK_KONVERSI` supaya klaim ini bisa diperiksa, bukan dipercaya.
"""
import atexit
import collections
import json
import os
import runpy
import sys

_dump = json.dump
_dumps = json.dumps
_hitung = collections.Counter()


def _bawaan(o):
    _hitung[type(o).__name__] += 1
    item = getattr(o, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    tolist = getattr(o, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:
            pass
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def dump(obj, fp, **kw):
    kw.setdefault("default", _bawaan)
    return _dump(obj, fp, **kw)


def dumps(obj, **kw):
    kw.setdefault("default", _bawaan)
    return _dumps(obj, **kw)


json.dump = dump
json.dumps = dumps


@atexit.register
def _tulis_jejak():
    jalur = os.environ.get("AB95_JEJAK_KONVERSI")
    if not jalur:
        return
    try:
        induk = os.path.dirname(jalur)
        if induk:
            os.makedirs(induk, exist_ok=True)
        with open(jalur, "w", encoding="utf-8") as fh:
            _dump({"konversi_tipe": dict(_hitung)}, fh, indent=1)
    except Exception as e:  # pragma: no cover
        print("gagal tulis jejak konversi:", e, file=sys.stderr)


AB95 = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
if not os.path.exists(AB95):
    raise SystemExit("runner tidak ditemukan: " + AB95)
sys.argv = [AB95] + sys.argv[1:]
runpy.run_path(AB95, run_name="__main__")
