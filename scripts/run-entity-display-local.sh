#!/usr/bin/env bash
# Entity display (C2 map) — requires o-my pipeline on Redis or memory-bus demo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OMY="${OMY_ROOT:-$(cd "$ROOT/../o-my" && pwd)}"
# shellcheck source=env.sh
. "$(dirname "$0")/env.sh"

PY="${PY:-python3}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

stop_ports() {
  pkill -f "uvicorn app.main:app.*8003" 2>/dev/null || true
  pkill -f "vite preview.*8080" 2>/dev/null || true
  for port in 8003 8080; do
    fuser -k "${port}/tcp" 2>/dev/null || true
  done
  sleep 1
}

use_memory_bus() {
  export REDIS_URL="memory://"
  stop_ports
  echo "== Entity display demo (memory bus) =="
  "$PY" "${ROOT}/scripts/run-demo-with-commlink.py" &
  echo "$!" >> /tmp/bm-entity.pids
  (cd "${ROOT}/services/entity-display/web" && npm run build --silent)
  (cd "${ROOT}/services/entity-display/web" && VITE_API_URL=http://127.0.0.1:8003 npm run preview -- --port 8080 --host 0.0.0.0) &
  echo "$!" >> /tmp/bm-entity.pids
  for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8003/health >/dev/null && curl -sf http://127.0.0.1:8080/ >/dev/null; then
      echo "Entity display ready: http://127.0.0.1:8080 (API :8003)"
      exit 0
    fi
    sleep 2
  done
  echo "Entity display failed to start" >&2
  exit 1
}

ensure_redis() {
  if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    return 0
  fi
  command -v redis-server >/dev/null 2>&1 || return 1
  redis-server --daemonize yes --port 6379 --save "" --appendonly no
  sleep 1
  redis-cli ping >/dev/null
}

: > /tmp/bm-entity.pids
if ! ensure_redis; then
  use_memory_bus
fi

stop_ports
echo "== Starting o-my pipeline + entity display (Redis) =="
chmod +x "${OMY}/scripts/run-stack-local.sh" 2>/dev/null || true
# o-my stack without its UI — we serve display from battlespace-manager
export PYTHONPATH="${OMY}/packages/uci_common/src:${ROOT}/services/entity-display/api"
(cd "${OMY}/services/commlink-status" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8004 --log-level warning) &
(cd "${OMY}/services/ads-b-sensor" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level warning) &
(cd "${OMY}/services/entity-sorter" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --log-level warning) &
(cd "${ROOT}/services/entity-display/api" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --log-level warning) &
(cd "${ROOT}/services/entity-display/web" && npm run build --silent)
(cd "${ROOT}/services/entity-display/web" && VITE_API_URL=http://127.0.0.1:8003 npm run preview -- --port 8080 --host 0.0.0.0) &

for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8003/health >/dev/null && curl -sf http://127.0.0.1:8080/ >/dev/null; then
    echo "Entity display ready: http://127.0.0.1:8080"
    exit 0
  fi
  sleep 2
done
echo "Stack failed" >&2
exit 1
