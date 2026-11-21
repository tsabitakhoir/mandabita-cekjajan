from app import scoring
from app.scoring import Nutrisi


def test_minuman_tawar_level_a():
    hasil = scoring.nilai(Nutrisi(200, "ml", 0, 5, 0))
    assert hasil["nutri_level"] == "A"
    assert hasil["penanda"]["ikon"] == "sangat_baik"
    assert hasil["ggl_per_sajian"]["garam_g"] == 0.0125


def test_minuman_manis_level_c():
    hasil = scoring.nilai(Nutrisi(200, "ml", 15, 30, 0))
    assert hasil["nutri_level"] == "C"
    assert hasil["penanda_zat"]["gula"]["level"] == "C"
    assert hasil["penanda_zat"]["garam"]["level"] == "B"
    assert hasil["penanda_zat"]["lemak"]["level"] == "A"


def test_biskuit_level_d():
    hasil = scoring.nilai(Nutrisi(30, "g", 6, 110, 7))
    assert hasil["nutri_level"] == "D"
    assert hasil["penanda"]["skala"] == 4
    assert hasil["penanda_zat"]["garam"]["level"] == "C"
    assert hasil["ggl_per_sajian"] == {"gula_g": 6, "garam_g": 0.275, "lemak_g": 7}
    assert "Perkiraan" in hasil["ringkasan"]


def test_batas_gula_per_100ml():
    def lv(gula):
        return scoring.level_per_zat(Nutrisi(100, "ml", gula, 0, 0))["gula"]

    assert lv(0.49) == "A"
    assert lv(0.5) == "B"
    assert lv(5.99) == "B"
    assert lv(6) == "C"
    assert lv(12.5) == "C"
    assert lv(12.51) == "D"


def test_level_keseluruhan_ikut_zat_terburuk():
    assert scoring.level_keseluruhan({"gula": "A", "garam": "B", "lemak": "D"}) == "D"
    assert scoring.level_keseluruhan({"gula": "A", "garam": "A", "lemak": "A"}) == "A"


def test_ambang_dihitung_per_100_bukan_per_sajian():
    # 6 g gula per 30 g = 20 g per 100 g -> D, walau 6 g per sajian kelihatan kecil
    assert scoring.level_per_zat(Nutrisi(30, "g", 6, 0, 0))["gula"] == "D"
