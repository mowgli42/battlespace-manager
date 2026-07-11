"""ITU nine-band spectrum summary tests."""
from __future__ import annotations

import unittest

from app.rf_bands import band_for_frequency_mhz, build_spectrum_band_summary, load_itu_bands
from app.rf_picture_contract import build_rf_picture


class RfBandsTests(unittest.TestCase):
    def test_nine_itu_bands_loaded(self) -> None:
        bands = load_itu_bands()
        self.assertEqual(len(bands), 9)
        labels = [b["label"] for b in bands]
        self.assertIn("HF", labels)
        self.assertIn("UHF", labels)
        self.assertIn("SHF", labels)

    def test_band_for_l_band_satcom(self) -> None:
        band = band_for_frequency_mhz(1575.0)
        self.assertIsNotNone(band)
        assert band is not None
        self.assertEqual(band["label"], "UHF")

    def test_harness_picture_includes_band_summary(self) -> None:
        from app.rf_harness import build_harness_picture

        picture = build_harness_picture()
        summary = picture.get("spectrum_band_summary") or {}
        self.assertEqual(summary.get("band_count"), 9)
        self.assertGreater(summary.get("active_band_count", 0), 0)
        self.assertIsInstance(summary.get("interactions"), list)
        self.assertIsInstance(summary.get("bands"), list)

    def test_band_summary_builds_interaction_devices(self) -> None:
        columns = {
            "columns": [
                {
                    "id": "jammers",
                    "assets": [
                        {
                            "asset_id": "jam-1",
                            "column": "jammers",
                            "label": "EF-111",
                            "emitter_class": "jammer",
                            "affiliation": "friendly",
                            "frequency_mhz": 1616.0,
                            "bandwidth_mhz": 100.0,
                            "freq_low_mhz": 1566.0,
                            "freq_high_mhz": 1666.0,
                            "jamming_active": True,
                        }
                    ],
                },
                {
                    "id": "comm",
                    "assets": [
                        {
                            "asset_id": "sat-1",
                            "column": "comm",
                            "label": "SATCOM L",
                            "emitter_class": "comm",
                            "affiliation": "friendly",
                            "frequency_mhz": 1616.0,
                            "bandwidth_mhz": 2.0,
                            "freq_low_mhz": 1615.0,
                            "freq_high_mhz": 1617.0,
                        }
                    ],
                },
            ],
            "overlap_bands": [
                {
                    "frequency_mhz": 1616.0,
                    "freq_low_mhz": 1615.0,
                    "freq_high_mhz": 1617.0,
                    "columns": ["jammers", "comm"],
                    "asset_ids": ["jam-1", "sat-1"],
                    "endpoints": [
                        {"column": "jammers", "asset_id": "jam-1"},
                        {"column": "comm", "asset_id": "sat-1"},
                    ],
                    "conflict_type": "jam_comm",
                    "severity": "high",
                }
            ],
        }
        summary = build_spectrum_band_summary(columns)
        self.assertEqual(len(summary["interactions"]), 1)
        devices = summary["interactions"][0]["devices"]
        self.assertEqual(len(devices), 2)
        self.assertGreater(devices[0]["power_level"], devices[1]["power_level"])

    def test_band_summary_counts_uhf_activity(self) -> None:
        from app.rf_harness import build_harness_picture

        picture = build_harness_picture()
        uhf = next(
            b for b in (picture["spectrum_band_summary"]["bands"]) if b["band_id"] == "uhf"
        )
        self.assertGreater(uhf["occupant_count"], 0)


if __name__ == "__main__":
    unittest.main()
