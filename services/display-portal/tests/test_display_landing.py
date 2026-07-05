"""Operator portal route registration tests."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from display_landing import (
    _http_probe,
    collect_portal_status,
    load_display_registry,
    load_monitoring_registry,
    render_landing_html,
)


class DisplayLandingTests(unittest.TestCase):
    def test_registry_has_three_displays(self) -> None:
        displays = load_display_registry()
        self.assertEqual(len(displays), 3)
        self.assertEqual({d["id"] for d in displays}, {"entity", "battlespace", "rf"})

    def test_monitoring_registry(self) -> None:
        mon = load_monitoring_registry()
        self.assertEqual({m["id"] for m in mon}, {"prometheus", "grafana"})

    def test_probe_offline(self) -> None:
        result = _http_probe("http://127.0.0.1:59999", "/health", timeout=0.2)
        self.assertEqual(result["status"], "offline")

    def test_collect_status_marks_current_display(self) -> None:
        with patch("display_landing._http_probe", return_value={"status": "offline", "detail": "mock"}):
            status = collect_portal_status(current_display="battlespace")
        current = [d for d in status["displays"] if d["is_current"]]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["id"], "battlespace")

    def test_render_html_includes_displays(self) -> None:
        status = {
            "generated_ms": 1,
            "summary": {"displays_live": 0, "displays_total": 3, "monitoring_live": 0, "monitoring_total": 2},
            "displays": load_display_registry(),
            "monitoring": load_monitoring_registry(),
        }
        html = render_landing_html(status)
        self.assertIn("Entity Display", html)
        self.assertIn("Prometheus", html)
        self.assertIn("Grafana", html)


if __name__ == "__main__":
    unittest.main()
