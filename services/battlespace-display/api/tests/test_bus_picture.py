"""Bus picture state tests."""

from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_OMY = os.path.join(_REPO, "..", "o-my", "packages", "uci_common", "src")
_OMYSIM = os.path.join(_REPO, "..", "o-my-sim", "packages", "uci_common", "src")
_API = os.path.join(_REPO, "services", "battlespace-display", "api")
for _p in (_OMY, _OMYSIM, _API):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from app.bus_picture import BusPictureState, subscribe_topics  # noqa: E402
from app.picture_contract import validate_picture  # noqa: E402
from uci_common.notification_messages import ThreatNotification, build_threat_notification_xml  # noqa: E402
from uci_common.route_messages import RouteDefinition, build_route_definition_xml  # noqa: E402
from uci_common.route_threat_messages import RouteThreatAssessment, build_route_threat_xml  # noqa: E402
from uci_common.sensing_messages import CorrelatedEntity, build_correlated_entity_xml  # noqa: E402
from uci_common.tasking_messages import TaskAllocation, TaskStatusMsg, build_task_status_xml, build_task_xml  # noqa: E402
from uci_common.topics import (  # noqa: E402
    TOPIC_CORRELATED_ENTITY,
    TOPIC_PLATFORM_ROUTE,
    TOPIC_ROUTE_THREAT,
    TOPIC_TASK,
    TOPIC_TASK_STATUS,
    TOPIC_THREAT_NOTIFICATION,
)


class BusPictureTests(unittest.TestCase):
    def test_correlated_entity_updates_picture(self) -> None:
        state = BusPictureState()
        ent = CorrelatedEntity(
            entity_id="ENT-1",
            latitude=29.5,
            longitude=47.5,
            domain="AIR",
            affiliation="OPFOR",
            platform_type="SAM",
            confidence=0.9,
            contributor_track_ids=["T-1"],
        )
        state.ingest(TOPIC_CORRELATED_ENTITY, build_correlated_entity_xml(ent))
        payload = state.snapshot()
        self.assertEqual(len(payload["entities"]), 1)
        self.assertEqual(payload["entities"][0]["entity_id"], "ENT-1")
        errors = validate_picture(
            {
                "sim_minutes": payload["sim_minutes"],
                "entities": payload["entities"],
                "threat_picture": payload["threat_picture"],
                "mission_thread": payload["mission_thread"],
                "attention_queue": payload["attention_queue"],
                "fkcm_targets": payload["fkcm_targets"],
                "timeline_view": {
                    "sim_minutes": payload["sim_minutes"],
                    "items": [],
                    "upcoming_count": 0,
                },
                "task_rows": payload["task_rows"],
            }
        )
        self.assertEqual(errors, [])

    def test_subscribes_route_threat_and_notification(self) -> None:
        topics = subscribe_topics()
        self.assertIn(TOPIC_ROUTE_THREAT, topics)
        self.assertIn(TOPIC_THREAT_NOTIFICATION, topics)
        self.assertIn(TOPIC_PLATFORM_ROUTE, topics)

    def test_platform_route_attaches_waypoints_to_threat(self) -> None:
        state = BusPictureState()
        state.ingest(
            TOPIC_PLATFORM_ROUTE,
            build_route_definition_xml(
                RouteDefinition(
                    route_name="CAP-BOX",
                    platform_id="F-15-01",
                    waypoints=[(28.5, 48.5), (29.0, 48.0), (29.2, 47.7)],
                )
            ),
        )
        state.ingest(
            TOPIC_ROUTE_THREAT,
            build_route_threat_xml(
                RouteThreatAssessment(
                    assessment_id="RTHR-1",
                    route_name="CAP-BOX",
                    threat_entity_id="POPUP-1",
                    closest_approach_nm=28.4,
                    severity="CRITICAL",
                    latitude=29.25,
                    longitude=47.65,
                )
            ),
        )
        snap = state.snapshot()
        self.assertEqual(len(snap["route_threats"][0]["waypoints"]), 3)
        self.assertIn("CAP-BOX", snap["route_geometries"])

    def test_route_threat_fills_list_and_attention(self) -> None:
        state = BusPictureState()
        threat = RouteThreatAssessment(
            assessment_id="RTHR-1",
            route_name="CAP-BOX",
            threat_entity_id="POPUP-1",
            closest_approach_nm=28.4,
            severity="CRITICAL",
            platform_ids=["F-15-01"],
            task_ids=["TSK-1"],
            recommended_action="STRIKE",
            latitude=29.2,
            longitude=47.6,
        )
        state.ingest(TOPIC_ROUTE_THREAT, build_route_threat_xml(threat))
        snap = state.snapshot()
        self.assertEqual(len(snap["route_threats"]), 1)
        self.assertEqual(snap["route_threats"][0]["route_name"], "CAP-BOX")
        self.assertEqual(snap["threat_picture"]["route_threats"], 1)
        self.assertTrue(any(a["kind"] == "POPUP" for a in snap["attention_queue"]))

    def test_threat_notification_maps_attention_kind(self) -> None:
        state = BusPictureState()
        note = ThreatNotification(
            notification_id="note-1",
            kind="ROUTE_THREAT",
            title="Route threat · CAP-BOX",
            detail="POPUP-1 @ 28.4 nm",
            entity_id="POPUP-1",
            route_name="CAP-BOX",
            priority=0,
            urgency="immediate",
        )
        state.ingest(TOPIC_THREAT_NOTIFICATION, build_threat_notification_xml(note))
        snap = state.snapshot()
        self.assertEqual(snap["attention_queue"][0]["kind"], "POPUP")
        self.assertEqual(snap["attention_queue"][0]["route_name"], "CAP-BOX")

    def test_task_rows_include_extended_fields(self) -> None:
        state = BusPictureState()
        task = TaskAllocation(
            task_id="popup-strike-1",
            target_entity_id="POPUP-1",
            assigned_platform_id="F-15-01",
            role="STRIKE",
            priority=0,
            route_name="CAP-BOX",
            time_sensitive=True,
            tst_window_minutes=15,
            cost_nm=28.4,
            target_name="Pop-up",
            target_type="POPUP_STRIKE",
            required_weapon="GBU-31",
        )
        state.ingest(TOPIC_TASK, build_task_xml(task))
        state.ingest(
            TOPIC_TASK_STATUS,
            build_task_status_xml(TaskStatusMsg(task_id=task.task_id, status="QUEUED")),
        )
        row = state.snapshot()["task_rows"][0]
        self.assertEqual(row["lifecycle_state"], "QUEUED")
        self.assertTrue(row["is_time_sensitive"])
        self.assertEqual(row["cost_nm"], 28.4)
        self.assertEqual(row["route_name"], "CAP-BOX")
        self.assertEqual(row["target_type"], "POPUP_STRIKE")


if __name__ == "__main__":
    unittest.main()
