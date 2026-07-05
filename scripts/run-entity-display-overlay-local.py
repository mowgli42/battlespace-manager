#!/usr/bin/env python3
"""Run Gulf War engine + entity-display API with dynamic detection overlays."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))
OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))

sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(OMY_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(BM_ROOT / "services/entity-display/api"))
sys.path = [
    p
    for p in sys.path
    if not p.endswith("/services/battlespace-display/api")
    and not p.endswith("/services/rf-display/api")
]

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENTITY_OVERLAYS", "1")
os.environ.setdefault(
    "ENTITY_SCENARIO_JSON",
    str(OMYSIM_ROOT / "fixtures" / "scenarios" / "gulf_war_1991.json"),
)
os.environ.setdefault(
    "COMMLINK_DIRECTORY_XML",
    str(BM_ROOT / "fixtures" / "commlink-directory-v1.1.xml"),
)

import uvicorn  # noqa: E402

from uci_common.bus import RedisBus  # noqa: E402
from uci_common.gulfwar_engine import GulfWarEngine  # noqa: E402

from app.main import app  # noqa: E402

bus = RedisBus()
engine = GulfWarEngine(publish=bus.publish)
engine.wire_bus_handlers(bus)

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
    threading.Thread(target=_sim_loop, daemon=True).start()

    port = int(os.getenv("ENTITY_API_PORT", "8003"))
    print("Entity display LIVE overlay mode (Gulf War engine + Redis bus)")
    print(f"  API:      http://localhost:{port}")
    print(f"  Overlays: http://localhost:{port}/api/overlays")
    print(f"  Verify:   http://localhost:{port}/api/harness/verify")
    print("  UI:       ./scripts/run-entity-display-local.sh  → http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
