from app import off
from conftest import BISKUIT, TEH, daftar_dan_login


def tambah(client, auth, produk):
    r = client.post("/api/products", json=produk, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_produk_butuh_autentikasi(client):
    assert client.get("/api/products/8999999000000").status_code == 401
    assert client.post("/api/products", json=BISKUIT).status_code == 401


def test_tambah_dan_cari_produk(client, auth):
    p = tambah(client, auth, BISKUIT)
    assert p["sumber"] == "manual" and p["status_verifikasi"] == "belum_terverifikasi"
    assert p["id"].startswith("prod-")
    r = client.get("/api/products/8999999000000", headers=auth)
    assert r.status_code == 200 and r.json()["id"] == p["id"]
    assert r.json()["nutrisi"]["sajian_per_kemasan"] == 3


def test_cari_produk_dengan_api_key(client, api_key_headers, auth):
    tambah(client, auth, BISKUIT)
    r = client.get("/api/products/8999999000000", headers=api_key_headers)
    assert r.status_code == 200


def test_api_key_salah(client):
    r = client.get("/api/products/8999999000000", headers={"X-API-Key": "kunci-yang-salah-sekali"})
    assert r.status_code == 401


def test_api_key_tidak_boleh_menulis_produk(client, api_key_headers):
    assert client.post("/api/products", json=BISKUIT, headers=api_key_headers).status_code == 401


def test_barcode_ganda_ditolak(client, auth):
    tambah(client, auth, BISKUIT)
    r = client.post("/api/products", json=BISKUIT, headers=auth)
    assert r.status_code == 400


def test_barcode_format_salah(client, auth):
    assert client.get("/api/products/abc", headers=auth).status_code == 400
    assert client.post("/api/products", json={**BISKUIT, "barcode": "123"}, headers=auth).status_code == 400


def test_produk_tidak_ditemukan(client, auth, monkeypatch):
    monkeypatch.setattr(off, "fetch_product", lambda barcode: None)
    r = client.get("/api/products/8991111111111", headers=auth)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_open_food_facts_disimpan_ke_katalog(client, auth, monkeypatch):
    panggilan = []

    def palsu(barcode):
        panggilan.append(barcode)
        return {"nama": "Susu Uji", "merek": "Merek", "kategori": "minuman", "takaran_saji": 200.0,
                "satuan_takaran": "ml", "sajian_per_kemasan": None, "gula_g": 9.0, "natrium_mg": 80.0, "lemak_g": 3.0}

    monkeypatch.setattr(off, "fetch_product", palsu)
    r = client.get("/api/products/8992222222222", headers=auth)
    assert r.status_code == 200
    assert r.json()["sumber"] == "open_food_facts"
    assert r.json()["status_verifikasi"] == "belum_terverifikasi"
    # pencarian kedua dilayani katalog, tidak memanggil Open Food Facts lagi
    assert client.get("/api/products/8992222222222", headers=auth).status_code == 200
    assert panggilan == ["8992222222222"]


def test_pemetaan_open_food_facts():
    data = {
        "product_name": "Biskuit OFF", "brands": "Merek A, Merek B", "categories_tags": ["en:biscuits"],
        "serving_quantity": "30", "serving_size": "30 g",
        "nutriments": {"sugars_100g": 20, "fat_100g": 23.3, "sodium_100g": 0.3667},
    }
    p = off.map_product(data)
    assert p["merek"] == "Merek A" and p["kategori"] == "makanan" and p["satuan_takaran"] == "g"
    assert p["takaran_saji"] == 30 and p["gula_g"] == 6 and p["lemak_g"] == 6.99
    assert round(p["natrium_mg"], 1) == 110.0


def test_pemetaan_open_food_facts_garam_dan_minuman():
    data = {"product_name": "Teh", "categories_tags": ["en:beverages"],
            "nutriments": {"sugars_100g": 7.5, "fat_100g": 0, "salt_100g": 0.0375}}
    p = off.map_product(data)
    assert p["kategori"] == "minuman" and p["satuan_takaran"] == "ml" and p["takaran_saji"] == 100
    assert round(p["natrium_mg"], 3) == 15.0


def test_pemetaan_open_food_facts_tidak_lengkap():
    assert off.map_product({"nutriments": {"sugars_100g": 5}}) is None


def test_penilaian_dari_nilai_gizi(client, api_key_headers):
    body = {"nutrisi": TEH["nutrisi"], "jumlah_sajian": 1}
    r = client.post("/api/assessments", json=body, headers=api_key_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["sumber_data"] == "input_langsung" and j["nutri_level"] == "C"
    assert j["dampak_jatah_harian"] is None


def test_penilaian_dari_barcode(client, auth):
    tambah(client, auth, BISKUIT)
    r = client.post("/api/assessments", json={"barcode": BISKUIT["barcode"]}, headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert j["sumber_data"] == "manual" and j["produk"]["nama"] == "Biskuit Contoh"
    assert j["nutri_level"] == "D" and j["ggl_per_sajian"]["garam_g"] == 0.275


def test_penilaian_harus_salah_satu(client, auth):
    r = client.post("/api/assessments", json={}, headers=auth)
    assert r.status_code == 400
    assert "salah satu" in r.json()["error"]["message"]
    both = {"barcode": BISKUIT["barcode"], "nutrisi": BISKUIT["nutrisi"]}
    assert client.post("/api/assessments", json=both, headers=auth).status_code == 400


def test_penilaian_butuh_autentikasi(client):
    assert client.post("/api/assessments", json={"nutrisi": TEH["nutrisi"]}).status_code == 401


def test_penilaian_dampak_jatah_harian(client, auth):
    tambah(client, auth, BISKUIT)
    anak = client.post("/api/children", json={"nama_panggilan": "Anak Uji", "usia_tahun": 8}, headers=auth).json()
    r = client.post("/api/assessments", json={"barcode": BISKUIT["barcode"], "child_id": anak["id"]}, headers=auth)
    assert r.json()["dampak_jatah_harian"] == {"gula_g": 14.6, "garam_g": 11.0, "lemak_g": 12.7}
    r = client.post("/api/assessments", json={"barcode": BISKUIT["barcode"], "child_id": anak["id"],
                                              "jumlah_sajian": 2}, headers=auth)
    assert r.json()["dampak_jatah_harian"]["gula_g"] == 29.3


def test_api_key_tidak_boleh_kirim_child_id(client, api_key_headers):
    body = {"nutrisi": TEH["nutrisi"], "child_id": "child-apa-saja"}
    r = client.post("/api/assessments", json=body, headers=api_key_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_penilaian_anak_milik_orang_lain(client, auth):
    anak = client.post("/api/children", json={"nama_panggilan": "Anak A", "usia_tahun": 6}, headers=auth).json()
    lain = daftar_dan_login(client, email="lain@example.com")
    r = client.post("/api/assessments", json={"nutrisi": TEH["nutrisi"], "child_id": anak["id"]}, headers=lain)
    assert r.status_code == 403
    r = client.post("/api/assessments", json={"nutrisi": TEH["nutrisi"], "child_id": "child-tidak-ada"}, headers=lain)
    assert r.status_code == 404
