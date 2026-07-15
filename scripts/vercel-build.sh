#!/usr/bin/env bash
# Vercel buildCommand: build battlespace-display SPA into ./public for CDN.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="${ROOT}/services/battlespace-display/web"
PUBLIC="${ROOT}/public"

cd "${WEB}"
npm run build

rm -rf "${PUBLIC}"
mkdir -p "${PUBLIC}"
cp -a "${WEB}/dist/." "${PUBLIC}/"

# Keep a marker so deploy logs show harness-oriented preview builds.
cat > "${PUBLIC}/deploy.json" <<EOF
{
  "display": "battlespace-display",
  "mode": "harness",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Static assets ready at public/ ($(find "${PUBLIC}" -type f | wc -l) files)"
