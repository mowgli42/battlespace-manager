"""Tests for timeline view builder."""

from __future__ import annotations

import unittest

from app.timeline import build_timeline_view


class TimelineViewTests(unittest.TestCase):
    def test_merges_scenario_and_tasks(self) -> None:
        view = build_timeline_view(
            sim_minutes=10.0,
            scenario_timeline=[
                {"simOffsetMinutes": 5, "event": "FEED_ON", "narrative": "AWACS live"},
                {"simOffsetMinutes": 20, "event": "SCUD", "narrative": "SCUD launch"},
            ],
            fired_offsets={5},
            task_rows=[
                {
                    "task_id": "T-1",
                    "role": "STRIKE",
                    "target_name": "SA-6",
                    "target_entity_id": "E-1",
                    "lifecycle_state": "NEW",
                    "assigned_at_sim": 10,
                    "kill_chain_phase": "Target",
                    "priority": 1,
                }
            ],
        )
        self.assertEqual(view["scenario_count"], 2)
        self.assertEqual(view["task_count"], 1)
        kinds = {i["kind"] for i in view["items"]}
        self.assertIn("scenario", kinds)
        self.assertIn("task", kinds)
        past = [i for i in view["items"] if i["id"].startswith("scenario-") and i["sim_offset"] == 5]
        self.assertEqual(past[0]["status"], "past")
        future = [i for i in view["items"] if i["sim_offset"] == 20]
        self.assertEqual(future[0]["status"], "future")
        imminent = build_timeline_view(
            sim_minutes=19.0,
            scenario_timeline=[{"simOffsetMinutes": 20, "event": "SCUD", "narrative": "SCUD"}],
            fired_offsets=set(),
            task_rows=[],
        )
        self.assertEqual(imminent["items"][0]["status"], "imminent")


if __name__ == "__main__":
    unittest.main()
