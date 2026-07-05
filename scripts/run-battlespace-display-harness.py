#!/usr/bin/env python3
"""Run battlespace-display API in F2T2EA harness mode."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BM_ROOT / "services/battlespace-display/api"))
sys.path = [
    p
    for p in sys.path
    if not p.endswith("/services/entity-display/api")
    and not p.endswith("/services/rf-display/api")
]

OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))
OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))
sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(OMY_ROOT / "packages/uci_common/src"))

os.environ["BATTLESPACE_HARNESS"] = "1"
os.environ.setdefault("ADVISOR_EMBEDDED", "0")

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402


def main() -> None:
    port = int(os.getenv("BATTLESPACE_API_PORT", "8004"))
    print("Battlespace display HARNESS mode (F2T2EA · TST · unassigned filters)")
    print(f"  API:     http://localhost:{port}")
    print(f"  Picture: http://localhost:{port}/api/picture")
    print(f"  Verify:  http://localhost:{port}/api/harness/verify")
    print("  UI:      cd services/battlespace-display/web && npm run dev")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
