#!/usr/bin/env bash
# Local smoke: vendor + import FastAPI app (harness). Does not call Vercel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

bash "${ROOT}/scripts/vercel-vendor-private.sh"

export PYTHONPATH="${ROOT}/services/battlespace-display/api:${ROOT}/services/display-portal:${ROOT}/.vercel-vendor/o-my/uci_common/src:${ROOT}/.vercel-vendor/o-my-sim/uci_common/src${PYTHONPATH:+:$PYTHONPATH}"
export BATTLESPACE_HARNESS=1
export BUS_PICTURE_MODE=0

python3 - <<'PY'
from api.index import app
from fastapi.testclient import TestClient

client = TestClient(app)
health = client.get("/health").json()
assert health.get("status") == "ok", health
assert health.get("harness_mode") is True, health
picture = client.get("/api/picture").json()
assert picture.get("harness_mode") is True, picture
assert isinstance(picture.get("entities"), list), "entities missing"
verify = client.get("/api/harness/verify").json()
assert verify.get("passed") is True, verify
print("vercel-smoke-ok", app.title, "entities=", len(picture.get("entities") or []))
PY
