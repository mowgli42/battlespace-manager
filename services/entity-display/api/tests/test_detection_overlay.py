"""Tests for detection overlay builder."""
from __future__ import annotations

import unittest

from app.detection_overlay import (
    build_detection_overlays,
    build_route_target_alerts,
    sample_platform_route,
)
from app.entity_harness import all_features_pass, build_harness_snapshot, verify_entity_features


class DetectionOverlayTests(unittest.TestCase):
    def test_sample_transit_route(self) -> None:
        platform = {
            "platformId": "TEST-01",
            "route": {
                "pattern": "transit",
                "waypoints": [
                    {"lat": 28.0, "lon": 48.0},
                    {"lat": 29.0, "lon": 48.5},
                ],
            },
        }
        pts = sample_platform_route(platform)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0], [28.0, 48.0])

    def test_route_target_alert_near_transit(self) -> None:
        doc = {
            "detection": {"route_buffer_nm": 10},
            "scenario": {
                "coalitionPlatforms": [
                    {
                        "platformId": "P1",
                        "callsign": "TEST",
                        "route": {
                            "pattern": "transit",
                            "name": "T",
                            "waypoints": [
                                {"lat": 28.0, "lon": 48.0},
                                {"lat": 29.0, "lon": 48.5},
                            ],
                        },
                    }
                ]
            },
            "targets": [{"target_id": "T1", "label": "HVT", "latitude": 28.5, "longitude": 48.2}],
        }
        alerts = build_route_target_alerts(doc)
        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["target_id"], "T1")

    def test_harness_overlays(self) -> None:
        snapshot = build_harness_snapshot()
        overlays = snapshot["overlays"]
        self.assertGreaterEqual(len(overlays["fog_zones"]), 2)
        self.assertGreaterEqual(len(overlays["route_corridors"]), 2)
        self.assertGreaterEqual(len(overlays["route_target_alerts"]), 1)

    def test_harness_verify_all_pass(self) -> None:
        snapshot = build_harness_snapshot()
        results = verify_entity_features(snapshot)
        self.assertTrue(all_features_pass(results))

    def test_undetected_not_in_tracks(self) -> None:
        snapshot = build_harness_snapshot()
        track_ids = {t["track_id"] for t in snapshot["tracks"]}
        self.assertNotIn("POPUP-SCUD-01", track_ids)

    def test_build_detection_overlays_summary(self) -> None:
        from app.entity_harness import load_harness_document

        doc = load_harness_document()
        overlays = build_detection_overlays(doc)
        self.assertIn("summary", overlays)
        self.assertGreater(overlays["summary"]["undetected_threat_count"], 0)


if __name__ == "__main__":
    unittest.main()
