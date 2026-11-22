import pytest

from app import quota
from conftest import BISKUIT, TEH, daftar_dan_login


def buat_anak(client, auth, usia=8, nama="Anak Uji"):
    r = client.post("/api/children", json={"nama_panggilan": nama, "usia_tahun": usia}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def buat_produk(client, auth, produk):
    return client.post("/api/products", json=produk, headers=auth).json()


@pytest.mark.parametrize("usia,batas", [
    (4, (35, 2.25, 50)), (6, (35, 2.25, 50)), (7, (41, 2.5, 55)), (9, (41, 2.5, 55)),
    (10, (47.5, 3.25, 65)), (12, (47.5, 3.25, 65)),
])
def test_batas_menurut_usia(usia, batas):
    assert quota.limits_for_age(usia) == {"gula_g": batas[0], "garam_g": batas[1], "lemak_g": batas[2]}


def test_status_dan_peringatan():
    assert quota.status_and_warning({"gula_g": 10, "garam_g": 79.9, "lemak_g": 0})[0] == "aman"
    assert quota.status_and_warning({"gula_g": 10, "garam_g": 80, "lemak_g": 0})[0] == "hampir_habis"
    assert quota.status_and_warning({"gula_g": 99.9, "garam_g": 0, "lemak_g": 0})[0] == "hampir_habis"
    status, pesan = quota.status_and_warning({"gula_g": 100, "garam_g": 0, "lemak_g": 120})
    assert status == "terlampaui" and "gula" in pesan and "lemak" in pesan


def test_batas_hari_memakai_wib():
    awal, akhir = quota.day_bounds_utc(__import__("datetime").date(2026, 11, 23))
    assert awal == "2026-11-22T17:00:00Z" and akhir == "2026-11-23T17:00:00Z"
    assert str(quota.wib_date_of("2026-11-22T17:30:00Z")) == "2026-11-23"


def test_anak_butuh_login(client):
    assert client.get("/api/children").status_code == 401
    assert client.post("/api/children", json={"nama_panggilan": "A", "usia_tahun": 8}).status_code == 401


def test_buat_dan_lihat_anak(client, auth):
    anak = buat_anak(client, auth)
    assert anak["id"].startswith("child-") and anak["usia_tahun"] == 8
    assert client.get(f"/api/children/{anak['id']}", headers=auth).json() == anak
    assert client.get("/api/children", headers=auth).json() == {"items": [anak]}


@pytest.mark.parametrize("usia", [3, 13, 0, -1])
def test_usia_di_luar_rentang(client, auth, usia):
    r = client.post("/api/children", json={"nama_panggilan": "A", "usia_tahun": usia}, headers=auth)
    assert r.status_code == 400
    assert "usia_tahun" in r.json()["error"]["message"]


def test_anak_orang_lain_403_dan_tidak_ada_404(client, auth):
    anak = buat_anak(client, auth)
    lain = daftar_dan_login(client, email="lain@example.com")
    assert client.get(f"/api/children/{anak['id']}", headers=lain).status_code == 403
    assert client.get(f"/api/children/{anak['id']}/daily-quota", headers=lain).status_code == 403
    assert client.get(f"/api/children/{anak['id']}/consumptions", headers=lain).status_code == 403
    assert client.get("/api/children/child-tidak-ada", headers=lain).status_code == 404
    assert client.get("/api/children", headers=lain).json() == {"items": []}


def test_jatah_kosong(client, auth):
    anak = buat_anak(client, auth)
    r = client.get(f"/api/children/{anak['id']}/daily-quota", params={"date": "2026-11-23"}, headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert j["batas"] == {"gula_g": 41.0, "garam_g": 2.5, "lemak_g": 55.0}
    assert j["terpakai"] == {"gula_g": 0, "garam_g": 0, "lemak_g": 0}
    assert j["status"] == "aman" and j["peringatan"] is None and j["alternatif"] == []
    assert j["tanggal"] == "2026-11-23"


def test_catat_konsumsi_memperbarui_jatah(client, auth):
    anak = buat_anak(client, auth)
    biskuit = buat_produk(client, auth, BISKUIT)
    teh = buat_produk(client, auth, TEH)
    url = f"/api/children/{anak['id']}/consumptions"

    r = client.post(url, json={"product_id": biskuit["id"], "waktu_konsumsi": "2026-11-23T03:30:00Z"}, headers=auth)
    assert r.status_code == 201
    assert r.json()["konsumsi"]["ggl"] == {"gula_g": 6.0, "garam_g": 0.275, "lemak_g": 7.0}

    r = client.post(url, json={"product_id": teh["id"], "waktu_konsumsi": "2026-11-23T05:10:00Z"}, headers=auth)
    jatah = r.json()["jatah_terbaru"]
    assert jatah["tanggal"] == "2026-11-23"
    assert jatah["terpakai"] == {"gula_g": 21.0, "garam_g": 0.35, "lemak_g": 7.0}
    assert jatah["persen_terpakai"] == {"gula_g": 51.2, "garam_g": 14.0, "lemak_g": 12.7}
    assert jatah["status"] == "aman"

    riwayat = client.get(url, params={"date": "2026-11-23"}, headers=auth).json()["items"]
    assert [x["product_id"] for x in riwayat] == [biskuit["id"], teh["id"]]
    assert client.get(url, params={"date": "2026-11-24"}, headers=auth).json() == {"items": []}


def test_konsumsi_menjelang_tengah_malam_wib_masuk_hari_wib(client, auth):
    anak = buat_anak(client, auth)
    teh = buat_produk(client, auth, TEH)
    url = f"/api/children/{anak['id']}/consumptions"
    # 16:30 UTC = 23:30 WIB tanggal 23; 17:30 UTC = 00:30 WIB tanggal 24
    client.post(url, json={"product_id": teh["id"], "waktu_konsumsi": "2026-11-23T16:30:00Z"}, headers=auth)
    client.post(url, json={"product_id": teh["id"], "waktu_konsumsi": "2026-11-23T17:30:00Z"}, headers=auth)
    assert len(client.get(url, params={"date": "2026-11-23"}, headers=auth).json()["items"]) == 1
    assert len(client.get(url, params={"date": "2026-11-24"}, headers=auth).json()["items"]) == 1


def test_status_hampir_habis_dan_terlampaui(client, auth):
    anak = buat_anak(client, auth, usia=8)  # batas gula 41 g
    teh = buat_produk(client, auth, TEH)          # 15 g gula per sajian
    biskuit = buat_produk(client, auth, BISKUIT)  # 6 g gula per sajian
    url = f"/api/children/{anak['id']}/consumptions"
    waktu = "2026-11-23T03:00:00Z"

    r = client.post(url, json={"product_id": teh["id"], "jumlah_sajian": 2, "waktu_konsumsi": waktu}, headers=auth)
    assert r.json()["jatah_terbaru"]["status"] == "aman"  # 30 g = 73,2%

    r = client.post(url, json={"product_id": biskuit["id"], "waktu_konsumsi": waktu}, headers=auth)
    j = r.json()["jatah_terbaru"]  # 36 g = 87,8%
    assert j["status"] == "hampir_habis" and "gula" in j["peringatan"]

    r = client.post(url, json={"product_id": teh["id"], "waktu_konsumsi": waktu}, headers=auth)
    j = r.json()["jatah_terbaru"]  # 51 g = 124,4%
    assert j["status"] == "terlampaui" and j["persen_terpakai"]["gula_g"] == 124.4
    assert "gula" in j["peringatan"]


def test_konsumsi_produk_tidak_ada_atau_anak_orang_lain(client, auth):
    anak = buat_anak(client, auth)
    url = f"/api/children/{anak['id']}/consumptions"
    assert client.post(url, json={"product_id": "prod-tidak-ada"}, headers=auth).status_code == 404
    teh = buat_produk(client, auth, TEH)
    lain = daftar_dan_login(client, email="lain@example.com")
    assert client.post(url, json={"product_id": teh["id"]}, headers=lain).status_code == 403
    assert client.post(url, json={}, headers=auth).status_code == 400
    assert client.post(url, json={"product_id": teh["id"], "jumlah_sajian": 0}, headers=auth).status_code == 400


def test_tanggal_tidak_valid(client, auth):
    anak = buat_anak(client, auth)
    r = client.get(f"/api/children/{anak['id']}/daily-quota", params={"date": "bukan-tanggal"}, headers=auth)
    assert r.status_code == 400
