#!/usr/bin/env bash
# Run o-my + battlespace-manager demos and capture walkthrough screenshots.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python3}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi
OMY="${OMY_ROOT:-$(cd "$ROOT/../o-my" && pwd)}"
OMYSIM="${OMYSIM_ROOT:-$(cd "$ROOT/../o-my-sim" && pwd)}"
IMG="${ROOT}/docs/images/walkthrough"

stop_all() {
  pkill -f "run-battlespace-local" 2>/dev/null || true
  pkill -f "run-demo-with-commlink" 2>/dev/null || true
  pkill -f "uvicorn app.main:app.*800[1-4]" 2>/dev/null || true
  pkill -f "vite preview.*808[01]" 2>/dev/null || true
  for port in 8001 8002 8003 8004 8080 8081; do
    fuser -k "${port}/tcp" 2>/dev/null || true
  done
  sleep 1
}

echo "== Phase 1: entity display (C2 map) =="
stop_all
chmod +x "${ROOT}/scripts/run-entity-display-local.sh"
"${ROOT}/scripts/run-entity-display-local.sh" &
sleep 8

"${PY}" "${ROOT}/scripts/capture-walkthrough-playwright.py"

echo "== Phase 2: battlespace display (Gulf War) =="
stop_all
export GULFWAR_PRESENTATION=1
export ADVISOR_EMBEDDED=1

(cd "${ROOT}/services/battlespace-display/web" && npm run build --silent)

"${PY}" "${ROOT}/scripts/run-battlespace-local.py" &
API_PID=$!
sleep 4

(cd "${ROOT}/services/battlespace-display/web" \
  && VITE_API_URL=http://127.0.0.1:8004 npm run preview -- --port 8081 --host 0.0.0.0) &
UI_PID=$!

for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8004/health >/dev/null && curl -sf http://127.0.0.1:8081/ >/dev/null; then
    break
  fi
  sleep 2
done

curl -sf http://127.0.0.1:8004/health || { echo "battlespace API failed"; exit 1; }

"${PY}" "${ROOT}/scripts/capture-walkthrough-playwright.py" --sim http://127.0.0.1:8081 || true

if "${PY}" -c "import playwright" 2>/dev/null; then
  "${PY}" "${ROOT}/scripts/capture-gulfwar-playwright.py" http://127.0.0.1:8081
  cp "${ROOT}/docs/images/gulfwar-"*.png "${IMG}/" 2>/dev/null || true
  cp "${ROOT}/docs/images/presentation/"*.png "${IMG}/" 2>/dev/null || true
fi

echo "== Phase 3: feed fusion CLI (o-my-sim) =="
export PYTHONPATH="${OMYSIM}/packages/uci_common/src:${OMYSIM}/packages/oms_uci_sim/src"
"${PY}" "${OMYSIM}/scripts/run-feed-fusion-demo.py" > "${IMG}/05-feed-fusion-output.txt" 2>&1 || true

echo ""
echo "Walkthrough screenshots: ${IMG}/"
echo "Live battlespace UI: http://127.0.0.1:8081 (API PID ${API_PID}, UI PID ${UI_PID})"
