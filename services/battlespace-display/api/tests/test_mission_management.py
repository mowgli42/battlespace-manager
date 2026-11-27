"""Phase 1 mission-management foundation tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.mission.auth import ActorContext
from app.mission.models import map_technical_readiness
from app.mission.service import MissionError, MissionService, reset_mission_service_for_tests
from app.mission.store import MissionStore

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED = REPO_ROOT / "fixtures" / "mission-management-seed-v1.json"


def _svc() -> MissionService:
    reset_mission_service_for_tests()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = MissionStore(tmp.name)
    svc = MissionService(store, stale_seconds=60)
    svc.ensure_seeded(SEED)
    return svc


SUPER = ActorContext(actor_id="OP-SUPER-1", role="mission_supervisor")
ANALYST = ActorContext(actor_id="AN-1", role="analyst")
ALPHA = ActorContext(actor_id="OP-ALPHA", role="operator")
BRAVO = ActorContext(actor_id="OP-BRAVO", role="operator")


class ReadinessMappingTests(unittest.TestCase):
    def test_map_readiness(self) -> None:
        self.assertEqual(map_technical_readiness("GREEN"), "Operational")
        self.assertEqual(map_technical_readiness("YELLOW"), "Degraded")
        self.assertEqual(map_technical_readiness("RED"), "Unavailable")
        self.assertEqual(map_technical_readiness(None), "Unknown")
        self.assertEqual(map_technical_readiness(""), "Unknown")


class OwnershipTests(unittest.TestCase):
    def test_operator_supports_multiple_aircraft_without_losing_primary(self) -> None:
        svc = _svc()
        alpha = svc.store.get_operator("OP-ALPHA")
        assert alpha is not None
        self.assertIn("COAL-F16C-01", alpha.primary_platform_ids)
        self.assertIn("COAL-F16C-02", alpha.support_platform_ids)
        self.assertIn("COAL-F15E-01", alpha.support_platform_ids)
        f15 = svc.store.get_platform("COAL-F15E-01")
        assert f15 is not None
        self.assertEqual(f15.primary_operator_id, "OP-STRIKE")
        self.assertIn("OP-ALPHA", f15.support_operator_ids)

    def test_each_active_platform_has_primary_team(self) -> None:
        svc = _svc()
        for plat in svc.store.list_platforms():
            self.assertTrue(plat.primary_team_id, plat.platform_id)

    def test_task_single_accountable_owner(self) -> None:
        svc = _svc()
        task = svc.store.get_task("TSK-M-SEAD-01")
        assert task is not None
        self.assertEqual(task.accountable_owner_id, "OP-ALPHA")
        self.assertNotIn("OP-ALPHA", task.supporting_operator_ids)
        self.assertIn("OP-BRAVO", task.supporting_operator_ids)


class ReassignmentTests(unittest.TestCase):
    def test_reassignment_awaits_acknowledgement(self) -> None:
        svc = _svc()
        result = svc.reassign_task(
            "TSK-M-SEAD-01",
            new_owner_id="OP-BRAVO",
            actor=SUPER,
            reason="workload balance",
            request_id="req-reassign-1",
        )
        task = svc.store.get_task("TSK-M-SEAD-01")
        assert task is not None
        self.assertEqual(task.accountable_owner_id, "OP-ALPHA")
        self.assertEqual(task.pending_owner_id, "OP-BRAVO")
        self.assertEqual(result["assignment"]["acknowledgement_status"], "pending")
        history = svc.store.list_assignments("TSK-M-SEAD-01")
        self.assertTrue(any(a.assignment_status == "superseded" for a in history))
        self.assertTrue(any(a.assignment_status == "pending_ack" for a in history))

        # Idempotent retry
        again = svc.reassign_task(
            "TSK-M-SEAD-01",
            new_owner_id="OP-BRAVO",
            actor=SUPER,
            reason="workload balance",
            request_id="req-reassign-1",
        )
        self.assertTrue(again["idempotent"])

        finalized = svc.acknowledge_task("TSK-M-SEAD-01", actor=BRAVO, accept=True)
        self.assertEqual(finalized.accountable_owner_id, "OP-BRAVO")
        self.assertEqual(finalized.pending_owner_id, "")
        self.assertEqual(finalized.status, "ACCEPTED")
        audit = svc.store.list_audit("task", "TSK-M-SEAD-01")
        self.assertTrue(any(e.event_type == "task.acknowledged" for e in audit))
        self.assertTrue(all(e.event_timestamp and e.received_timestamp for e in audit))

    def test_admin_override_transfers_immediately(self) -> None:
        svc = _svc()
        result = svc.reassign_task(
            "TSK-M-STRIKE-01",
            new_owner_id="OP-CAS",
            actor=SUPER,
            reason="override",
            admin_override=True,
            request_id="req-override-1",
        )
        self.assertEqual(result["task"]["accountable_owner_id"], "OP-CAS")
        self.assertEqual(result["assignment"]["assignment_status"], "active")


class CompletionEvidenceTests(unittest.TestCase):
    def test_completion_requires_evidence(self) -> None:
        svc = _svc()
        with self.assertRaises(MissionError):
            svc.complete_task("TSK-M-SEAD-01", actor=ALPHA, evidence="")
        done = svc.complete_task("TSK-M-SEAD-01", actor=ALPHA, evidence="BDA photo BDA-001")
        self.assertEqual(done.status, "COMPLETED")
        self.assertEqual(done.completion_evidence, "BDA photo BDA-001")


class FleetOverviewTests(unittest.TestCase):
    def test_committed_vs_reserve(self) -> None:
        svc = _svc()
        picture = {
            "harness_mode": True,
            "platforms": [
                {"platform_id": "COAL-F16C-01", "callsign": "VIPER01", "readiness": "GREEN", "active_task_id": "TSK-HARNESS-01"},
                {"platform_id": "COAL-KC135-01", "callsign": "TEXACO01", "readiness": "GREEN", "active_task_id": ""},
                {"platform_id": "COAL-A10-01", "callsign": "HOG01", "readiness": None, "stale": True},
            ],
        }
        fleet = svc.build_fleet_overview(picture)
        by_id = {r["platform_id"]: r for r in fleet["platforms"]}
        committed = by_id["COAL-F16C-01"]
        self.assertEqual(committed["technical_readiness"], "Operational")
        self.assertTrue(committed["operational_availability"]["committed"])
        self.assertEqual(committed["operational_availability"]["state"], "unavailable_for_additional")

        reserve = by_id["COAL-KC135-01"]
        self.assertEqual(reserve["technical_readiness"], "Operational")
        self.assertTrue(reserve["held_in_reserve"])
        self.assertEqual(reserve["operational_availability"]["state"], "available_reserved")
        self.assertFalse(reserve["operational_availability"]["committed"])

        unknown = by_id["COAL-A10-01"]
        self.assertEqual(unknown["technical_readiness"], "Unknown")
        self.assertTrue(unknown["stale"])

        self.assertGreaterEqual(fleet["counts"]["committed"], 1)
        self.assertGreaterEqual(fleet["counts"]["uncommitted_operational"], 1)
        self.assertGreaterEqual(fleet["counts"]["stale_telemetry"], 1)
        self.assertGreaterEqual(fleet["counts"]["unknown"], 1)

    def test_operator_workload_conflict_factors(self) -> None:
        svc = _svc()
        wl = svc.build_operator_workload("OP-ALPHA")
        self.assertIsNone(wl["workload_score"])
        self.assertIn("primary_aircraft", wl["factors"])
        self.assertTrue(wl["conflict_indicator"])
        self.assertGreaterEqual(len(wl["factors"]["supported_aircraft"]), 1)

    def test_mission_progress_criteria_based(self) -> None:
        svc = _svc()
        prog = svc.build_mission_progress("MSN-GULF-01")
        self.assertEqual(prog["milestone_completion"]["denominator"], 3)
        self.assertEqual(prog["milestone_completion"]["numerator"], 1)
        self.assertIn("criteria-based", prog["note"].lower())


class AlertAuditTests(unittest.TestCase):
    def test_ack_does_not_resolve(self) -> None:
        svc = _svc()
        alert = svc.acknowledge_alert("ALT-SEED-01", actor=SUPER)
        self.assertEqual(alert.acknowledgement_status, "acknowledged")
        self.assertEqual(alert.resolution_status, "open")


class AuthRouteTests(unittest.TestCase):
    def test_unauthorized_reassign_via_service_guard_is_route_level(self) -> None:
        # Route-level 403 is covered by FastAPI dependency; service still requires actor.
        from app.mission.auth import require_reassign
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            require_reassign(ANALYST)
        self.assertEqual(ctx.exception.status_code, 403)


class CompatContractNoteTests(unittest.TestCase):
    def test_seed_platform_ids_align_with_harness(self) -> None:
        """Contract: mission seed platform_ids must exist in battlespace harness fixture."""
        import json

        harness = json.loads((REPO_ROOT / "fixtures" / "battlespace-harness-scenario-v1.json").read_text())
        seed = json.loads(SEED.read_text())
        harness_ids = {p["platform_id"] for p in harness["picture"]["platforms"]}
        seed_ids = {p["platform_id"] for p in seed["platforms"]}
        self.assertTrue(seed_ids.issubset(harness_ids), seed_ids - harness_ids)


if __name__ == "__main__":
    unittest.main()
