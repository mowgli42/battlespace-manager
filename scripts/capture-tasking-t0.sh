#!/usr/bin/env bash
# Capture CAOC tasking queue at T+0 (platforms + ATO tasks) for visual verification.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=env.sh
. "$(dirname "$0")/env.sh"

UI_PORT="${BATTLESPACE_UI_PORT:-8081}"
API_PORT="${BATTLESPACE_API_PORT:-8004}"
OUT="${ROOT}/docs/images/tasking-queue-t0-fix.png"

export GULFWAR_PRESENTATION=1
export ADVISOR_EMBEDDED=1

echo "== Building battlespace UI =="
(cd services/battlespace-display/web && npm run build --silent)

echo "== Stopping prior demo on :${API_PORT} / :${UI_PORT} =="
pkill -f "run-battlespace-local" 2>/dev/null || true
pkill -f "vite preview" 2>/dev/null || true
for port in "${API_PORT}" "${UI_PORT}"; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 2

echo "== Starting API =="
python3 scripts/run-battlespace-local.py &
API_PID=$!
sleep 3

echo "== Starting UI on :${UI_PORT} =="
(cd services/battlespace-display/web && VITE_API_URL="http://127.0.0.1:${API_PORT}" npm run preview -- --port "${UI_PORT}" --host 0.0.0.0) &
UI_PID=$!

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null && curl -sf "http://127.0.0.1:${UI_PORT}/" >/dev/null; then
    break
  fi
  sleep 2
done
curl -sf "http://127.0.0.1:${API_PORT}/health" || { echo "API failed"; kill "$API_PID" "$UI_PID" 2>/dev/null; exit 1; }

PYTHON="${ROOT}/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON=python3
"$PYTHON" -m pip install playwright -q 2>/dev/null || true
"$PYTHON" -m playwright install chromium 2>/dev/null || true

echo "== Waiting for stack to settle =="
sleep 8

echo "== Capturing Decisions tab at T+0 =="
"$PYTHON" scripts/capture-tasking-t0.py "http://127.0.0.1:${UI_PORT}" "${OUT}"

echo ""
echo "Screenshot: ${OUT}"
echo "Live demo:  http://127.0.0.1:${UI_PORT} (API PID ${API_PID}, UI PID ${UI_PID})"
echo "Stop: kill ${API_PID} ${UI_PID}"
