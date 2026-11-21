from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import scoring

VERSION = "0.2.0"
DISCLAIMER = "Hasil berupa perkiraan, bukan diagnosis atau pengganti saran tenaga kesehatan."

app = FastAPI(
    title="CekJajan Service API",
    version=VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

api = APIRouter(prefix="/api")


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    err = exc.errors()[0]
    nama = str(err["loc"][-1])
    if err["type"] == "missing":
        pesan = f"Parameter {nama} wajib diisi."
    else:
        pesan = f"Parameter {nama} tidak valid."
    return JSONResponse(status_code=400, content=error_body("bad_request", pesan))


@api.get("/health", tags=["Publik"], summary="Cek layanan hidup")
def health():
    return {"status": "ok", "service": "cekjajan", "version": VERSION}


@api.get(
    "/assessments/quick",
    tags=["Publik", "Penilaian"],
    summary="Penilaian cepat dari nilai gizi (tanpa login)",
)
def assessments_quick(
    takaran_saji: float = Query(..., ge=0.1, description="Besar satu sajian."),
    satuan_takaran: Literal["g", "ml"] = Query(..., description="Satuan takaran."),
    gula_g: float = Query(..., ge=0, description="Gula per sajian, gram."),
    natrium_mg: float = Query(..., ge=0, description="Natrium per sajian, miligram."),
    lemak_g: float = Query(..., ge=0, description="Lemak total per sajian, gram."),
):
    hasil = scoring.nilai(
        scoring.Nutrisi(takaran_saji, satuan_takaran, gula_g, natrium_mg, lemak_g)
    )
    return {
        "sumber_data": "input_langsung",
        "produk": None,
        **hasil,
        "dampak_jatah_harian": None,
        "disclaimer": DISCLAIMER,
        "dinilai_pada": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


app.include_router(api)
