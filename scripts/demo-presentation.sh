#!/usr/bin/env bash
# Restart Gulf War demo in presentation mode and capture screenshots.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=env.sh
. "$(dirname "$0")/env.sh"

export GULFWAR_PRESENTATION=1
export ADVISOR_EMBEDDED=1

echo "== Building battlespace UI =="
(cd services/battlespace-display/web && npm run build --silent)

echo "== Stopping prior demo on :8004 / :8081 =="
pkill -f "run-battlespace-local" 2>/dev/null || true
pkill -f "vite preview" 2>/dev/null || true
for port in 8004 8081; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 2

echo "== Starting API (presentation pace) =="
python3 scripts/run-battlespace-local.py &
API_PID=$!
sleep 3

echo "== Starting UI preview on :8081 =="
cd services/battlespace-display/web
VITE_API_URL=http://127.0.0.1:8004 npm run preview -- --port 8081 --host 0.0.0.0 &
UI_PID=$!
cd "$ROOT"

echo "== Waiting for stack =="
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8004/health >/dev/null && curl -sf http://127.0.0.1:8081/ >/dev/null; then
    break
  fi
  sleep 2
done
curl -sf http://127.0.0.1:8004/health || { echo "API failed"; exit 1; }

echo "== Capturing screenshots (~90s staged + tabs) =="
pip install playwright -q 2>/dev/null || true
python3 -m playwright install chromium 2>/dev/null || true
python3 scripts/capture-gulfwar-playwright.py http://127.0.0.1:8081

echo ""
echo "Done. Presentation images: docs/images/presentation/"
echo "  Open http://127.0.0.1:8081 for live demo (API PID $API_PID, UI PID $UI_PID)"
echo "  Stop: kill $API_PID $UI_PID"
