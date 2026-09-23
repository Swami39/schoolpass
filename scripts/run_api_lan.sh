#!/usr/bin/env bash
# Run FastAPI so phones on the same LAN can reach it (not only localhost).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "Missing .env — copy from .env.example first." >&2
  exit 1
fi
LAN_IP="${SCHOOLPASS_LAN_IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1)}"
echo "Listening on 0.0.0.0:8000 (phones use http://${LAN_IP}:8000)"
exec uvicorn schoolpass.api.main:app --host 0.0.0.0 --port 8000 --reload
