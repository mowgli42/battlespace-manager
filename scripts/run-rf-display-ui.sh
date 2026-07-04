#!/usr/bin/env bash
set -euo pipefail
BM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "${BM_ROOT}/scripts/env.sh"

export VITE_API_URL="${VITE_API_URL:-http://localhost:8005}"
cd "${BM_ROOT}/services/rf-display/web"
npm install --silent
npm run dev -- --host 0.0.0.0 --port 8082
