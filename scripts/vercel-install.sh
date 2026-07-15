#!/usr/bin/env bash
# Vercel installCommand: vendor private Python packages (best-effort) + npm deps.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

echo "== vercel-install: vendor private uci_common =="
bash "${ROOT}/scripts/vercel-vendor-private.sh"

WEB="${ROOT}/services/battlespace-display/web"
if [[ ! -f "${WEB}/package.json" ]]; then
  echo "ERROR: missing ${WEB}/package.json" >&2
  exit 1
fi

echo "== vercel-install: npm deps (${WEB}) =="
cd "${WEB}"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

echo "== vercel-install: done =="
