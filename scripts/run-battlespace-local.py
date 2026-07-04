#!/usr/bin/env python3
"""Run Gulf War battlespace display API with embedded engine (memory bus)."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))
_uci = Path("/app/packages/uci_common/src")
if _uci.is_dir():
    sys.path.insert(0, str(_uci))
else:
    sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(BM_ROOT / "services/battlespace-display/api"))

os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("ADVISOR_EMBEDDED", "0")

import uvicorn  # noqa: E402

from uci_common.bus import RedisBus  # noqa: E402
from uci_common.gulfwar_engine import GulfWarEngine  # noqa: E402

from app.main import app, set_engine  # noqa: E402

bus = RedisBus()
engine = GulfWarEngine(publish=bus.publish)
set_engine(engine)

_PRESENTATION = os.getenv("GULFWAR_PRESENTATION", "").lower() in ("1", "true", "yes")
_SIM_DELTA = float(os.getenv("GULFWAR_SIM_DELTA_MIN", "1.0" if _PRESENTATION else "2.0"))
_TICK_SLEEP = float(os.getenv("GULFWAR_TICK_SECONDS", "1.5" if _PRESENTATION else "1.0"))


def _sim_loop() -> None:
    while True:
        engine.tick(sim_delta_minutes=_SIM_DELTA)
        time.sleep(_TICK_SLEEP)


def _seed_feeds() -> None:
    for fid in ("LINK16-TACTICAL", "AWACS-MAGIC", "AIS-NAG", "MTI-KUWAIT"):
        engine._active_feeds.add(fid)
    engine._seed_air_tasking_order()


def main() -> None:
    if _PRESENTATION:
        engine.reset()
        _seed_feeds()
        _seed_feeds()
        print("Presentation mode: T+0 reset, paced scenario (~75s to T+50)")
    else:
        _seed_feeds()

    threading.Thread(target=_sim_loop, daemon=True).start()
    port = int(os.getenv("BATTLESPACE_API_PORT", "8004"))
    print("Battlespace display (embedded Gulf War engine)")
    print(f"  API:  http://localhost:{port}")
    print("  UI:   ./scripts/run-battlespace-ui.sh  → http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
