import hashlib
import hmac
import os
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .db import get_db
from .errors import ApiError

TOKEN_TTL = 86400  # 24 jam
_N, _R, _P = 2**14, 8, 1

bearer = HTTPBearer(auto_error=False, description="JWT dari POST /auth/login.")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="API key untuk kelompok lain.")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


_dummy_hash = None


def verify_dummy(password: str) -> None:
    """Menyamakan waktu respons saat email tidak ada, agar tidak bisa dipakai menebak akun."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password")
    verify_password(password, _dummy_hash)


def make_token(user_id: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, config.jwt_secret(), algorithm="HS256")


def _tolak(pesan: str) -> ApiError:
    return ApiError(401, "unauthorized", pesan, {"WWW-Authenticate": "Bearer"})


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, config.jwt_secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise _tolak("Token sudah kedaluwarsa. Silakan login lagi.")
    except jwt.InvalidTokenError:
        raise _tolak("Token tidak valid.")


@dataclass
class Principal:
    kind: str  # "user" atau "apikey"
    user: dict | None = None
    key_name: str | None = None


def _user_dari_token(creds: HTTPAuthorizationCredentials, db) -> Principal:
    payload = _decode(creds.credentials)
    row = db.execute("SELECT id, nama, email, role FROM users WHERE id = ?", (payload["sub"],)).fetchone()
    if row is None:
        raise _tolak("Token tidak valid.")
    return Principal("user", user=dict(row))


def require_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)) -> Principal:
    if creds is None:
        raise _tolak("Token diperlukan. Kirim header Authorization: Bearer <token>.")
    return _user_dari_token(creds, db)


def require_user_or_key(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    key: str | None = Depends(api_key_header),
    db=Depends(get_db),
) -> Principal:
    if creds is not None:
        return _user_dari_token(creds, db)
    if key is not None:
        for kunci, nama in config.api_keys().items():
            if hmac.compare_digest(kunci.encode(), key.encode()):
                return Principal("apikey", key_name=nama)
        raise _tolak("API key salah.")
    raise _tolak("Token atau API key diperlukan.")
