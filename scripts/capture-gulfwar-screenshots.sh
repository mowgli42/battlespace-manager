#!/usr/bin/env bash
# Quick headless Chromium captures (no staged timing). Prefer capture-gulfwar-playwright.py for demos.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/docs/images"
mkdir -p "$IMG"
BASE="${1:-http://localhost:8080}"

if command -v chromium >/dev/null 2>&1; then
  BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
  BROWSER=chromium-browser
elif command -v google-chrome >/dev/null 2>&1; then
  BROWSER=google-chrome
else
  echo "Chromium or Chrome required for screenshots"
  exit 1
fi

shot() {
  local name="$1"
  local url="$2"
  echo "Capturing $name ..."
  for i in $(seq 1 40); do
    if curl -sf "$url" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  sleep 4
  "$BROWSER" --headless=new --disable-gpu --window-size=1600,900 \
    --screenshot="$IMG/$name" "$url"
}

shot "gulfwar-map.png" "$BASE"
shot "gulfwar-tracks.png" "$BASE/?tab=tracks"
shot "gulfwar-sources.png" "$BASE/?tab=sources"
shot "gulfwar-decisions.png" "$BASE/?tab=decisions"
shot "gulfwar-assess.png" "$BASE/?tab=assess"
shot "gulfwar-killchain.png" "$BASE/?tab=killchain"

# Legacy aliases for older docs
cp -f "$IMG/gulfwar-sources.png" "$IMG/gulfwar-fusion.png" 2>/dev/null || true
cp -f "$IMG/gulfwar-decisions.png" "$IMG/gulfwar-tasking.png" 2>/dev/null || true

echo "Screenshots written to $IMG/gulfwar-*.png"
