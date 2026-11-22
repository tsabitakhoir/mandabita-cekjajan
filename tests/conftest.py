import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.main import app

API_KEY = "kunci-uji-ahay-1234567890"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "uji.db"))
    monkeypatch.setenv("JWT_SECRET", "rahasia-uji-" + "x" * 32)
    monkeypatch.setenv("API_KEYS", f"ahay:{API_KEY}")
    dbmod._siap.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api_key_headers():
    return {"X-API-Key": API_KEY}


def daftar_dan_login(client, email="ortu.uji@example.com", password="PasswordContoh123"):
    r = client.post("/api/auth/register", json={"nama": "Orang Tua Uji", "email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def auth(client):
    return daftar_dan_login(client)


BISKUIT = {
    "barcode": "8999999000000",
    "nama": "Biskuit Contoh",
    "merek": "Merek Contoh",
    "kategori": "makanan",
    "nutrisi": {"takaran_saji": 30, "satuan_takaran": "g", "sajian_per_kemasan": 3,
                "gula_g": 6, "natrium_mg": 110, "lemak_g": 7},
}
TEH = {
    "barcode": "8999999000017",
    "nama": "Teh Manis Kemasan Contoh",
    "kategori": "minuman",
    "nutrisi": {"takaran_saji": 200, "satuan_takaran": "ml", "gula_g": 15, "natrium_mg": 30, "lemak_g": 0},
}
