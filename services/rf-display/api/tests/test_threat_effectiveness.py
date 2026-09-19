"""Threat registry, BDA suppression, and jam stand-down tests."""

from __future__ import annotations

import unittest

from app.rf_harness import build_harness_picture
from app.threat_effectiveness import (
    apply_jam_standdown,
    build_threat_registry,
    filter_emitters_by_threat_registry,
    load_opzone_catalog,
    opzone_to_geo_filter,
    threat_summary,
)


class ThreatEffectivenessTests(unittest.TestCase):
    def test_harness_suppresses_destroyed_threat(self) -> None:
        picture = build_harness_picture()
        suppressed_ids = {row["entity_id"] for row in picture.get("suppressed_threats") or []}
        self.assertIn("HVT-SA6-02", suppressed_ids)
        visible_ids = {
            e.get("target_entity_id") or e.get("emitter_id")
            for e in picture.get("emitters") or []
        }
        self.assertNotIn("HVT-SA6-02", visible_ids)
        self.assertGreaterEqual(picture["threat_summary"]["active"], 1)
        self.assertGreaterEqual(picture["threat_summary"]["suppressed"], 1)

    def test_jam_stays_active_with_overlapping_threat(self) -> None:
        picture = build_harness_picture()
        jammers = picture.get("ew_platforms") or []
        self.assertTrue(any(j.get("jamming_active") for j in jammers))

    def test_jam_standdown_without_overlap(self) -> None:
        emitters = [
            {
                "emitter_id": "radar-1",
                "emitter_class": "radar",
                "emitter_type": "RADAR",
                "frequency_mhz": 5400,
                "bandwidth_mhz": 50,
            }
        ]
        jammers = [
            {
                "platform_id": "jam-1",
                "jamming_active": True,
                "frequency_mhz": 1616,
                "bandwidth_mhz": 100,
            }
        ]
        updated = apply_jam_standdown(jammers, emitters)
        self.assertFalse(updated[0]["jamming_active"])
        self.assertEqual(updated[0]["jam_standdown_reason"], "no_active_threats_in_band")

    def test_opzone_catalog_and_geo_filter(self) -> None:
        zones = load_opzone_catalog()
        self.assertGreaterEqual(len(zones), 1)
        gf = opzone_to_geo_filter(zones[0])
        self.assertTrue(gf["active"])
        self.assertIn("geometry", gf)

    def test_out_of_opzone_status(self) -> None:
        emitters = [
            {
                "emitter_id": "e1",
                "target_entity_id": "T-1",
                "label": "Remote radar",
                "emitter_type": "RADAR",
                "frequency_mhz": 3000,
                "latitude": 35.0,
                "longitude": 50.0,
            }
        ]
        geo_filter = {
            "type": "polygon",
            "active": True,
            "geometry": {
                "polygon": [[27.0, 46.0], [27.0, 49.0], [30.0, 49.0], [30.0, 46.0]],
            },
        }
        registry = build_threat_registry(emitters=emitters, geo_filter=geo_filter)
        self.assertEqual(registry[0]["effective_status"], "out_of_opzone")
        visible, suppressed = filter_emitters_by_threat_registry(emitters, registry)
        self.assertEqual(len(visible), 0)
        self.assertEqual(len(suppressed), 1)
        summary = threat_summary(registry)
        self.assertEqual(summary["out_of_opzone"], 1)


if __name__ == "__main__":
    unittest.main()
