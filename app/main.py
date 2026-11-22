import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Path as PathParam, Query
from fastapi.responses import FileResponse

from . import config, off, quota, scoring
from .db import get_db, new_id
from .errors import ApiError, register_handlers
from .schemas import (
    AssessmentRequest,
    ChildInput,
    ConsumptionInput,
    LoginRequest,
    ProductInput,
    RegisterRequest,
)
from .security import (
    TOKEN_TTL,
    Principal,
    hash_password,
    make_token,
    require_user,
    require_user_or_key,
    verify_dummy,
    verify_password,
)

VERSION = "0.2.0"
DISCLAIMER = "Hasil berupa perkiraan, bukan diagnosis atau pengganti saran tenaga kesehatan."
BARCODE_RE = r"^[0-9]{8,14}$"
OPENAPI_FILE = Path(__file__).resolve().parent.parent / "openapi.yaml"

log = logging.getLogger("cekjajan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.jwt_secret()  # gagal lebih awal bila belum diatur
    yield


app = FastAPI(
    title="CekJajan Service API",
    version=VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)
register_handlers(app)
api = APIRouter(prefix="/api")


# ---------- pembantu ----------

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def user_dict(row) -> dict:
    return {"id": row["id"], "nama": row["nama"], "email": row["email"], "role": row["role"]}


def child_dict(row) -> dict:
    return {"id": row["id"], "nama_panggilan": row["nama_panggilan"], "usia_tahun": row["usia_tahun"]}


def product_dict(row) -> dict:
    nutrisi = {
        "takaran_saji": row["takaran_saji"],
        "satuan_takaran": row["satuan_takaran"],
        "gula_g": row["gula_g"],
        "natrium_mg": row["natrium_mg"],
        "lemak_g": row["lemak_g"],
    }
    if row["sajian_per_kemasan"] is not None:
        nutrisi["sajian_per_kemasan"] = row["sajian_per_kemasan"]
    return {
        "id": row["id"],
        "barcode": row["barcode"],
        "nama": row["nama"],
        "merek": row["merek"],
        "kategori": row["kategori"],
        "nutrisi": nutrisi,
        "sumber": row["sumber"],
        "status_verifikasi": row["status_verifikasi"],
    }


def nutrisi_of(row) -> scoring.Nutrisi:
    return scoring.Nutrisi(row["takaran_saji"], row["satuan_takaran"], row["gula_g"], row["natrium_mg"], row["lemak_g"])


def insert_product(db, data: dict, sumber: str, status: str):
    pid = new_id("prod")
    db.execute(
        "INSERT INTO products (id, barcode, nama, merek, kategori, takaran_saji, satuan_takaran, sajian_per_kemasan,"
        " gula_g, natrium_mg, lemak_g, sumber, status_verifikasi) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            pid, data.get("barcode"), data["nama"], data.get("merek"), data["kategori"], data["takaran_saji"],
            data["satuan_takaran"], data.get("sajian_per_kemasan"), data["gula_g"], data["natrium_mg"],
            data["lemak_g"], sumber, status,
        ),
    )
    db.commit()
    return db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()


def find_product_by_barcode(db, barcode: str):
    """Katalog CekJajan dulu, lalu Open Food Facts (hasilnya disimpan ke katalog)."""
    row = db.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()
    if row is not None:
        return row
    data = off.fetch_product(barcode)
    if data is None:
        return None
    data["barcode"] = barcode
    try:
        return insert_product(db, data, "open_food_facts", "belum_terverifikasi")
    except sqlite3.IntegrityError:  # barcode yang sama baru saja disimpan permintaan lain
        return db.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()


