"""Tasking queue contract at T+0 — OMS platforms and ATO rows must hydrate on reset."""

from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_OMY_SIM = os.path.join(_REPO_ROOT, "..", "o-my-sim", "packages", "uci_common", "src")
_OMY = os.path.join(_REPO_ROOT, "..", "o-my", "packages", "uci_common", "src")
_API = os.path.join(_REPO_ROOT, "services", "battlespace-display", "api")
for _p in (_OMY, _OMY_SIM, _API):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from app.main import app, set_engine  # noqa: E402
from app.picture_contract import assert_picture_contract  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from uci_common.gulfwar_engine import GulfWarEngine  # noqa: E402


class TaskingT0Tests(unittest.TestCase):
    def setUp(self) -> None:
        engine = GulfWarEngine(publish=lambda *_a, **_k: None)
        engine.reset()
        set_engine(engine)
        self.client = TestClient(app)

    def test_picture_at_t0_lists_platforms_and_ato_tasks(self) -> None:
        resp = self.client.get("/api/picture")
        self.assertEqual(resp.status_code, 200)
        pic = resp.json()
        assert_picture_contract(pic)
        platforms = pic.get("platforms") or []
        tasks = pic.get("task_rows") or []
        self.assertGreaterEqual(len(platforms), 20, "coalition OMS platforms at T+0")
        self.assertGreaterEqual(len(tasks), 5, "ATO strike/ISR tasks at T+0")
        self.assertTrue(
            any(p.get("callsign") for p in platforms),
            "platform rows must include callsign",
        )
        tst = [t for t in tasks if t.get("is_time_sensitive")]
        self.assertGreater(len(tst), 0, "HVT ATO rows should be TST-flagged")

    def test_sim_seek_zero_keeps_hydrated_platforms(self) -> None:
        self.client.post("/api/sim/seek", json={"offset_minutes": 0})
        pic = self.client.get("/api/picture").json()
        self.assertGreater(len(pic.get("platforms") or []), 0)
        self.assertGreater(len(pic.get("task_rows") or []), 0)


if __name__ == "__main__":
    unittest.main()
