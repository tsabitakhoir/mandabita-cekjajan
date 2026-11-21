from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUICK = "/api/assessments/quick"


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "cekjajan", "version": "0.2.0"}


def test_quick_biskuit():
    r = client.get(QUICK, params={"takaran_saji": 30, "satuan_takaran": "g",
                                  "gula_g": 6, "natrium_mg": 110, "lemak_g": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["sumber_data"] == "input_langsung"
    assert body["produk"] is None
    assert body["dampak_jatah_harian"] is None
    assert body["nutri_level"] == "D"
    assert body["penanda"]["ikon"] == "batasi"
    assert set(body["penanda_zat"]) == {"gula", "garam", "lemak"}
    assert "disclaimer" in body and body["dinilai_pada"].endswith("Z")


def test_quick_minuman_manis():
    r = client.get(QUICK, params={"takaran_saji": 200, "satuan_takaran": "ml",
                                  "gula_g": 15, "natrium_mg": 30, "lemak_g": 0})
    assert r.json()["nutri_level"] == "C"


def test_quick_parameter_kurang():
    r = client.get(QUICK, params={"takaran_saji": 30, "satuan_takaran": "g",
                                  "natrium_mg": 110, "lemak_g": 7})
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "bad_request"
    assert "gula_g" in err["message"]


def test_quick_nilai_negatif():
    r = client.get(QUICK, params={"takaran_saji": 30, "satuan_takaran": "g",
                                  "gula_g": -1, "natrium_mg": 110, "lemak_g": 7})
    assert r.status_code == 400
    assert "gula_g" in r.json()["error"]["message"]


def test_quick_satuan_salah():
    r = client.get(QUICK, params={"takaran_saji": 30, "satuan_takaran": "kg",
                                  "gula_g": 1, "natrium_mg": 1, "lemak_g": 1})
    assert r.status_code == 400


def test_dokumentasi_swagger_ada():
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200
