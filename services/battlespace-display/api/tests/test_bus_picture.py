"""Bus picture state tests."""

from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_OMY = os.path.join(_REPO, "..", "o-my", "packages", "uci_common", "src")
_OMYSIM = os.path.join(_REPO, "..", "o-my-sim", "packages", "uci_common", "src")
_API = os.path.join(_REPO, "services", "battlespace-display", "api")
for _p in (_OMY, _OMYSIM, _API):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from app.bus_picture import BusPictureState  # noqa: E402
from app.picture_contract import validate_picture  # noqa: E402
from uci_common.sensing_messages import CorrelatedEntity, build_correlated_entity_xml  # noqa: E402
from uci_common.topics import TOPIC_CORRELATED_ENTITY  # noqa: E402


class BusPictureTests(unittest.TestCase):
    def test_correlated_entity_updates_picture(self) -> None:
        state = BusPictureState()
        ent = CorrelatedEntity(
            entity_id="ENT-1",
            latitude=29.5,
            longitude=47.5,
            domain="AIR",
            affiliation="OPFOR",
            platform_type="SAM",
            confidence=0.9,
            contributor_track_ids=["T-1"],
        )
        state.ingest(TOPIC_CORRELATED_ENTITY, build_correlated_entity_xml(ent))
        payload = state.snapshot()
        self.assertEqual(len(payload["entities"]), 1)
        self.assertEqual(payload["entities"][0]["entity_id"], "ENT-1")
        errors = validate_picture(
            {
                "sim_minutes": payload["sim_minutes"],
                "entities": payload["entities"],
                "threat_picture": payload["threat_picture"],
                "mission_thread": payload["mission_thread"],
                "attention_queue": payload["attention_queue"],
                "fkcm_targets": payload["fkcm_targets"],
                "timeline_view": {
                    "sim_minutes": payload["sim_minutes"],
                    "items": [],
                    "upcoming_count": 0,
                },
                "task_rows": payload["task_rows"],
            }
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
