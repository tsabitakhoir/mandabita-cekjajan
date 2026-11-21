"""Logika penilaian gizi CekJajan.

Rujukan: PerBPOM 10/2026 (Nutri-Level, per 100 g/ml) untuk ambang A sampai D.
Aturan resmi hanya mencakup minuman. Untuk makanan padat ambang yang sama dipakai
per 100 g sebagai perkiraan.
"""
from dataclasses import dataclass

NATRIUM_KE_GARAM = 2.5 / 1000  # garam (g) = natrium (mg) x 2,5 / 1000

# (batas atas A, batas atas B, batas atas C). Nilai di atas batas C masuk level D.
# A dan B memakai "kurang dari", C memakai "sampai dengan".
_AMBANG = {
    "gula": (0.5, 6.0, 12.5),       # g per 100 g/ml
    "natrium": (5.0, 120.0, 500.0),  # mg per 100 g/ml
    "lemak": (0.5, 3.0, 17.0),       # g per 100 g/ml
}

LEVELS = ("A", "B", "C", "D")

PENANDA = {
    "A": {"level": "A", "skala": 1, "ikon": "sangat_baik", "label": "Sangat baik", "warna": "hijau_tua"},
    "B": {"level": "B", "skala": 2, "ikon": "baik", "label": "Baik", "warna": "hijau_muda"},
    "C": {"level": "C", "skala": 3, "ikon": "hati_hati", "label": "Hati-hati", "warna": "kuning"},
    "D": {"level": "D", "skala": 4, "ikon": "batasi", "label": "Batasi", "warna": "merah"},
}

_KATA = {"A": "sangat rendah", "B": "rendah", "C": "sedang", "D": "tinggi"}

_SARAN = {
    "A": "Pilihan yang baik.",
    "B": "Pilihan yang cukup baik.",
    "C": "Konsumsi dengan bijak dan pertimbangkan alternatif yang lebih rendah.",
    "D": "Sebaiknya dibatasi.",
}


@dataclass(frozen=True)
class Nutrisi:
    takaran_saji: float
    satuan_takaran: str  # "g" atau "ml"
    gula_g: float
    natrium_mg: float
    lemak_g: float


def _level(nilai: float, zat: str) -> str:
    a, b, c = _AMBANG[zat]
    if nilai < a:
        return "A"
    if nilai < b:
        return "B"
    if nilai <= c:
        return "C"
    return "D"


def level_per_zat(n: Nutrisi) -> dict:
    """Level A-D untuk gula, garam (dari natrium), dan lemak, dihitung per 100 g/ml."""
    faktor = 100.0 / n.takaran_saji
    return {
        "gula": _level(n.gula_g * faktor, "gula"),
        "garam": _level(n.natrium_mg * faktor, "natrium"),
        "lemak": _level(n.lemak_g * faktor, "lemak"),
    }


def level_keseluruhan(per_zat: dict) -> str:
    """Level terburuk dari ketiga zat."""
    return max(per_zat.values(), key=LEVELS.index)


def ggl_per_sajian(n: Nutrisi, jumlah_sajian: float = 1.0) -> dict:
    return {
        "gula_g": round(n.gula_g * jumlah_sajian, 4),
        "garam_g": round(n.natrium_mg * jumlah_sajian * NATRIUM_KE_GARAM, 4),
        "lemak_g": round(n.lemak_g * jumlah_sajian, 4),
    }


def ringkasan(per_zat: dict, keseluruhan: str, satuan: str) -> str:
    teks = (
        f"Gula {_KATA[per_zat['gula']]}, garam {_KATA[per_zat['garam']]}, "
        f"lemak {_KATA[per_zat['lemak']]}. {_SARAN[keseluruhan]}"
    )
    if satuan == "g":
        teks += " Perkiraan: ambang resmi BPOM berlaku untuk minuman."
    return teks


def nilai(n: Nutrisi) -> dict:
    """Hasil penilaian lengkap untuk satu sajian."""
    per_zat = level_per_zat(n)
    total = level_keseluruhan(per_zat)
    return {
        "ggl_per_sajian": ggl_per_sajian(n),
        "nutri_level": total,
        "penanda": PENANDA[total],
        "penanda_zat": {zat: PENANDA[lv] for zat, lv in per_zat.items()},
        "ringkasan": ringkasan(per_zat, total, n.satuan_takaran),
    }
