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
unset BUS_PICTURE_MODE
export PYTHONPATH="${ROOT}/services/entity-display/api:${PYTHONPATH:-}"

pkill -f "uvicorn app.main:app.*8030" 2>/dev/null || true
pkill -f "vite preview.*8930" 2>/dev/null || true
for port in 8030 8930; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 1

echo "== Entity display (Redis bus only) REDIS_URL=${REDIS_URL} =="
(cd "${ROOT}/services/entity-display/api" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8030 --log-level info) &
(cd "${ROOT}/services/entity-display/web" && npm install --silent && npm run build --silent)
(cd "${ROOT}/services/entity-display/web" && VITE_API_URL=http://127.0.0.1:8030 npm run preview -- --port 8930 --host 0.0.0.0) &

for _ in $(seq 1 25); do
  if curl -sf http://127.0.0.1:8030/health >/dev/null && curl -sf http://127.0.0.1:8930/ >/dev/null; then
    echo "Entity display: http://127.0.0.1:8930  (API :8030)"
    exit 0
  fi
  sleep 2
done
echo "Entity display failed" >&2
exit 1