def get_child_for(db, child_id: str, user: dict):
    row = db.execute("SELECT * FROM children WHERE id = ?", (child_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "Profil anak tidak ditemukan.")
    if row["owner_id"] != user["id"]:
        raise ApiError(403, "forbidden", "Profil anak ini bukan milik akun Anda.")
    return row


def build_assessment(n: scoring.Nutrisi, sumber_data: str, produk, child=None, jumlah: float = 1.0) -> dict:
    hasil = scoring.nilai(n)
    dampak = None
    if child is not None:
        batas = quota.limits_for_age(child["usia_tahun"])
        ggl = scoring.ggl_per_sajian(n, jumlah)
        dampak = {k: round(ggl[k] / batas[k] * 100, 1) for k in batas}
    return {
        "sumber_data": sumber_data,
        "produk": produk,
        **hasil,
        "dampak_jatah_harian": dampak,
        "disclaimer": DISCLAIMER,
        "dinilai_pada": now_utc(),
    }


# ---------- publik ----------

@api.get("/health", tags=["Publik"], summary="Cek layanan hidup")
def health():
    return {"status": "ok", "service": "cekjajan", "version": VERSION}


@api.get("/openapi.yaml", tags=["Publik"], summary="Kontrak OpenAPI lengkap", include_in_schema=False)
def contract():
    if not OPENAPI_FILE.exists():
        raise ApiError(404, "not_found", "Berkas kontrak tidak tersedia.")
    return FileResponse(OPENAPI_FILE, media_type="application/yaml")


@api.get("/assessments/quick", tags=["Publik", "Penilaian"], summary="Penilaian cepat dari nilai gizi (tanpa login)")
def assessments_quick(
    takaran_saji: float = Query(..., ge=0.1, description="Besar satu sajian."),
    satuan_takaran: Literal["g", "ml"] = Query(..., description="Satuan takaran."),
    gula_g: float = Query(..., ge=0, description="Gula per sajian, gram."),
    natrium_mg: float = Query(..., ge=0, description="Natrium per sajian, miligram."),
    lemak_g: float = Query(..., ge=0, description="Lemak total per sajian, gram."),
):
    n = scoring.Nutrisi(takaran_saji, satuan_takaran, gula_g, natrium_mg, lemak_g)
    return build_assessment(n, "input_langsung", None)


# ---------- auth ----------

@api.post("/auth/register", status_code=201, tags=["Auth"], summary="Daftar akun orang tua")
def register(req: RegisterRequest, db=Depends(get_db)):
    uid = new_id("usr")
    try:
        db.execute(
            "INSERT INTO users (id, nama, email, password_hash, role) VALUES (?,?,?,?, 'orang_tua')",
            (uid, req.nama.strip(), req.email.strip().lower(), hash_password(req.password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ApiError(400, "bad_request", "Email sudah terdaftar.")
    return user_dict(db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())


@api.post("/auth/login", tags=["Auth"], summary="Masuk dan dapatkan JWT")
def login(req: LoginRequest, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if row is None:
        verify_dummy(req.password)
        raise ApiError(401, "unauthorized", "Email atau password salah.")
    if not verify_password(req.password, row["password_hash"]):
        raise ApiError(401, "unauthorized", "Email atau password salah.")
    return {
        "token": make_token(row["id"], row["role"]),
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "user": user_dict(row),
    }


@api.get("/auth/me", tags=["Auth"], summary="Data pengguna yang sedang login")
def me(p: Principal = Depends(require_user)):
    return p.user


# ---------- produk ----------

@api.get("/products/{barcode}", tags=["Produk"], summary="Cari produk lewat barcode")
def get_product(
    barcode: str = PathParam(..., pattern=BARCODE_RE),
    p: Principal = Depends(require_user_or_key),
    db=Depends(get_db),
):
    row = find_product_by_barcode(db, barcode)
    if row is None:
        raise ApiError(
            404, "not_found",
            "Produk dengan barcode ini tidak ditemukan atau data gizinya tidak lengkap. Gunakan input manual.",
        )
    return product_dict(row)


@api.post("/products", status_code=201, tags=["Produk"], summary="Tambah produk manual")
def create_product(req: ProductInput, p: Principal = Depends(require_user), db=Depends(get_db)):
    data = {"barcode": req.barcode, "nama": req.nama.strip(), "merek": req.merek, "kategori": req.kategori,
            **req.nutrisi.model_dump()}
    try:
        row = insert_product(db, data, "manual", "belum_terverifikasi")
    except sqlite3.IntegrityError:
        raise ApiError(400, "bad_request", "Barcode ini sudah ada di katalog.")
    return product_dict(row)


# ---------- penilaian ----------

@api.post("/assessments", tags=["Penilaian"], summary="Nilai produk dari barcode atau nilai gizi")
def create_assessment(req: AssessmentRequest, p: Principal = Depends(require_user_or_key), db=Depends(get_db)):
    child = None
    if req.child_id is not None:
        if p.kind != "user":
            raise ApiError(403, "forbidden", "API key tidak boleh mengirim child_id.")
        child = get_child_for(db, req.child_id, p.user)

    if req.barcode is not None:
        row = find_product_by_barcode(db, req.barcode)
        if row is None:
            raise ApiError(
                404, "not_found",
                "Produk dengan barcode ini tidak ditemukan atau data gizinya tidak lengkap. Gunakan input manual.",
            )
        return build_assessment(nutrisi_of(row), row["sumber"], product_dict(row), child, req.jumlah_sajian)

    n = scoring.Nutrisi(**{k: v for k, v in req.nutrisi.model_dump().items() if k != "sajian_per_kemasan"})
    return build_assessment(n, "input_langsung", None, child, req.jumlah_sajian)


# ---------- anak ----------

@api.get("/children", tags=["Anak"], summary="Daftar anak milik akun")
def list_children(p: Principal = Depends(require_user), db=Depends(get_db)):
    rows = db.execute("SELECT * FROM children WHERE owner_id = ? ORDER BY created_at, id", (p.user["id"],)).fetchall()
    return {"items": [child_dict(r) for r in rows]}


@api.post("/children", status_code=201, tags=["Anak"], summary="Buat profil anak")
def create_child(req: ChildInput, p: Principal = Depends(require_user), db=Depends(get_db)):
    cid = new_id("child")
    db.execute(
        "INSERT INTO children (id, owner_id, nama_panggilan, usia_tahun) VALUES (?,?,?,?)",
        (cid, p.user["id"], req.nama_panggilan.strip(), req.usia_tahun),
    )
    db.commit()
    return child_dict(db.execute("SELECT * FROM children WHERE id = ?", (cid,)).fetchone())


@api.get("/children/{childId}", tags=["Anak"], summary="Profil satu anak")
def get_child(childId: str, p: Principal = Depends(require_user), db=Depends(get_db)):
    return child_dict(get_child_for(db, childId, p.user))


@api.get("/children/{childId}/daily-quota", tags=["Anak"], summary="Jatah GGL harian")
def daily_quota(
    childId: str,
    date: date | None = Query(None, description="Tanggal (YYYY-MM-DD). Bawaan hari ini (Asia/Jakarta)."),
    p: Principal = Depends(require_user),
    db=Depends(get_db),
):
    child = get_child_for(db, childId, p.user)
    return quota.build_quota(db, child, date or quota.today_wib())


@api.get("/children/{childId}/consumptions", tags=["Anak"], summary="Riwayat konsumsi satu tanggal")
def list_consumptions(
    childId: str,
    date: date | None = Query(None, description="Tanggal (YYYY-MM-DD). Bawaan hari ini (Asia/Jakarta)."),
    p: Principal = Depends(require_user),
    db=Depends(get_db),
):
    get_child_for(db, childId, p.user)
    rows = quota.consumptions_on(db, childId, date or quota.today_wib())
    return {"items": [quota.consumption_dict(r) for r in rows]}


@api.post("/children/{childId}/consumptions", status_code=201, tags=["Anak"], summary="Catat konsumsi")
def create_consumption(
    childId: str, req: ConsumptionInput, p: Principal = Depends(require_user), db=Depends(get_db)
):
    child = get_child_for(db, childId, p.user)
    prod = db.execute("SELECT * FROM products WHERE id = ?", (req.product_id,)).fetchone()
    if prod is None:
        raise ApiError(404, "not_found", "Produk tidak ditemukan.")
    waktu = quota.utc_str(req.waktu_konsumsi) if req.waktu_konsumsi else now_utc()
    ggl = scoring.ggl_per_sajian(nutrisi_of(prod), req.jumlah_sajian)
    cid = new_id("cons")
    db.execute(
        "INSERT INTO consumptions (id, child_id, product_id, jumlah_sajian, waktu_konsumsi, gula_g, garam_g, lemak_g)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (cid, childId, req.product_id, req.jumlah_sajian, waktu, ggl["gula_g"], ggl["garam_g"], ggl["lemak_g"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM consumptions WHERE id = ?", (cid,)).fetchone()
    return {
        "konsumsi": quota.consumption_dict(row),
        "jatah_terbaru": quota.build_quota(db, child, quota.wib_date_of(waktu)),
    }


app.include_router(api)
