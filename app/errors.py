from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


_KODE_HTTP = {404: "not_found", 405: "method_not_allowed"}


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(body(exc.code, exc.message), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        kode = _KODE_HTTP.get(exc.status_code, "http_error")
        pesan = "Path tidak ditemukan." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(body(kode, pesan), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        err = exc.errors()[0]
        loc = [str(x) for x in err["loc"]]
        nama = loc[-1]
        awalan = "Parameter" if loc[0] in ("query", "path") else "Field"
        if err["type"] == "missing":
            pesan = f"{awalan} {nama} wajib diisi."
        elif err["type"] == "value_error" and err.get("ctx", {}).get("error"):
            pesan = str(err["ctx"]["error"])
        elif err["type"] == "json_invalid":
            pesan = "Isi request bukan JSON yang valid."
        elif len(loc) == 1:  # galat pada seluruh body
            pesan = "Isi request tidak valid."
        else:
            pesan = f"{awalan} {nama} tidak valid."
        return JSONResponse(body("bad_request", pesan), status_code=400)
