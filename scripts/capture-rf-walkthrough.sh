#!/usr/bin/env bash
# Start RF display (+ optional battlespace) and capture walkthrough screenshots.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python3}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi
# shellcheck source=scripts/env.sh
source "${ROOT}/scripts/env.sh"
IMG="${ROOT}/docs/images/rf-walkthrough"

stop_rf() {
  pkill -f "run-rf-display-local" 2>/dev/null || true
  pkill -f "uvicorn.*8005" 2>/dev/null || true
  fuser -k 8005/tcp 8082/tcp 8083/tcp 2>/dev/null || true
  sleep 1
}

stop_rf

echo "== RF display API =="
export GULFWAR_PRESENTATION=1
export RF_FORCE_MEMORY_BUS=1

"${PY}" "${ROOT}/scripts/run-rf-display-local.py" &
API_PID=$!
sleep 5

echo "== RF display web =="
(cd "${ROOT}/services/rf-display/web" && npm run build --silent)
(cd "${ROOT}/services/rf-display/web" \
  && VITE_API_URL=http://127.0.0.1:8005 npm run preview -- --port 8082 --host 0.0.0.0) &
UI_PID=$!

for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8005/health >/dev/null && curl -sf http://127.0.0.1:8082/ >/dev/null; then
    break
  fi
  sleep 2
done
curl -sf http://127.0.0.1:8005/health || { echo "RF API failed"; exit 1; }

# Advance sim so SA-6 SIGINT cue appears (~T+12)
sleep 20

echo "== Capture screenshots =="
"${PY}" "${ROOT}/scripts/capture-rf-playwright.py" --rf http://127.0.0.1:8082

# Optional: battlespace tasking cross-link screenshot
if curl -sf http://127.0.0.1:8081/ >/dev/null 2>&1; then
  "${PY}" "${ROOT}/scripts/capture-rf-playwright.py" --rf http://127.0.0.1:8082 --battlespace http://127.0.0.1:8081
fi

echo ""
echo "RF walkthrough assets: ${IMG}/"
echo "Live RF UI: http://127.0.0.1:8082 (API PID ${API_PID}, UI PID ${UI_PID})"
