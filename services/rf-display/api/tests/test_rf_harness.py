"""RF harness and geo filter tests."""

from __future__ import annotations

import unittest

from app.geo_filter import (
    apply_geo_filter,
    geo_filter_matches,
    point_in_circle,
    point_in_polygon,
    point_near_route,
    validate_geo_filter,
)
from app.rf_harness import all_features_pass, build_harness_picture, verify_rf_features


class GeoFilterTests(unittest.TestCase):
    def test_point_in_circle(self) -> None:
        self.assertTrue(point_in_circle(28.5, 48.0, 28.5, 48.0, 10))
        self.assertFalse(point_in_circle(30.0, 48.0, 28.5, 48.0, 5))

    def test_point_in_polygon(self) -> None:
        square = [[27.0, 48.0], [29.0, 48.0], [29.0, 49.0], [27.0, 49.0]]
        self.assertTrue(point_in_polygon(28.0, 48.5, square))
        self.assertFalse(point_in_polygon(26.0, 48.5, square))

    def test_point_near_route(self) -> None:
        route = [[28.0, 48.0], [29.0, 48.5]]
        self.assertTrue(point_near_route(28.5, 48.2, route, 15))
        self.assertFalse(point_near_route(28.5, 50.0, route, 1))

    def test_validate_geo_filter(self) -> None:
        errors = validate_geo_filter(
            {
                "type": "circle",
                "active": True,
                "geometry": {"center_lat": 28.5, "center_lon": 48.0, "radius_nm": 20},
            }
        )
        self.assertEqual([], errors)

    def test_apply_geo_filter_reduces_emitters(self) -> None:
        picture = build_harness_picture()
        before = len(picture["emitters"])
        filtered = apply_geo_filter(
            picture,
            {
                "type": "circle",
                "active": True,
                "label": "Remote box",
                "geometry": {"center_lat": 30.0, "center_lon": 50.0, "radius_nm": 5},
            },
        )
        self.assertLess(len(filtered["emitters"]), before)
        self.assertTrue(filtered["geo_filter_summary"]["active"])


class RfHarnessTests(unittest.TestCase):
    def test_harness_picture_contract(self) -> None:
        picture = build_harness_picture()
        self.assertIn("spectrum_columns", picture)
        self.assertEqual(4, len(picture["spectrum_columns"]["columns"]))

    def test_all_features_pass(self) -> None:
        picture = build_harness_picture()
        results = verify_rf_features(picture)
        self.assertTrue(all_features_pass(results), results)

    def test_geo_filter_matches_helper(self) -> None:
        gf = {
            "type": "polygon",
            "active": True,
            "geometry": {
                "polygon": [[27.0, 48.0], [29.0, 48.0], [29.0, 49.0], [27.0, 49.0]],
            },
        }
        self.assertTrue(geo_filter_matches(28.45, 48.35, gf))


if __name__ == "__main__":
    unittest.main()
