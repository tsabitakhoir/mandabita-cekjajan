"""Jatah GGL harian anak dan catatan konsumsi."""
from datetime import date, datetime, time, timedelta, timezone

WIB = timezone(timedelta(hours=7))

# Usia -> batas harian. Rujukan: Permenkes 30/2013 dan Permenkes 28/2019 (lihat openapi.yaml).
_BATAS = [
    (4, 6, {"gula_g": 35.0, "garam_g": 2.25, "lemak_g": 50.0}),
    (7, 9, {"gula_g": 41.0, "garam_g": 2.5, "lemak_g": 55.0}),
    (10, 12, {"gula_g": 47.5, "garam_g": 3.25, "lemak_g": 65.0}),
]
_NAMA_ZAT = {"gula_g": "gula", "garam_g": "garam", "lemak_g": "lemak"}


def limits_for_age(usia: int) -> dict:
    for awal, akhir, batas in _BATAS:
        if awal <= usia <= akhir:
            return dict(batas)
    raise ValueError("Usia di luar 4 sampai 12 tahun.")


def today_wib() -> date:
    return datetime.now(WIB).date()


def utc_str(dt: datetime) -> str:
    """datetime -> 'YYYY-MM-DDTHH:MM:SSZ'. Tanpa zona waktu dianggap UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wib_date_of(utc_text: str) -> date:
    dt = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB).date()


def day_bounds_utc(d: date) -> tuple:
    awal = datetime.combine(d, time.min, tzinfo=WIB)
    return utc_str(awal), utc_str(awal + timedelta(days=1))


def consumption_dict(row) -> dict:
    return {
        "id": row["id"],
        "child_id": row["child_id"],
        "product_id": row["product_id"],
        "jumlah_sajian": row["jumlah_sajian"],
        "waktu_konsumsi": row["waktu_konsumsi"],
        "ggl": {"gula_g": row["gula_g"], "garam_g": row["garam_g"], "lemak_g": row["lemak_g"]},
    }


def consumptions_on(db, child_id: str, d: date) -> list:
    awal, akhir = day_bounds_utc(d)
    return db.execute(
        "SELECT * FROM consumptions WHERE child_id = ? AND waktu_konsumsi >= ? AND waktu_konsumsi < ? "
        "ORDER BY waktu_konsumsi, id",
        (child_id, awal, akhir),
    ).fetchall()


def status_and_warning(persen_mentah: dict) -> tuple:
    tertinggi = max(persen_mentah.values())
    lewat = [_NAMA_ZAT[k] for k, v in persen_mentah.items() if v >= 100]
    if tertinggi >= 100:
        return "terlampaui", f"Jatah {', '.join(lewat)} hari ini sudah terlampaui."
    if tertinggi >= 80:
        dekat = [_NAMA_ZAT[k] for k, v in persen_mentah.items() if v >= 80]
        return "hampir_habis", f"Jatah {', '.join(dekat)} hari ini hampir habis."
    return "aman", None


def build_quota(db, child, d: date) -> dict:
    batas = limits_for_age(child["usia_tahun"])
    rows = consumptions_on(db, child["id"], d)
    terpakai = {
        "gula_g": round(sum(r["gula_g"] for r in rows), 4),
        "garam_g": round(sum(r["garam_g"] for r in rows), 4),
        "lemak_g": round(sum(r["lemak_g"] for r in rows), 4),
    }
    mentah = {k: terpakai[k] / batas[k] * 100 for k in batas}
    status, peringatan = status_and_warning(mentah)
    return {
        "child_id": child["id"],
        "tanggal": d.isoformat(),
        "batas": batas,
        "terpakai": terpakai,
        "persen_terpakai": {k: round(v, 1) for k, v in mentah.items()},
        "status": status,
        "peringatan": peringatan,
        "alternatif": [],
    }
