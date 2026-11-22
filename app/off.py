"""Klien Open Food Facts. Hanya mengubah data mereka ke bentuk produk CekJajan."""
import logging

import httpx

log = logging.getLogger("cekjajan.off")

URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
FIELDS = "product_name,brands,categories_tags,serving_quantity,serving_size,nutriments"
HEADERS = {"User-Agent": "CekJajan-MandaBita/0.2 (tugas kuliah ITB; kontak lewat repositori GitHub)"}


def _angka(nilai):
    try:
        return float(nilai)
    except (TypeError, ValueError):
        return None


def map_product(data: dict) -> dict | None:
    """Mengembalikan produk per sajian, atau None bila data gizinya tidak lengkap."""
    nut = data.get("nutriments") or {}
    gula100 = _angka(nut.get("sugars_100g"))
    lemak100 = _angka(nut.get("fat_100g"))
    natrium_g100 = _angka(nut.get("sodium_100g"))
    if natrium_g100 is None:
        garam100 = _angka(nut.get("salt_100g"))
        natrium_g100 = None if garam100 is None else garam100 / 2.5
    if gula100 is None or lemak100 is None or natrium_g100 is None:
        return None
    natrium_mg100 = natrium_g100 * 1000

    tags = data.get("categories_tags") or []
    minuman = any("beverage" in t for t in tags)
    ukuran = (data.get("serving_size") or "").lower()
    satuan = "ml" if (minuman or "ml" in ukuran) else "g"
    takaran = _angka(data.get("serving_quantity"))
    if not takaran or takaran <= 0:
        takaran = 100.0
    f = takaran / 100.0

    merek = (data.get("brands") or "").split(",")[0].strip() or None
    return {
        "nama": (data.get("product_name") or "").strip() or "Produk tanpa nama",
        "merek": merek,
        "kategori": "minuman" if minuman else "makanan",
        "takaran_saji": takaran,
        "satuan_takaran": satuan,
        "sajian_per_kemasan": None,
        "gula_g": round(gula100 * f, 4),
        "natrium_mg": round(natrium_mg100 * f, 4),
        "lemak_g": round(lemak100 * f, 4),
    }


def fetch_product(barcode: str) -> dict | None:
    """Mencari barcode di Open Food Facts. None bila tidak ada, data tidak lengkap, atau layanan tidak terjangkau."""
    try:
        r = httpx.get(
            URL.format(barcode=barcode), params={"fields": FIELDS}, headers=HEADERS, timeout=6.0, follow_redirects=True
        )
        if r.status_code != 200:
            return None
        payload = r.json()
        if payload.get("status") != 1:
            return None
        return map_product(payload.get("product") or {})
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Open Food Facts tidak terjangkau: %s", e)
        return None
