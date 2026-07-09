#!/usr/bin/env bash
# Battlespace display API + UI against shared Redis (bus picture mode).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env.sh
. "$(dirname "$0")/env.sh"

PY="${PY:-python3}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export BUS_PICTURE_MODE="${BUS_PICTURE_MODE:-1}"
export SERVICE_STATUS_BUS="${SERVICE_STATUS_BUS:-1}"
export ADVISOR_BUS="${ADVISOR_BUS:-1}"
export TASKING_VIA_BUS="${TASKING_VIA_BUS:-1}"
export ADVISOR_EMBEDDED=0
API_PORT="${BATTLESPACE_API_PORT:-8004}"
UI_PORT="${BATTLESPACE_UI_PORT:-8081}"

pkill -f "run-battlespace-bus" 2>/dev/null || true
pkill -f "uvicorn app.main:app.*${API_PORT}" 2>/dev/null || true
for port in "${API_PORT}" "${UI_PORT}"; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 1

echo "== Battlespace bus picture API :${API_PORT} =="
"$PY" "${ROOT}/scripts/run-battlespace-bus.py" &
API_PID=$!
sleep 2

echo "== Battlespace UI :${UI_PORT} =="
(cd "${ROOT}/services/battlespace-display/web" && npm install --silent && npm run build --silent)
(cd "${ROOT}/services/battlespace-display/web" && VITE_API_URL="http://127.0.0.1:${API_PORT}" npm run preview -- --port "${UI_PORT}" --host 0.0.0.0) &
UI_PID=$!

for _ in $(seq 1 25); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null && curl -sf "http://127.0.0.1:${UI_PORT}/" >/dev/null; then
    echo ""
    echo "Battlespace display: http://127.0.0.1:${UI_PORT}  (API :${API_PORT}, bus picture)"
    echo "Stop: kill ${API_PID} ${UI_PID}"
    exit 0
  fi
  sleep 2
done
echo "Battlespace bus stack failed" >&2
exit 1
