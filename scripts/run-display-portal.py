#!/usr/bin/env python3
"""Run the OMS display portal on :8888."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BM_ROOT / "services" / "display-portal"))

os.environ.setdefault("DISPLAY_PUBLIC_HOST", "localhost")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("DISPLAY_PORTAL_PORT", "8888")), reload=False)
