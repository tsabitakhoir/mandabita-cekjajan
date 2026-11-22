#!/usr/bin/env bash
# Menjalankan layanan di STB. Jalankan dari folder repo: bash deploy.sh
set -euo pipefail

acak() { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i 's/^GATEWAY_PORT=.*/GATEWAY_PORT=80/' .env
  echo ".env dibuat dengan GATEWAY_PORT=80"
fi

# JWT_SECRET: buat bila belum ada atau masih berisi contoh.
if ! grep -q '^JWT_SECRET=' .env; then
  echo "JWT_SECRET=$(acak)" >> .env
  echo "JWT_SECRET ditambahkan ke .env"
elif grep -q '^JWT_SECRET=GANTI' .env || grep -q '^JWT_SECRET=$' .env; then
  sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$(acak)/" .env
  echo "JWT_SECRET dibuat di .env"
fi
grep -q '^API_KEYS=' .env || echo "API_KEYS=" >> .env

PORT=$(grep '^GATEWAY_PORT=' .env | cut -d= -f2)
if ss -tln | grep -q ":${PORT} " && ! docker compose ps --status running 2>/dev/null | grep -q gateway; then
  echo "Port ${PORT} sudah dipakai proses lain:"
  ss -tlnp | grep ":${PORT} " || true
  echo "Hentikan prosesnya dulu (cek: docker ps), lalu jalankan ulang."
  exit 1
fi

docker compose up -d --build
sleep 4
curl -fsS "http://localhost:${PORT}/api/health" && echo && echo "Layanan hidup."
