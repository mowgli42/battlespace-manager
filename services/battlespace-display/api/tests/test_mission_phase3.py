"""Phase 3 performance intelligence tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.mission.auth import ActorContext
from app.mission.service import MissionService, reset_mission_service_for_tests
from app.mission.store import MissionStore

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED = REPO_ROOT / "fixtures" / "mission-management-seed-v1.json"
SUPER = ActorContext(actor_id="OP-SUPER-1", role="mission_supervisor")


def _svc() -> MissionService:
    reset_mission_service_for_tests()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    svc = MissionService(MissionStore(tmp.name), stale_seconds=60)
    svc.ensure_seeded(SEED)
    return svc


class UtilizationTests(unittest.TestCase):
    def test_utilization_excludes_reserve_from_denominator(self) -> None:
        svc = _svc()
        report = svc.build_utilization_report(
            start="2026-11-27T09:00:00Z", end="2026-11-27T12:00:00Z"
        )
        self.assertGreater(report["fleet"]["mission_assigned_minutes"], 0)
        self.assertGreater(report["fleet"]["operationally_available_minutes"], 0)
        self.assertGreater(report["uncommitted_operational_time"]["intentional_reserve_minutes"], 0)
        self.assertGreater(report["uncommitted_operational_time"]["minutes"], 0)
        self.assertIn("not classified as inefficiently", report["uncommitted_operational_time"]["note"])
        # F16 fully assigned; A10 uncommitted; KC reserve
        by_id = {p["platform_id"]: p for p in report["platforms"]}
        self.assertAlmostEqual(by_id["COAL-F16C-01"]["utilization"]["ratio"], 1.0)
        self.assertEqual(by_id["COAL-A10-01"]["utilization"]["ratio"], 0.0)
        self.assertEqual(by_id["COAL-KC135-01"]["operationally_available_minutes"], 0.0)
        self.assertGreater(by_id["COAL-KC135-01"]["intentional_reserve_minutes"], 0)
        self.assertGreater(report["fleet"]["stale_or_unknown_minutes"], 0)

    def test_record_sample(self) -> None:
        svc = _svc()
        before = len(svc.store.list_utilization_samples())
        result = svc.record_utilization_sample(
            {
                "harness_mode": True,
                "platforms": [
                    {"platform_id": "COAL-F16C-01", "readiness": "GREEN", "active_task_id": "X"},
                ],
            },
            actor=SUPER,
        )
        self.assertGreater(result["sample_count"], 0)
        self.assertGreater(len(svc.store.list_utilization_samples()), before)


class TaskMetricTests(unittest.TestCase):
    def test_on_time_and_delay_after_completion(self) -> None:
        svc = _svc()
        # Complete SEAD with evidence — due 14:00, complete "now" may be late relative to seed due
        svc.complete_task("TSK-M-SEAD-01", actor=ActorContext("OP-ALPHA", "operator"), evidence="BDA-OK")
        metrics = svc.build_task_metrics()
        self.assertIn("numerator", metrics["definition"])
        self.assertIn("denominator", metrics["definition"])
        self.assertGreaterEqual(metrics["on_time"]["denominator"], 1)
        self.assertTrue(any(d["task_id"] == "TSK-M-SEAD-01" for d in metrics["task_delay"]["items"]))


class MilestoneTests(unittest.TestCase):
    def test_milestone_analytics(self) -> None:
        svc = _svc()
        ms = svc.build_milestone_analytics("MSN-GULF-01")
        self.assertEqual(ms["aggregate"]["denominator"], 3)
        self.assertEqual(ms["aggregate"]["numerator"], 1)
        self.assertAlmostEqual(ms["aggregate"]["ratio"], 1 / 3)


class HealthTests(unittest.TestCase):
    def test_health_from_picture_not_invented(self) -> None:
        svc = _svc()
        health = svc.build_health_overview(
            {
                "platforms": [
                    {
                        "platform_id": "COAL-F16C-01",
                        "callsign": "VIPER01",
                        "readiness": "GREEN",
                        "fuel_percent": 74,
                        "weapons_remaining": 4,
                        "subsystems": {"jammer": "ONLINE", "weapons": "DEGRADED"},
                    },
                    {"platform_id": "COAL-A10-01", "readiness": None},
                ]
            }
        )
        by_id = {h["platform_id"]: h for h in health["platforms"]}
        self.assertEqual(by_id["COAL-F16C-01"]["technical_readiness"], "Operational")
        self.assertIn("weapons", by_id["COAL-F16C-01"]["degraded_sensors"])
        self.assertFalse(by_id["COAL-F16C-01"]["invented"])
        self.assertEqual(by_id["COAL-A10-01"]["technical_readiness"], "Unknown")
        self.assertEqual(by_id["COAL-A10-01"]["health_source"], "picture")
        # Platform with no picture row
        missing = next(h for h in health["platforms"] if h["platform_id"] == "COAL-E3-01")
        self.assertEqual(missing["health_source"], "missing")
        self.assertEqual(missing["subsystems"], {})


class PostFlightTests(unittest.TestCase):
    def test_post_flight_review(self) -> None:
        svc = _svc()
        review = svc.build_post_flight_review("MSN-GULF-01")
        self.assertEqual(review["mission"]["mission_id"], "MSN-GULF-01")
        self.assertGreaterEqual(review["summary"]["total_tasks"], 3)
        self.assertTrue(any(t["task_id"] == "TSK-M-CAS-01" and t["status"] == "BLOCKED" for t in review["task_reviews"]))
        self.assertIn("telemetry alone does not", review["note"].lower())


class BottleneckTests(unittest.TestCase):
    def test_bottlenecks_never_auto_assign(self) -> None:
        svc = _svc()
        result = svc.build_bottleneck_analysis(
            {
                "harness_mode": True,
                "platforms": [
                    {"platform_id": "COAL-F16C-01", "readiness": "GREEN", "active_task_id": "X"},
                    {
                        "platform_id": "COAL-EA18G-01",
                        "readiness": "YELLOW",
                        "subsystems": {"jammer": "FAULT"},
                    },
                ],
            }
        )
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(all(b["auto_action"] is None for b in result["bottlenecks"]))
        self.assertIn("never auto-assigns", result["note"].lower())
        kinds = {b["kind"] for b in result["bottlenecks"]}
        self.assertTrue({"operator_workload", "health"} & kinds or "blocked_task" in kinds)


if __name__ == "__main__":
    unittest.main()
