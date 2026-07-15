#!/usr/bin/env bash
# Vercel installCommand: vendor private Python packages + npm deps for battlespace web.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

bash "${ROOT}/scripts/vercel-vendor-private.sh"

WEB="${ROOT}/services/battlespace-display/web"
if [[ ! -f "${WEB}/package.json" ]]; then
  echo "ERROR: missing ${WEB}/package.json" >&2
  exit 1
fi

cd "${WEB}"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
