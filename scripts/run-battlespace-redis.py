#!/usr/bin/env python3
"""Run Gulf War engine + battlespace API with Redis bus (external processing mode)."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))
sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(BM_ROOT / "services/battlespace-display/api"))

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GULFWAR_EXTERNAL_PROCESSING", "1")

import uvicorn  # noqa: E402

from uci_common.bus import RedisBus  # noqa: E402
from uci_common.gulfwar_engine import GulfWarEngine  # noqa: E402

from app.main import app, set_engine  # noqa: E402

bus = RedisBus()
engine = GulfWarEngine(publish=bus.publish)
engine.wire_bus_handlers(bus)
set_engine(engine)

_SIM_DELTA = float(os.getenv("GULFWAR_SIM_DELTA_MIN", "1.0"))
_TICK_SLEEP = float(os.getenv("GULFWAR_TICK_SECONDS", "1.0"))


def _sim_loop() -> None:
    while True:
        engine.tick(sim_delta_minutes=_SIM_DELTA)
        time.sleep(_TICK_SLEEP)


def main() -> None:
    engine.reset()
    for fid in ("LINK16-TACTICAL", "AWACS-MAGIC", "AIS-NAG", "MTI-KUWAIT"):
        engine._active_feeds.add(fid)
    engine._seed_air_tasking_order()
    if not engine._external_processing:
        threading.Thread(target=_sim_loop, daemon=True).start()
    port = int(os.getenv("BATTLESPACE_API_PORT", "8004"))
    print(f"Battlespace + Redis bus: {os.environ['REDIS_URL']}")
    print(f"  API http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
