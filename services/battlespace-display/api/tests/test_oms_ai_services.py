"""OMS AI service registry and probe tests."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.oms_ai_services import (
    load_service_registry,
    merge_oms_attention,
    probe_service,
    refresh_oms_ai_services,
)


class OmsAiServicesTests(unittest.TestCase):
    def test_registry_includes_mission_advisor(self) -> None:
        reg = load_service_registry()
        ids = {s["service_id"] for s in reg}
        self.assertIn("mission-advisor", ids)
        self.assertIn("task-allocator", ids)

    def test_probe_offline_service(self) -> None:
        spec = next(s for s in load_service_registry() if s["service_id"] == "mission-advisor")
        with patch("app.oms_ai_services._http_get_json", side_effect=OSError("connection refused")):
            row = probe_service({**spec, "default_url": "http://127.0.0.1:59999"})
        self.assertEqual(row["status"], "offline")

    def test_probe_live_mission_advisor(self) -> None:
        spec = next(s for s in load_service_registry() if s["service_id"] == "mission-advisor")

        def fake_get(url: str, timeout: float = 1.5):
            if url.endswith("/health"):
                return {"status": "ok", "service": "mission-advisor"}
            return {
                "suggestions": [{"suggestion_id": "s1", "status": "open", "target_entity_id": "T1"}],
                "isr_assignments": [],
            }

        with patch("app.oms_ai_services.load_service_registry", return_value=[spec]):
            with patch("app.oms_ai_services._http_get_json", side_effect=fake_get):
                services, sugs, _isr, summary = refresh_oms_ai_services(None, dedup_keys=set())
        advisor = next(s for s in services if s["service_id"] == "mission-advisor")
        self.assertEqual(advisor["status"], "live")
        self.assertEqual(len(sugs), 1)
        self.assertTrue(summary["any_live"])

    def test_no_recommendations_when_all_offline(self) -> None:
        with patch("app.oms_ai_services.probe_service", return_value={"service_id": "x", "status": "offline"}):
            with patch("app.oms_ai_services.load_service_registry", return_value=[{"service_id": "x"}]):
                _, sugs, _, summary = refresh_oms_ai_services(None)
        self.assertEqual(sugs, [])
        self.assertFalse(summary["any_live"])

    def test_merge_attention_only_when_live(self) -> None:
        queue = [{"id": "t1", "kind": "TASK", "priority": 1, "urgency": 1}]
        sugs = [{"suggestion_id": "s1", "suggested_role": "STRIKE", "target_entity_id": "T1", "priority": 1}]
        merged = merge_oms_attention(queue, sugs, services_live=True)
        self.assertTrue(any(i.get("kind") == "AGENT" for i in merged))
        unchanged = merge_oms_attention(queue, sugs, services_live=False)
        self.assertEqual(len(unchanged), 1)
        self.assertEqual(unchanged[0]["kind"], "TASK")


if __name__ == "__main__":
    unittest.main()
