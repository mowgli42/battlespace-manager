#!/usr/bin/env bash
# Start harness-mode displays + portal and capture README screenshots.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi
# shellcheck source=scripts/env.sh
source "${ROOT}/scripts/env.sh"

IMG="${ROOT}/docs/images/displays"
mkdir -p "$IMG"

stop_all() {
  pkill -f "run-entity-display-harness" 2>/dev/null || true
  pkill -f "run-battlespace-display-harness" 2>/dev/null || true
  pkill -f "run-rf-display-harness" 2>/dev/null || true
  pkill -f "run-display-portal" 2>/dev/null || true
  pkill -f "vite preview" 2>/dev/null || true
  for port in 8003 8004 8005 8080 8081 8082 8888; do
    fuser -k "${port}/tcp" 2>/dev/null || true
  done
  sleep 2
}

stop_all

echo "== Build web UIs =="
for svc in entity-display battlespace-display rf-display; do
  (cd "${ROOT}/services/${svc}/web" && npm install --silent && npm run build --silent)
done

echo "== Start harness APIs =="
export ENTITY_HARNESS=1 BATTLESPACE_HARNESS=1 RF_HARNESS=1 ADVISOR_EMBEDDED=0
export REDIS_URL=memory://
export COMMLINK_DIRECTORY_XML="${ROOT}/fixtures/commlink-directory-v1.1.xml"

"$PY" "${ROOT}/scripts/run-entity-display-harness.py" &
"$PY" "${ROOT}/scripts/run-battlespace-display-harness.py" &
"$PY" "${ROOT}/scripts/run-rf-display-harness.py" &
"$PY" "${ROOT}/scripts/run-display-portal.py" &

echo "== Start UI previews =="
(cd "${ROOT}/services/entity-display/web" && VITE_API_URL=http://127.0.0.1:8003 npm run preview -- --port 8080 --host 0.0.0.0) &
(cd "${ROOT}/services/battlespace-display/web" && VITE_API_URL=http://127.0.0.1:8004 npm run preview -- --port 8081 --host 0.0.0.0) &
(cd "${ROOT}/services/rf-display/web" && VITE_API_URL=http://127.0.0.1:8005 npm run preview -- --port 8082 --host 0.0.0.0) &

echo "== Wait for stack =="
for url in \
  http://127.0.0.1:8003/health \
  http://127.0.0.1:8004/health \
  http://127.0.0.1:8005/health \
  http://127.0.0.1:8888/health \
  http://127.0.0.1:8080/ \
  http://127.0.0.1:8081/ \
  http://127.0.0.1:8082/; do
  for _ in $(seq 1 45); do
    if curl -sf "$url" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  curl -sf "$url" >/dev/null || { echo "Failed waiting for $url"; exit 1; }
done

echo "== Install Playwright if needed =="
"$PY" -m pip install playwright -q 2>/dev/null || true
"$PY" -m playwright install chromium 2>/dev/null || true

echo "== Capture screenshots =="
"$PY" "${ROOT}/scripts/capture-displays-playwright.py"

echo ""
echo "Done. Screenshots: ${IMG}/"
ls -la "${IMG}/"
