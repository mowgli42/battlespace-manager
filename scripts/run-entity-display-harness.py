#!/usr/bin/env python3
"""Run entity-display API in harness mode with detection overlay scenario."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BM_ROOT / "services/entity-display/api"))
sys.path = [
    p
    for p in sys.path
    if not p.endswith("/services/battlespace-display/api")
    and not p.endswith("/services/rf-display/api")
]

OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))
sys.path.append(str(OMY_ROOT / "packages/uci_common/src"))

os.environ["ENTITY_HARNESS"] = "1"
os.environ["REDIS_URL"] = "memory://"
os.environ.setdefault(
    "COMMLINK_DIRECTORY_XML",
    str(BM_ROOT / "fixtures" / "commlink-directory-v1.1.xml"),
)

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402


def main() -> None:
    port = int(os.getenv("ENTITY_API_PORT", "8003"))
    print("Entity display HARNESS mode (fog-of-war + route-target overlays)")
    print(f"  API:     http://localhost:{port}")
    print(f"  Verify:  http://localhost:{port}/api/harness/verify")
    print("  UI:      ENTITY_HARNESS=1 ./scripts/run-entity-display-local.sh  → http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
