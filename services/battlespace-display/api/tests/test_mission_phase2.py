"""Phase 2 resource-management tests."""

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


class TeamConsoleTests(unittest.TestCase):
    def test_team_console_separates_primary_and_support(self) -> None:
        svc = _svc()
        console = svc.build_team_console("TEAM-SEAD")
        primary_ids = {p["platform_id"] for p in console["primary_aircraft"]}
        self.assertIn("COAL-F16C-01", primary_ids)
        self.assertTrue(console["primary_operators"])
        self.assertIn("active_tasks", console["workload"])
        self.assertIsNone(console["workload"]["workload_score"])
        self.assertIn("Primary ownership", console["note"])

    def test_supporting_operator_keeps_primary_visibility(self) -> None:
        svc = _svc()
        console = svc.build_team_console("TEAM-SEAD")
        alpha = next(m for m in console["members"] if m["operator"]["operator_id"] == "OP-ALPHA")
        self.assertIn("COAL-F16C-01", alpha["factors"]["primary_aircraft"])
        self.assertGreaterEqual(len(alpha["factors"]["supported_aircraft"]), 1)


class TeamComparisonTests(unittest.TestCase):
    def test_teams_overview_relative_load(self) -> None:
        svc = _svc()
        overview = svc.build_teams_overview()
        self.assertGreaterEqual(len(overview["teams"]), 3)
        self.assertIn("median_active_tasks", overview)
        for t in overview["teams"]:
            self.assertIn(t["relative_load"], ("higher", "lower", "typical"))
            self.assertIsNone(t["workload"]["workload_score"])


class OperatorWorkloadOverviewTests(unittest.TestCase):
    def test_operators_workload_overview(self) -> None:
        svc = _svc()
        ow = svc.build_operators_workload_overview()
        self.assertGreaterEqual(ow["conflict_count"], 1)
        self.assertIsNone(ow["workload_score"])
        alpha = next(r for r in ow["operators"] if r["operator"]["operator_id"] == "OP-ALPHA")
        self.assertTrue(alpha["conflict_indicator"])


class CommitmentsTests(unittest.TestCase):
    def test_platform_commitments_and_availability(self) -> None:
        svc = _svc()
        picture = {
            "harness_mode": True,
            "platforms": [
                {
                    "platform_id": "COAL-F16C-01",
                    "readiness": "GREEN",
                    "active_task_id": "TSK-HARNESS-01",
                },
                {"platform_id": "COAL-KC135-01", "readiness": "GREEN", "active_task_id": ""},
                {"platform_id": "COAL-F15E-01", "readiness": "GREEN", "active_task_id": ""},
            ],
        }
        committed = svc.build_platform_commitments("COAL-F16C-01", picture)
        self.assertEqual(committed["operational_availability"]["state"], "unavailable_for_additional")
        self.assertFalse(committed["operational_availability"]["can_accept_additional"])

        reserve = svc.build_platform_commitments("COAL-KC135-01", picture)
        self.assertEqual(reserve["operational_availability"]["state"], "available_reserved")
        self.assertTrue(reserve["operational_availability"]["can_accept_additional"])

        strike = svc.build_platform_commitments("COAL-F15E-01", picture)
        self.assertTrue(any(c.get("status") == "scheduled" for c in strike["scheduled_commitments"]))
        self.assertEqual(strike["operational_availability"]["estimated_available_at"], "2026-11-27T16:15:00Z")

    def test_upsert_commitment_audited(self) -> None:
        svc = _svc()
        entry = svc.upsert_platform_commitment(
            "COAL-A10-01",
            {
                "label": "CAS stack",
                "kind": "scheduled",
                "status": "scheduled",
                "estimated_available_at": "2026-11-27T17:00:00Z",
                "reason": "phase2 test",
            },
            actor=SUPER,
        )
        self.assertTrue(entry["commitment_id"])
        detail = svc.build_platform_commitments("COAL-A10-01")
        self.assertTrue(any(c["commitment_id"] == entry["commitment_id"] for c in detail["scheduled_commitments"]))
        audit = svc.store.list_audit("platform", "COAL-A10-01")
        self.assertTrue(any(e.event_type == "platform.commitment_upserted" for e in audit))


class ConflictsTests(unittest.TestCase):
    def test_resource_conflicts_include_blocked_and_workload(self) -> None:
        svc = _svc()
        result = svc.build_resource_conflicts(
            {
                "harness_mode": True,
                "platforms": [
                    {"platform_id": "COAL-F16C-01", "readiness": "GREEN", "active_task_id": "X"},
                    {"platform_id": "COAL-A10-01", "readiness": None, "stale": True},
                ],
            }
        )
        kinds = {c["kind"] for c in result["conflicts"]}
        self.assertIn("operator_workload", kinds)
        self.assertIn("blocked_task", kinds)
        self.assertTrue(all(c["auto_action"] is None for c in result["conflicts"]))
        self.assertIn("never auto-assigns", result["note"].lower())


class MissionProgressPhase2Tests(unittest.TestCase):
    def test_enriched_progress_has_dependencies(self) -> None:
        svc = _svc()
        prog = svc.build_mission_progress("MSN-GULF-01")
        self.assertIn("dependencies", prog)
        self.assertIn("resource_constraints", prog)
        self.assertGreaterEqual(prog["task_counts"]["blocked"], 1)
        self.assertTrue(any("TSK-M-SEAD-01" in (d.get("reason") or "") for d in prog["dependencies"]))


if __name__ == "__main__":
    unittest.main()
