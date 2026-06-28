"""Picture schema contract tests for /api/picture."""

from __future__ import annotations

import os
import sys
import unittest

# Sibling repos on PYTHONPATH when run via scripts/run-display-tests.sh
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_OMY_SIM = os.path.join(_REPO_ROOT, "..", "o-my-sim", "packages", "uci_common", "src")
_OMY = os.path.join(_REPO_ROOT, "..", "o-my", "packages", "uci_common", "src")
_API = os.path.join(_REPO_ROOT, "services", "battlespace-display", "api")
for _p in (_OMY, _OMY_SIM, _API):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from app.picture_contract import assert_picture_contract, picture_from_snapshot, validate_picture  # noqa: E402
from uci_common.gulfwar_engine import GulfWarEngine  # noqa: E402


class PictureContractTests(unittest.TestCase):
    def test_rejects_empty_payload(self) -> None:
        errors = validate_picture({})
        self.assertTrue(any("sim_minutes" in e for e in errors))
        self.assertTrue(any("entities" in e for e in errors))

    def test_accepts_minimal_valid_fixture(self) -> None:
        payload = {
            "sim_minutes": 15.0,
            "entities": [],
            "threat_picture": {"entity_count": 0, "active_tasks": 0},
            "mission_thread": {"f2t2ea_phases": [], "phase_counts": {}},
            "attention_queue": [],
            "fkcm_targets": [],
            "timeline_view": {"sim_minutes": 15.0, "items": [], "upcoming_count": 0},
            "task_rows": [],
        }
        self.assertEqual(validate_picture(payload), [])
        assert_picture_contract(payload)

    def test_gulfwar_engine_picture_at_t15(self) -> None:
        mini = {
            "scenarioId": "TEST-PICTURE-01",
            "demoScale": {"enabled": False},
            "bbox": {"south": 28.0, "north": 31.5, "west": 46.0, "east": 49.5},
            "coalitionPlatforms": [],
            "highValueTargets": [],
            "timeline": [{"simOffsetMinutes": 20, "event": "SCUD", "narrative": "SCUD"}],
        }
        engine = GulfWarEngine(publish=lambda *_a, **_k: None, scenario=mini)
        for _ in range(15):
            engine.tick(sim_delta_minutes=1.0)
        snap = engine.snapshot()
        payload = picture_from_snapshot(
            snap,
            scenario_timeline=mini["timeline"],
            fired_offsets=engine._fired_events,
        )
        self.assertGreaterEqual(payload.get("sim_minutes", 0), 14.0)
        assert_picture_contract(payload)
        self.assertIsInstance(payload["entities"], list)
        self.assertIn("items", payload["timeline_view"])


if __name__ == "__main__":
    unittest.main()
