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

    def test_aligned_tracks_per_aircraft_with_debrief_markers(self) -> None:
        view = build_timeline_view(
            sim_minutes=40.0,
            scenario_timeline=[{"simOffsetMinutes": 10, "event": "FEED_ON", "narrative": "AWACS live"}],
            fired_offsets={10},
            task_rows=[
                {
                    "task_id": "STK-1",
                    "role": "STRIKE",
                    "target_name": "SA-6",
                    "target_entity_id": "E-1",
                    "assigned_platform_id": "COAL-F15C-01",
                    "lifecycle_state": "QUEUED",
                    "first_seen_sim": 25,
                    "is_time_sensitive": True,
                    "tst_minutes_remaining": 8,
                    "priority": 0,
                },
                {
                    "task_id": "ISR-1",
                    "role": "ISR",
                    "target_name": "SCUD",
                    "target_entity_id": "E-2",
                    "assigned_platform_id": "COAL-U2-01",
                    "lifecycle_state": "QUEUED",
                    "first_seen_sim": 30,
                    "priority": 2,
                },
            ],
            platforms=[
                {
                    "platform_id": "COAL-F15C-01",
                    "callsign": "EAGLE01",
                    "platform_type": "F-15C",
                    "operational_role": "CAP",
                    "route_name": "EAST_CAP",
                    "active_task_id": "STK-1",
                },
                {
                    "platform_id": "COAL-U2-01",
                    "callsign": "DRAGON01",
                    "platform_type": "U-2",
                    "operational_role": "ISR",
                    "route_name": "HIGH_ISR_RACETRACK",
                },
            ],
            route_threats=[
                {
                    "assessment_id": "R1",
                    "route_name": "EAST_CAP",
                    "threat_entity_id": "POPUP-1",
                    "platform_ids": ["COAL-F15C-01"],
                    "severity": "HIGH",
                    "closest_approach_nm": 12.0,
                    "time_to_closest_sec": 180,
                    "recommended_action": "STRIKE",
                }
            ],
        )
        ids = [t["aircraft_id"] for t in view["tracks"]]
        self.assertIn("COAL-F15C-01", ids)
        self.assertIn("COAL-U2-01", ids)
        eagle = next(t for t in view["tracks"] if t["aircraft_id"] == "COAL-F15C-01")
        marks = {e["marker"] for e in eagle["events"]}
        self.assertIn("caret", marks)
        self.assertIn("circle", marks)
        strike = next(e for e in eagle["events"] if e["kind"] == "strike")
        # Queued TST sits on the upcoming side (NOW + remaining), not first_seen.
        self.assertGreater(strike["t_min"], 40)
        self.assertAlmostEqual(strike["t_min"], 48.0, places=1)
        threat = next(e for e in eagle["events"] if e["kind"] == "threat")
        self.assertGreater(threat["t_min"], 40)
        dragon = next(t for t in view["tracks"] if t["aircraft_id"] == "COAL-U2-01")
        self.assertTrue(any(e["marker"] == "diamond" for e in dragon["events"]))
        self.assertLessEqual(len(eagle["events"]), 12)
        self.assertAlmostEqual(view["axis_start_minutes"], 40.0 - 15.0, places=1)
        self.assertAlmostEqual(view["axis_max_minutes"], 40.0 + 45.0, places=1)
        self.assertEqual(view["past_fraction"], 0.25)
        self.assertIn(60, view["zoom_spans_minutes"])

    def test_dedups_flood_of_popup_strikes_on_one_jet(self) -> None:
        tasks = [
            {
                "task_id": f"popup-strike-{i}",
                "role": "STRIKE",
                "target_name": "SAME",
                "target_entity_id": "ENT-1",
                "assigned_platform_id": "COAL-F15C-02",
                "lifecycle_state": "QUEUED",
                "first_seen_sim": 10 + i,
                "priority": 1,
            }
            for i in range(80)
        ]
        view = build_timeline_view(
            sim_minutes=100.0,
            scenario_timeline=[],
            fired_offsets=set(),
            task_rows=tasks,
            platforms=[
                {
                    "platform_id": "COAL-F15C-02",
                    "callsign": "EAGLE02",
                    "platform_type": "F-15C",
                    "operational_role": "CAP",
                    "active_task_id": "popup-strike-79",
                }
            ],
        )
        eagle = view["tracks"][0]
        strikes = [e for e in eagle["events"] if e["kind"] == "strike"]
        self.assertEqual(len(strikes), 1)
        self.assertGreater(strikes[0]["t_min"], 100.0)
        self.assertLess(len(view["items"]), 20)

    def test_queued_task_without_eta_is_not_stacked_on_now(self) -> None:
        view = build_timeline_view(
            sim_minutes=200.0,
            scenario_timeline=[],
            fired_offsets=set(),
            task_rows=[
                {
                    "task_id": "STK-late",
                    "role": "STRIKE",
                    "target_name": "SA-6",
                    "target_entity_id": "E-9",
                    "assigned_platform_id": "COAL-F16C-01",
                    "lifecycle_state": "QUEUED",
                    "first_seen_sim": 10,
                    "priority": 1,
                }
            ],
            platforms=[
                {
                    "platform_id": "COAL-F16C-01",
                    "callsign": "VIPER01",
                    "platform_type": "F-16C",
                    "operational_role": "STRIKE",
                    "active_task_id": "STK-late",
                }
            ],
        )
        viper = next(t for t in view["tracks"] if t["aircraft_id"] == "COAL-F16C-01")
        strike = next(e for e in viper["events"] if e["kind"] == "strike")
        self.assertGreater(strike["t_min"], 200.0)


if __name__ == "__main__":
    unittest.main()
