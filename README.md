# CekJajan Service

Microservice Penilaian Gizi dan Jatah GGL Harian (Kelompok MandaBita, K02).
Kontrak lengkap: `openapi.yaml` (juga di `/api/openapi.yaml`). Swagger UI: `/api/docs`.
Dokumentasi lengkap dalam `README.pdf`.

Layanan hidup di `https://mandabita.stei.site/api`.

## Endpoint

| Endpoint | Akses |
|---|---|
| `GET /api/health` | publik |
| `GET /api/assessments/quick` | publik |
| `POST /api/auth/register`, `POST /api/auth/login` | publik |
| `GET /api/auth/me` | JWT |
| `GET /api/products/{barcode}` | JWT atau API key |
| `POST /api/products` | JWT |
| `POST /api/assessments` | JWT atau API key |
| `GET, POST /api/children`, `GET /api/children/{id}` | JWT |
| `GET /api/children/{id}/daily-quota` | JWT |
| `GET, POST /api/children/{id}/consumptions` | JWT |

## Menjalankan di laptop

```
cp .env.example .env      # isi JWT_SECRET dengan: openssl rand -hex 32
docker compose up --build
curl localhost:8080/api/health
```

Tanpa Docker:

```
pip install -r requirements-dev.txt
python3 -m pytest
JWT_SECRET=$(openssl rand -hex 32) DB_PATH=./cekjajan.db python3 -m uvicorn app.main:app --port 8000
```

## Deploy di STB

```
git clone https://github.com/tsabitakhoir/mandabita-cekjajan.git
cd mandabita-cekjajan
bash deploy.sh
```

`deploy.sh` membuat `.env` (port 80 dan `JWT_SECRET` acak) bila belum ada, memeriksa port,
lalu menjalankan `docker compose up -d --build`. `cloudflared` berjalan sebagai service di STB
dan meneruskan `https://mandabita.stei.site/api` ke `http://localhost:80`. Pastikan port 80
tidak dipakai proses lain (nginx aaPanel dinonaktifkan).

Memperbarui setelah ada perubahan kode: `git pull && bash deploy.sh`.

## API key kelompok lain

Isi di `.env` pada baris `API_KEYS`, format `nama:kunci` dipisah koma (kunci minimal 16 karakter),
lalu `docker compose up -d`:

```
API_KEYS=ahay:kunci-acak-1,aisyahjeko:kunci-acak-2
```

Satu kunci per kelompok. Mencabut kunci: hapus pasangannya dari `.env` dan jalankan ulang.
Kunci acak: `openssl rand -hex 16`.

## Struktur

```
app/main.py        endpoint FastAPI
app/scoring.py     Nutri-Level, penanda, konversi gizi
app/quota.py       batas harian per usia, jatah, batas tanggal WIB
app/security.py    JWT, hash password (scrypt), API key
app/off.py         klien Open Food Facts
app/db.py          SQLite (volume Docker cekjajan-data di /data)
gateway/nginx.conf gateway dan rate limit
tests/             pytest (65 tes)
```

## Rate limit (gateway)

60/menit per IP untuk endpoint publik, 10/menit per IP untuk login dan daftar,
300/menit per API key atau IP untuk endpoint lain. Melebihi batas: HTTP 429.
