QUICK = "/api/assessments/quick"
PARAM = {"takaran_saji": 30, "satuan_takaran": "g", "gula_g": 6, "natrium_mg": 110, "lemak_g": 7}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "cekjajan", "version": "0.2.0"}


def test_quick_biskuit(client):
    r = client.get(QUICK, params=PARAM)
    assert r.status_code == 200
    body = r.json()
    assert body["sumber_data"] == "input_langsung"
    assert body["produk"] is None
    assert body["dampak_jatah_harian"] is None
    assert body["nutri_level"] == "D"
    assert body["penanda"]["ikon"] == "batasi"
    assert set(body["penanda_zat"]) == {"gula", "garam", "lemak"}
    assert "disclaimer" in body and body["dinilai_pada"].endswith("Z")


def test_quick_minuman_manis(client):
    r = client.get(QUICK, params={"takaran_saji": 200, "satuan_takaran": "ml",
                                  "gula_g": 15, "natrium_mg": 30, "lemak_g": 0})
    assert r.json()["nutri_level"] == "C"


def test_quick_parameter_kurang(client):
    p = {k: v for k, v in PARAM.items() if k != "gula_g"}
    r = client.get(QUICK, params=p)
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "bad_request"
    assert "gula_g" in err["message"]


def test_quick_nilai_negatif(client):
    r = client.get(QUICK, params={**PARAM, "gula_g": -1})
    assert r.status_code == 400
    assert "gula_g" in r.json()["error"]["message"]


def test_quick_satuan_salah(client):
    assert client.get(QUICK, params={**PARAM, "satuan_takaran": "kg"}).status_code == 400


def test_path_tidak_ada_memakai_format_error(client):
    r = client.get("/api/tidak-ada")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_dokumentasi_dan_kontrak(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200
    r = client.get("/api/openapi.yaml")
    assert r.status_code == 200
    assert "openapi: 3.0.3" in r.text
