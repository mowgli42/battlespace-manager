#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/images/demo-screenshot.png"
URL="${1:-http://localhost:8080}"
mkdir -p "$(dirname "$OUT")"

echo "Waiting for $URL ..."
for i in $(seq 1 60); do
  if curl -sf "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

sleep 20

if command -v chromium >/dev/null 2>&1; then
  BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
  BROWSER=chromium-browser
elif command -v google-chrome >/dev/null 2>&1; then
  BROWSER=google-chrome
else
  echo "No Chromium found; install chromium for screenshots"
  exit 1
fi

"$BROWSER" --headless=new --disable-gpu --window-size=1400,900 \
  --screenshot="$OUT" "$URL"

echo "Wrote $OUT"
