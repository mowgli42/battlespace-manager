#!/usr/bin/env bash
# Entity display only — expects o-my cross-stack processors on shared Redis.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env.sh
. "$(dirname "$0")/env.sh"

PY="${PY:-python3}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export SERVICE_STATUS_BUS="${SERVICE_STATUS_BUS:-1}"

pkill -f "uvicorn app.main:app.*8003" 2>/dev/null || true
pkill -f "vite preview.*8080" 2>/dev/null || true
for port in 8003 8080; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 1

echo "== Entity display (Redis bus only) REDIS_URL=${REDIS_URL} =="
(cd "${ROOT}/services/entity-display/api" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --log-level info) &
(cd "${ROOT}/services/entity-display/web" && npm install --silent && npm run build --silent)
(cd "${ROOT}/services/entity-display/web" && VITE_API_URL=http://127.0.0.1:8003 npm run preview -- --port 8080 --host 0.0.0.0) &

for _ in $(seq 1 25); do
  if curl -sf http://127.0.0.1:8003/health >/dev/null && curl -sf http://127.0.0.1:8080/ >/dev/null; then
    echo "Entity display: http://127.0.0.1:8080  (API :8003)"
    exit 0
  fi
  sleep 2
done
echo "Entity display failed" >&2
exit 1
