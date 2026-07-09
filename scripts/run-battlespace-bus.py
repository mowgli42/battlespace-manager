#!/usr/bin/env python3
"""Run battlespace API in bus picture mode (no GulfWarEngine)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))
OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))
sys.path.insert(0, str(OMY_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(BM_ROOT / "services/battlespace-display/api"))
sys.path.insert(0, str(BM_ROOT / "services/display-portal"))

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("BUS_PICTURE_MODE", "1")
os.environ.setdefault("SERVICE_STATUS_BUS", "1")
os.environ.setdefault("ADVISOR_BUS", "1")
os.environ.setdefault("TASKING_VIA_BUS", "1")
os.environ.setdefault("ADVISOR_EMBEDDED", "0")

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("BATTLESPACE_API_PORT", "8004"))
    print(f"Battlespace bus picture: {os.environ['REDIS_URL']}")
    print(f"  API http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
