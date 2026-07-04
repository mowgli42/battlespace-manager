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
        self.assertIn("deconfliction_summary", picture)


if __name__ == "__main__":
    unittest.main()
