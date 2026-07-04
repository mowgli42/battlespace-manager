"""Tests for FSPL jam propagation."""

import unittest

from app.rf_propagation import fspl_db, jam_effective_coverage_nm, terrain_mask_factor


class RfPropagationTests(unittest.TestCase):
    def test_fspl_increases_with_distance(self) -> None:
        near = fspl_db(10, 9500)
        far = fspl_db(100, 9500)
        self.assertLess(near, far)

    def test_terrain_mask_low_altitude(self) -> None:
        self.assertLess(terrain_mask_factor(5000), terrain_mask_factor(35000))

    def test_jam_coverage_bounds(self) -> None:
        result = jam_effective_coverage_nm(frequency_mhz=9500, altitude_feet=35000)
        self.assertGreaterEqual(result["effective_coverage_nm"], 15)
        self.assertLessEqual(result["effective_coverage_nm"], 120)
        self.assertIn("fspl_at_effective_db", result)


if __name__ == "__main__":
    unittest.main()
