"""Pengaturan dari environment. Dibaca saat dipakai agar mudah diuji."""
import os


def db_path() -> str:
    return os.environ.get("DB_PATH", "/data/cekjajan.db")


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32 or secret.upper().startswith("GANTI"):
        raise RuntimeError(
            "JWT_SECRET belum diatur. Isi dengan string acak minimal 32 karakter di file .env "
            "(bash deploy.sh membuatnya otomatis)."
        )
    return secret


def api_keys() -> dict:
    """API_KEYS berbentuk 'ahay:kunci1,aisyahjeko:kunci2'. Mengembalikan {kunci: nama_kelompok}."""
    hasil = {}
    for pasangan in os.environ.get("API_KEYS", "").split(","):
        pasangan = pasangan.strip()
        if not pasangan:
            continue
        nama, sep, kunci = pasangan.partition(":")
        if not sep:
            nama, kunci = "klien", pasangan
        if len(kunci) >= 16:
            hasil[kunci] = nama
    return hasil
