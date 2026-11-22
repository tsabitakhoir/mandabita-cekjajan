import time

import jwt

from conftest import daftar_dan_login

REG = {"nama": "Orang Tua Uji", "email": "ortu.uji@example.com", "password": "PasswordContoh123"}


def test_register_dan_login(client):
    r = client.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    user = r.json()
    assert user["role"] == "orang_tua" and user["email"] == "ortu.uji@example.com"
    assert "password" not in user and "password_hash" not in user

    r = client.post("/api/auth/login", json={"email": REG["email"], "password": REG["password"]})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 86400
    assert body["user"]["id"] == user["id"]


def test_login_email_tidak_membedakan_huruf_besar(client):
    client.post("/api/auth/register", json=REG)
    r = client.post("/api/auth/login", json={"email": "ORTU.Uji@Example.com", "password": REG["password"]})
    assert r.status_code == 200


def test_register_password_terlalu_pendek(client):
    r = client.post("/api/auth/register", json={**REG, "password": "pendek"})
    assert r.status_code == 400
    assert "password" in r.json()["error"]["message"]


def test_register_email_tidak_valid(client):
    assert client.post("/api/auth/register", json={**REG, "email": "bukan-email"}).status_code == 400


def test_register_email_ganda(client):
    client.post("/api/auth/register", json=REG)
    r = client.post("/api/auth/register", json={**REG, "email": REG["email"].upper()})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


def test_login_salah(client):
    client.post("/api/auth/register", json=REG)
    r = client.post("/api/auth/login", json={"email": REG["email"], "password": "salah-salah-salah"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    r = client.post("/api/auth/login", json={"email": "tidak.ada@example.com", "password": "apa-saja-123456"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Email atau password salah."


def test_me(client, auth):
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["email"] == "ortu.uji@example.com"


def test_me_tanpa_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_token_rusak_atau_salah_kunci(client, auth):
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    palsu = jwt.encode({"sub": "usr-x", "exp": int(time.time()) + 60}, "kunci-lain-" + "y" * 32, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + palsu}).status_code == 401


def test_token_kedaluwarsa(client, monkeypatch):
    headers = daftar_dan_login(client)
    token = headers["Authorization"].split()[1]
    sub = jwt.decode(token, options={"verify_signature": False})["sub"]
    lama = jwt.encode({"sub": sub, "exp": int(time.time()) - 10}, "rahasia-uji-" + "x" * 32, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer " + lama})
    assert r.status_code == 401
    assert "kedaluwarsa" in r.json()["error"]["message"]


def test_token_tanpa_algoritma_none_ditolak(client):
    palsu = jwt.encode({"sub": "usr-x", "exp": int(time.time()) + 60}, key=None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + palsu}).status_code == 401
