#!/usr/bin/env bash
# Menjalankan layanan di STB. Jalankan dari folder repo: bash deploy.sh
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i 's/^GATEWAY_PORT=.*/GATEWAY_PORT=80/' .env
  echo ".env dibuat dengan GATEWAY_PORT=80"
fi

PORT=$(grep '^GATEWAY_PORT=' .env | cut -d= -f2)
if ss -tln | grep -q ":${PORT} " && ! docker compose ps --status running 2>/dev/null | grep -q gateway; then
  echo "Port ${PORT} sudah dipakai proses lain:"
  ss -tlnp | grep ":${PORT} " || true
  echo "Hentikan prosesnya dulu (cek: docker ps), lalu jalankan ulang."
  exit 1
fi

mkdir -p data
docker compose up -d --build
sleep 3
curl -fsS "http://localhost:${PORT}/api/health" && echo && echo "Layanan hidup."
