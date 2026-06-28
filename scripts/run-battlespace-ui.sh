#!/usr/bin/env bash
# Battlespace Gulf War operator UI (preview on :8081, API default :8004).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${BATTLESPACE_API_PORT:-8004}"
UI_PORT="${BATTLESPACE_UI_PORT:-8081}"

cd "${ROOT}/services/battlespace-display/web"
npm install --silent
npm run build --silent
VITE_API_URL="http://127.0.0.1:${API_PORT}" npm run preview -- --port "${UI_PORT}" --host 0.0.0.0
