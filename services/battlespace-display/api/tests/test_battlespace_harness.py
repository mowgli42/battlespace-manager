"""Battlespace display harness tests."""
from __future__ import annotations

import unittest

from app.battlespace_harness import (
    all_features_pass,
    assign_harness_task,
    build_harness_picture,
    load_harness_document,
    reset_harness_assignments,
    verify_battlespace_features,
)
from app.picture_contract import assert_picture_contract


class BattlespaceHarnessTests(unittest.TestCase):
    def test_build_harness_picture_contract(self) -> None:
        picture = build_harness_picture()
        assert_picture_contract(picture)
        self.assertTrue(picture.get("harness_mode"))

    def test_verify_all_features_pass(self) -> None:
        picture = build_harness_picture()
        results = verify_battlespace_features(picture)
        self.assertTrue(all_features_pass(results), results)

    def test_tst_and_unassigned_tasks(self) -> None:
        picture = build_harness_picture()
        tasks = picture.get("task_rows") or []
        tst = [t for t in tasks if t.get("is_time_sensitive") and t.get("lifecycle_state") != "EXECUTED"]
        unassigned = [
            t
            for t in tasks
            if not t.get("assigned_platform_id") and t.get("lifecycle_state") not in ("EXECUTED", "ABORTED")
        ]
        hp_unassigned = [t for t in unassigned if int(t.get("priority", 99)) <= 2]
        self.assertGreaterEqual(len(tst), 2)
        self.assertGreaterEqual(len(hp_unassigned), 2)

    def test_fkcm_f2t2ea_phases(self) -> None:
        picture = build_harness_picture()
        phases = {t.get("phase") for t in picture.get("fkcm_targets") or []}
        self.assertIn("Find", phases)
        self.assertIn("Target", phases)

    def test_timeline_view_built(self) -> None:
        picture = build_harness_picture()
        tv = picture.get("timeline_view") or {}
        self.assertIn("items", tv)
        self.assertGreaterEqual(tv.get("sim_minutes", 0), 20)

    def test_sample_oms_platforms_and_allocation(self) -> None:
        picture = build_harness_picture()
        platforms = picture.get("platforms") or []
        self.assertGreaterEqual(len(platforms), 6, "harness should ship sample OMS platforms")
        callsigns = {p.get("callsign") for p in platforms}
        self.assertIn("VIPER02", callsigns)
        self.assertIn("STRIKE01", callsigns)
        unassigned = [
            t
            for t in picture.get("task_rows") or []
            if not t.get("assigned_platform_id") and t.get("lifecycle_state") not in ("EXECUTED", "ABORTED")
        ]
        with_reco = [t for t in unassigned if t.get("recommended_platform_id")]
        self.assertGreaterEqual(len(with_reco), 2)
        attention = picture.get("attention_queue") or []
        self.assertTrue(any(a.get("task_id") and a.get("recommended_callsign") for a in attention))

    def test_full_psab_to_udeid_routes(self) -> None:
        picture = build_harness_picture()
        geoms = picture.get("route_geometries") or {}
        self.assertIn("CAS-LANE", geoms)
        psab = [24.0627, 47.5805]
        udeid = [25.1173, 51.3149]
        for name in ("CAP-BOX", "SEAD-BOX", "ORBIT-N", "CAS-LANE"):
            wps = (geoms.get(name) or {}).get("waypoints") or []
            self.assertGreaterEqual(len(wps), 10, name)
            self.assertEqual(wps[0], psab, name)
            self.assertEqual(wps[-1], udeid, name)
            self.assertEqual((geoms[name].get("origin") or "")[:4], "OEPS")
            self.assertIn("Udeid", geoms[name].get("destination") or "")
        threats = {r["route_name"]: r for r in picture.get("route_threats") or []}
        self.assertLessEqual(threats["CAP-BOX"]["closest_approach_nm"], 50)
        self.assertGreater(threats["SEAD-BOX"]["closest_approach_nm"], 50)
        self.assertGreater(threats["ORBIT-N"]["closest_approach_nm"], 100)

    def test_expected_features_in_fixture(self) -> None:
        doc = load_harness_document()
        self.assertIn("expected_features", doc)
        self.assertIn("picture", doc)

    def test_attention_tst_matches_task_tst_count(self) -> None:
        """Attention TST kinds and task_rows is_time_sensitive should agree at 3."""
        picture = build_harness_picture()
        tasks = picture.get("task_rows") or []
        tst_tasks = [
            t for t in tasks if t.get("is_time_sensitive") and t.get("lifecycle_state") != "EXECUTED"
        ]
        attn_tst = [a for a in (picture.get("attention_queue") or []) if a.get("kind") == "TST"]
        self.assertEqual(len(tst_tasks), 3)
        self.assertEqual(len(attn_tst), 3)
        self.assertEqual(
            {t["task_id"] for t in tst_tasks},
            {a["task_id"] for a in attn_tst},
        )

    def test_harness_assign_updates_task_and_attention(self) -> None:
        reset_harness_assignments()
        self.addCleanup(reset_harness_assignments)
        before = build_harness_picture()
        task = next(
            t
            for t in (before.get("task_rows") or [])
            if t.get("task_id") == "TSK-HARNESS-02"
        )
        self.assertFalse(task.get("assigned_platform_id"))
        assign_harness_task("TSK-HARNESS-02", "COAL-F15E-01", "STRIKE01")
        after = build_harness_picture()
        assigned = next(t for t in after["task_rows"] if t["task_id"] == "TSK-HARNESS-02")
        self.assertEqual(assigned["assigned_platform_id"], "COAL-F15E-01")
        self.assertEqual(assigned["platform_callsign"], "STRIKE01")
        self.assertEqual(assigned["lifecycle_state"], "ACCEPTED")
        self.assertFalse(
            any(
                a.get("task_id") == "TSK-HARNESS-02" and a.get("kind") in ("TST", "TASK")
                for a in after.get("attention_queue") or []
            )
        )


if __name__ == "__main__":
    unittest.main()
