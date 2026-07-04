import unittest

from app.rf_deconfliction import detect_rf_conflicts
from app.rf_picture_contract import assert_rf_picture_contract, build_rf_picture, validate_rf_picture


class RfDeconflictionTests(unittest.TestCase):
    def test_jam_comm_overlap(self) -> None:
        conflicts = detect_rf_conflicts(
            comm_links=[
                {
                    "link_id": "lnk-sat",
                    "frequency_mhz": 1616.0,
                    "bandwidth_mhz": 0.042,
                    "status": "active",
                    "type": "satcom",
                }
            ],
            emitters=[],
            ew_platforms=[
                {
                    "platform_id": "COAL-EF111-01",
                    "callsign": "RAVEN01",
                    "frequency_mhz": 1616.0,
                    "bandwidth_mhz": 50,
                    "jamming_active": True,
                }
            ],
            emcon_areas=[],
        )
        types = {c["conflict_type"] for c in conflicts}
        self.assertIn("jam_comm", types)

    def test_jrfl_violation_on_protected_band(self) -> None:
        conflicts = detect_rf_conflicts(
            comm_links=[],
            emitters=[],
            ew_platforms=[
                {
                    "platform_id": "COAL-EF111-01",
                    "callsign": "RAVEN01",
                    "frequency_mhz": 1616.0,
                    "bandwidth_mhz": 50,
                    "jamming_active": True,
                    "task_role": "EW_SUPPORT",
                }
            ],
            emcon_areas=[],
            jrfl_entries=[
                {
                    "id": "jrfl-1",
                    "frequency_mhz": 1616.0,
                    "bandwidth_mhz": 0.042,
                    "restriction": "NO_EA",
                    "label": "SATCOM L",
                }
            ],
            ea_authority={"authorized_roles": ["SEAD"]},
        )
        self.assertTrue(any(c["conflict_type"] == "jrfl_violation" for c in conflicts))

    def test_emcon_radar_violation(self) -> None:
        conflicts = detect_rf_conflicts(
            comm_links=[],
            emitters=[
                {
                    "emitter_id": "rad-1",
                    "emitter_type": "SA-6_FIRE_CONTROL_RADAR",
                    "emitter_class": "radar",
                    "latitude": 27.5,
                    "longitude": 48.4,
                    "label": "SA-6",
                }
            ],
            ew_platforms=[],
            emcon_areas=[
                {
                    "id": "emcon-1",
                    "name": "Test EMCON",
                    "posture": "EMCON_ALPHA",
                    "restrictions": ["no_radar"],
                    "polygon": [[27.0, 48.0], [28.0, 48.0], [28.0, 49.0], [27.0, 49.0]],
                }
            ],
        )
        self.assertTrue(any(c["conflict_type"] == "emcon_violation" for c in conflicts))

    def test_jam_support_overlap(self) -> None:
        conflicts = detect_rf_conflicts(
            comm_links=[],
            emitters=[],
            ew_platforms=[
                {
                    "platform_id": "COAL-EF111-01",
                    "callsign": "RAVEN01",
                    "frequency_mhz": 1575.0,
                    "bandwidth_mhz": 50,
                    "jamming_active": True,
                }
            ],
            emcon_areas=[],
            support_assets=[
                {
                    "asset_id": "GPS_L1",
                    "label": "GPS L1",
                    "frequency_mhz": 1575.42,
                    "bandwidth_mhz": 2.046,
                    "support_kind": "gps",
                }
            ],
        )
        self.assertTrue(any(c["conflict_type"] == "jam_support" for c in conflicts))


class RfPictureContractTests(unittest.TestCase):
    def test_minimal_picture_contract(self) -> None:
        picture = build_rf_picture(
            sim_minutes=12.0,
            commlink_display={"links": [], "contacts": [], "reservations": [], "summary": {}},
            directory_links=[],
            engine_snapshot=None,
            scenario={"coalitionPlatforms": []},
        )
        self.assertEqual([], validate_rf_picture(picture))
        assert_rf_picture_contract(picture)
        self.assertIn("spectrum", picture)
        self.assertIn("spectrum_columns", picture)
        self.assertIn("support_assets", picture)
        self.assertIn("deconfliction_summary", picture)
        cols = picture["spectrum_columns"]
        self.assertEqual(4, len(cols["columns"]))
        col_ids = {c["id"] for c in cols["columns"]}
        self.assertEqual({"threat_radars", "jammers", "comm", "support"}, col_ids)
        self.assertGreaterEqual(len(picture["support_assets"]), 2)

    def test_spectrum_columns_with_gps_and_scenario(self) -> None:
        picture = build_rf_picture(
            sim_minutes=5.0,
            commlink_display={"links": [], "contacts": [], "reservations": [], "summary": {}},
            directory_links=[],
            engine_snapshot=None,
            scenario={
                "coalitionPlatforms": [
                    {
                        "platformId": "COAL-E3-01",
                        "callsign": "MAGIC01",
                        "type": "E-3",
                        "role": "AWACS",
                        "orbit": {"lat": 30.2, "lon": 48.0},
                    }
                ]
            },
        )
        support_ids = {a["asset_id"] for a in picture["support_assets"]}
        self.assertIn("GPS_L1", support_ids)
        self.assertTrue(any(a.startswith("COAL-E3-01") for a in support_ids))
        support_col = next(c for c in picture["spectrum_columns"]["columns"] if c["id"] == "support")
        self.assertGreaterEqual(len(support_col["assets"]), 2)


if __name__ == "__main__":
    unittest.main()
