"""FastAPI route tests for RF display."""

from __future__ import annotations

import os
import unittest

try:
    from fastapi.testclient import TestClient  # noqa: E402

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

if _HAS_FASTAPI:
    os.environ.setdefault("RF_HARNESS", "1")
    os.environ.setdefault("REDIS_URL", "memory://")
    from app.main import app  # noqa: E402


@unittest.skipUnless(_HAS_FASTAPI, "fastapi not installed")
class RfApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_harness_mode(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertTrue(body.get("harness_mode"))

    def test_picture_has_spectrum_columns(self) -> None:
        resp = self.client.get("/api/picture")
        self.assertEqual(200, resp.status_code)
        picture = resp.json()
        self.assertEqual(4, len(picture["spectrum_columns"]["columns"]))

    def test_harness_verify_passes(self) -> None:
        resp = self.client.get("/api/harness/verify")
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertTrue(body["passed"], body.get("checks"))

    def test_geo_filter_circle(self) -> None:
        resp = self.client.post(
            "/api/geo-filter",
            json={
                "type": "circle",
                "active": True,
                "label": "test",
                "geometry": {"center_lat": 28.45, "center_lon": 48.35, "radius_nm": 10},
            },
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual("ok", resp.json()["status"])
        picture = self.client.get("/api/picture").json()
        self.assertTrue(picture["geo_filter_summary"]["active"])
        self.client.delete("/api/geo-filter")


if __name__ == "__main__":
    unittest.main()
