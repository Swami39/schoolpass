#!/bin/sh
# Waits for Postgres, runs migrations, then starts the API or the worker.
# Invoked as: sh /app/entrypoint.sh [api|worker]
set -eu

echo "Waiting for postgres..."
python - <<'EOF'
import socket
import time

for _ in range(90):
    try:
        with socket.create_connection(("postgres", 5432), timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("postgres not reachable after 90s")
print("postgres is up")
EOF

echo "Running migrations..."
alembic upgrade head

MODE="${1:-api}"
if [ "$MODE" = "worker" ]; then
    echo "Starting worker..."
    exec python -m schoolpass.worker.main
else
    echo "Starting API on 0.0.0.0:8000..."
    exec uvicorn schoolpass.api.main:app --host 0.0.0.0 --port 8000
fi
