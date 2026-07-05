"""Tests for live (dynamic) detection overlay builder."""
from __future__ import annotations

import unittest

from app.detection_overlay import build_dynamic_fog_zones, build_live_detection_overlays
from app.scenario_context import ground_truth_threats, load_scenario, scenario_path


_MINI_SCENARIO = {
    "bbox": {"centerLat": 29.75, "centerLon": 47.75},
    "coalitionPlatforms": [
        {
            "platformId": "COAL-E3-01",
            "callsign": "MAGIC01",
            "type": "E-3",
            "role": "AWACS",
            "orbit": {"lat": 30.2, "lon": 48.0, "radiusNm": 80},
            "capabilities": ["TRACK_FEED"],
        },
        {
            "platformId": "COAL-EF111-01",
            "callsign": "RAVEN01",
            "type": "EF-111",
            "route": {
                "pattern": "transit",
                "name": "SEAD",
                "waypoints": [
                    {"lat": 28.8, "lon": 47.5},
                    {"lat": 28.5, "lon": 48.0},
                    {"lat": 28.3, "lon": 48.4},
                ],
            },
        },
    ],
    "highValueTargets": [
        {
            "entityId": "HVT-SA6-01",
            "name": "SA-6",
            "affiliation": "OPFOR",
            "initialPosition": {"lat": 28.45, "lon": 48.35},
            "priority": 1,
        },
        {
            "entityId": "HVT-SCUD-01",
            "name": "Scud",
            "affiliation": "OPFOR",
            "initialPosition": {"lat": 29.1, "lon": 48.1},
            "priority": 1,
        },
    ],
    "timeline": [
        {
            "simOffsetMinutes": 14,
            "event": "POPUP_THREAT",
            "entityId": "POPUP-SCUD-02",
            "position": {"lat": 29.25, "lon": 47.65},
        }
    ],
}


class LiveDetectionOverlayTests(unittest.TestCase):
    def test_fog_zones_for_undetected_outside_coverage(self) -> None:
        threats = ground_truth_threats(_MINI_SCENARIO, sim_minutes=20.0)
        sensors = [
            {
                "latitude": 30.2,
                "longitude": 48.0,
                "coverage_radius_nm": 80,
                "online": True,
            }
        ]
        zones = build_dynamic_fog_zones(threats, detected_entity_ids=set(), sensors=sensors)
        self.assertGreaterEqual(len(zones), 1)
        for zone in zones:
            self.assertGreaterEqual(len(zone["polygon"]), 3)
            self.assertNotIn("latitude", zone)

    def test_no_fog_for_detected_threats(self) -> None:
        threats = ground_truth_threats(_MINI_SCENARIO, sim_minutes=20.0)
        detected = {t["threat_id"] for t in threats}
        zones = build_dynamic_fog_zones(threats, detected_entity_ids=detected, sensors=[])
        self.assertEqual(len(zones), 0)

    def test_live_overlays_with_platform_positions(self) -> None:
        overlays = build_live_detection_overlays(
            _MINI_SCENARIO,
            platforms_live={
                "COAL-E3-01": {"latitude": 30.2, "longitude": 48.0, "radar_online": True},
            },
            detected_entity_ids={"HVT-SA6-01"},
            sim_minutes=20.0,
        )
        self.assertGreaterEqual(overlays["summary"]["fog_zone_count"], 1)
        self.assertGreaterEqual(overlays["summary"]["route_corridor_count"], 1)
        self.assertTrue(overlays["summary"]["live_mode"])
        undetected = overlays["summary"]["undetected_threat_count"]
        self.assertGreaterEqual(undetected, 2)

    def test_route_alerts_only_for_detected_targets(self) -> None:
        overlays = build_live_detection_overlays(
            _MINI_SCENARIO,
            platforms_live={},
            detected_entity_ids={"HVT-SA6-01"},
            sim_minutes=20.0,
        )
        for alert in overlays["route_target_alerts"]:
            self.assertEqual(alert["target_id"], "HVT-SA6-01")

    def test_gulf_war_scenario_loads(self) -> None:
        if not scenario_path().is_file():
            self.skipTest(f"scenario missing: {scenario_path()}")
        scenario = load_scenario()
        self.assertIn("highValueTargets", scenario)
        overlays = build_live_detection_overlays(
            scenario,
            platforms_live={},
            detected_entity_ids=set(),
            sim_minutes=0.0,
        )
        self.assertGreater(overlays["summary"]["undetected_threat_count"], 0)


if __name__ == "__main__":
    unittest.main()
