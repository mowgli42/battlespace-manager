"""Run RF display API with embedded Gulf War engine + commlink overlay."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))
OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", BM_ROOT.parent / "o-my-sim"))

_uci_omy = OMY_ROOT / "packages/uci_common/src"
_uci_sim = OMYSIM_ROOT / "packages/uci_common/src"
_docker_omy = Path("/app/packages/uci_common_omy/src")
_docker_sim = Path("/app/packages/uci_common_sim/src")

if _docker_omy.is_dir():
    sys.path.insert(0, str(_docker_omy))
    sys.path.insert(0, str(_docker_sim))
else:
    sys.path.insert(0, str(_uci_sim))
sys.path.insert(0, str(BM_ROOT / "services/rf-display/api"))
# Avoid implicit namespace merge with battlespace-display/api/app
sys.path = [
    p
    for p in sys.path
    if not p.endswith("/services/battlespace-display/api")
    and not p.endswith("/services/entity-display/api")
]

os.environ["REDIS_URL"] = os.getenv("REDIS_URL", "memory://")
if os.environ.get("RF_FORCE_MEMORY_BUS", "1") == "1":
    os.environ["REDIS_URL"] = "memory://"
os.environ.setdefault("ADVISOR_EMBEDDED", "0")
os.environ.setdefault(
    "COMMLINK_DIRECTORY_XML",
    str(BM_ROOT / "fixtures" / "commlink-directory-v1.1.xml"),
)

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
    for fid in ("LINK16-TACTICAL", "AWACS-MAGIC", "AIS-NAG", "MTI-KUWAIT", "SAT-SIGINT"):
        engine._active_feeds.add(fid)
    engine._seed_air_tasking_order()


def main() -> None:
    if _PRESENTATION:
        engine.reset()
        _seed_feeds()
        print("Presentation mode: paced scenario for walkthrough capture")
    else:
        _seed_feeds()

    def _delayed_sim() -> None:
        time.sleep(2.0)
        _sim_loop()

    threading.Thread(target=_delayed_sim, daemon=True).start()
    port = int(os.getenv("RF_API_PORT", "8005"))
    print("RF display (embedded Gulf War engine + commlink/spectrum overlay)")
    print(f"  API:  http://localhost:{port}")
    print("  UI:   ./scripts/run-rf-display-ui.sh  → http://localhost:8082")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
