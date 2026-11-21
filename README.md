# CekJajan Service

Microservice Penilaian Gizi dan Jatah GGL Harian (Kelompok MandaBita).
Kontrak lengkap ada di `openapi.yaml`. Swagger UI tersedia di `/api/docs`.

## Status

| Endpoint | Status |
|---|---|
| `GET /api/health` | siap |
| `GET /api/assessments/quick` | siap |
| auth, produk, penilaian, anak, jatah harian | belum dibuat |

## Menjalankan di laptop

```
cp .env.example .env
docker compose up --build
curl localhost:8080/api/health
```

Tanpa Docker:

```
pip install -r requirements-dev.txt
python3 -m pytest
python3 -m uvicorn app.main:app --port 8000
```

## Deploy di STB

```
git clone <url-repo> && cd cekjajan-service
cp .env.example .env        # ubah GATEWAY_PORT=80
docker compose up -d --build
curl localhost/api/health
```

`cloudflared` berjalan sebagai service di STB dan meneruskan
`https://mandabita.stei.site/api` ke `http://localhost:80`. Pastikan port 80 tidak
dipakai proses lain (misalnya nginx aaPanel).

## Struktur

```
app/scoring.py     logika Nutri-Level, penanda, dan konversi gizi
app/main.py        endpoint FastAPI
gateway/nginx.conf gateway dan rate limit (60/menit per IP, 300/menit per API key)
tests/             pytest
```
