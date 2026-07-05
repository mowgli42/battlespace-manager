"""Battlespace display harness tests."""
from __future__ import annotations

import unittest

from app.battlespace_harness import (
    all_features_pass,
    build_harness_picture,
    load_harness_document,
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

    def test_expected_features_in_fixture(self) -> None:
        doc = load_harness_document()
        self.assertIn("expected_features", doc)
        self.assertIn("picture", doc)


if __name__ == "__main__":
    unittest.main()
