import os
import sqlite3
import uuid

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    nama TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'orang_tua',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS children (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    nama_panggilan TEXT NOT NULL,
    usia_tahun INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    barcode TEXT UNIQUE,
    nama TEXT NOT NULL,
    merek TEXT,
    kategori TEXT NOT NULL,
    takaran_saji REAL NOT NULL,
    satuan_takaran TEXT NOT NULL,
    sajian_per_kemasan REAL,
    gula_g REAL NOT NULL,
    natrium_mg REAL NOT NULL,
    lemak_g REAL NOT NULL,
    sumber TEXT NOT NULL,
    status_verifikasi TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS consumptions (
    id TEXT PRIMARY KEY,
    child_id TEXT NOT NULL REFERENCES children(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    jumlah_sajian REAL NOT NULL,
    waktu_konsumsi TEXT NOT NULL,
    gula_g REAL NOT NULL,
    garam_g REAL NOT NULL,
    lemak_g REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_konsumsi_anak_waktu ON consumptions(child_id, waktu_konsumsi);
CREATE INDEX IF NOT EXISTS idx_anak_pemilik ON children(owner_id);
"""

_siap: set = set()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    path = config.db_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if path not in _siap:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _siap.add(path)
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
