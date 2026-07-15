"""Vercel serverless entry for battlespace-display (harness preview).

Private o-my / o-my-sim packages are vendored at build time into .vercel-vendor/
(same dual-PYTHONPATH pattern as Docker). Live Redis bus is disabled; the UI
serves fixtures via BATTLESPACE_HARNESS=1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_VENDOR_PATHS = (
    ROOT / ".vercel-vendor" / "o-my" / "uci_common" / "src",
    ROOT / ".vercel-vendor" / "o-my-sim" / "uci_common" / "src",
)
for path in _VENDOR_PATHS:
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

_API_ROOT = ROOT / "services" / "battlespace-display" / "api"
_PORTAL = ROOT / "services" / "display-portal"
for path in (_API_ROOT, _PORTAL):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Preview defaults — override in Vercel project env if needed.
os.environ.setdefault("BATTLESPACE_HARNESS", "1")
os.environ.setdefault("BUS_PICTURE_MODE", "0")
os.environ.setdefault("ADVISOR_EMBEDDED", "0")
os.environ.setdefault("GULFWAR_EXTERNAL_PROCESSING", "0")

from app.main import app  # noqa: E402

__all__ = ["app"]
