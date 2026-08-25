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
from uci_common.f2t2ea_messages import (  # noqa: E402
    F2t2eaState,
    TargetGenerated,
    build_f2t2ea_state_xml,
    build_target_generated_xml,
    history_entry,
)
from uci_common.notification_messages import ThreatNotification, build_threat_notification_xml  # noqa: E402
from uci_common.oms_state_messages import (  # noqa: E402
    OmsRouteState,
    OmsStateSnapshot,
    build_oms_state_xml,
)
from uci_common.platform_messages import PlatformStatusReport, build_platform_status_xml  # noqa: E402
from uci_common.route_messages import RouteDefinition, build_route_definition_xml  # noqa: E402
from uci_common.route_threat_messages import RouteThreatAssessment, build_route_threat_xml  # noqa: E402
from uci_common.sensing_messages import (  # noqa: E402
    CorrelatedEntity,
    CorrelationEvent,
    build_correlated_entity_xml,
    build_correlation_event_xml,
)
from uci_common.tasking_messages import TaskAllocation, TaskStatusMsg, build_task_status_xml, build_task_xml  # noqa: E402
from uci_common.topics import (  # noqa: E402
    TOPIC_CORRELATED_ENTITY,
    TOPIC_CORRELATION_EVENT,
    TOPIC_F2T2EA_STATE,
    TOPIC_OMS_STATE,
    TOPIC_PLATFORM_ROUTE,
    TOPIC_PLATFORM_STATUS,
    TOPIC_ROUTE_THREAT,
    TOPIC_TARGET_GENERATED,
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
        fusion = next(f for f in payload["feed_status"] if f["feed_id"] == "entity-fusion")
        self.assertTrue(fusion["active"])
        self.assertEqual(fusion["type"], "processor")
        self.assertEqual(fusion["role"], "correlation")
        self.assertGreater(fusion["tracks_last_tick"], 0)
        self.assertEqual(fusion["status"], "live")
        sorter = next(f for f in payload["feed_status"] if f["feed_id"] == "entity-sorter")
        self.assertFalse(sorter["active"])
        self.assertEqual(sorter["status"], "idle")
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

    def test_feed_status_always_lists_processors(self) -> None:
        snap = BusPictureState().snapshot()
        ids = [f["feed_id"] for f in snap["feed_status"]]
        self.assertEqual(ids[:2], ["entity-fusion", "entity-sorter"])
        for row in snap["feed_status"]:
            self.assertIn("type", row)
            self.assertIn("active", row)
            self.assertIn("tracks_last_tick", row)
            self.assertIn("role", row)

    def test_correlation_event_fills_fusion_rows_and_sensor_feed(self) -> None:
        state = BusPictureState()
        state.ingest(
            TOPIC_CORRELATED_ENTITY,
            build_correlated_entity_xml(
                CorrelatedEntity(
                    entity_id="ENT-1",
                    latitude=29.5,
                    longitude=47.5,
                    domain="AIR",
                    affiliation="OPFOR",
                    platform_type="SAM",
                    confidence=0.9,
                    contributor_track_ids=["T-1"],
                )
            ),
        )
        state.ingest(
            TOPIC_CORRELATION_EVENT,
            build_correlation_event_xml(
                CorrelationEvent(
                    event_type="ASSOCIATE",
                    track_id="T-1",
                    entity_id="ENT-1",
                    score=0.88,
                    source_feed="LINK16-TACTICAL",
                )
            ),
        )
        snap = state.snapshot()
        self.assertTrue(snap["fusion_rows"])
        self.assertEqual(snap["fusion_rows"][0]["kind"], "CORRELATION")
        self.assertEqual(snap["fusion_rows"][0]["source_feed"], "LINK16-TACTICAL")
        sensor = next(f for f in snap["feed_status"] if f["feed_id"] == "LINK16-TACTICAL")
        self.assertTrue(sensor["active"])
        self.assertEqual(sensor["type"], "sensor")

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

    def test_entity_registry_and_f2t2ea_from_correlated_opfor(self) -> None:
        state = BusPictureState()
        state.ingest(
            TOPIC_CORRELATED_ENTITY,
            build_correlated_entity_xml(
                CorrelatedEntity(
                    entity_id="ENT-HVT-SCUD-01",
                    latitude=29.1,
                    longitude=48.1,
                    domain="GROUND",
                    affiliation="OPFOR",
                    platform_type="SCUD_LAUNCHER",
                    confidence=0.99,
                    contributor_track_ids=["MTI-HVT-SCUD-01"],
                )
            ),
        )
        snap = state.snapshot()
        self.assertEqual(len(snap["entity_registry"]), 1)
        self.assertEqual(snap["entity_registry"][0]["entity_id"], "ENT-HVT-SCUD-01")
        self.assertIn("Find", snap["mission_thread"]["f2t2ea_phases"])
        self.assertGreaterEqual(len(snap["fkcm_targets"]), 1)
        self.assertEqual(snap["fkcm_targets"][0]["target_id"], "ENT-HVT-SCUD-01")

    def test_f2t2ea_state_and_generated_target_fill_kill_chain(self) -> None:
        state = BusPictureState()
        state.ingest(
            TOPIC_TARGET_GENERATED,
            build_target_generated_xml(
                TargetGenerated(
                    message_id="TGT-1",
                    target_id="tgt-scud-1",
                    source_assessment_id="asmt-1",
                    priority=1,
                    latitude=29.2,
                    longitude=47.8,
                    weaponeering="GBU-31",
                    collateral_estimate="low",
                )
            ),
        )
        state.ingest(
            TOPIC_F2T2EA_STATE,
            build_f2t2ea_state_xml(
                F2t2eaState(
                    message_id="F2-1",
                    target_id="tgt-scud-1",
                    current_phase="ENGAGE",
                    status="active",
                    history=[history_entry("FIND", "created")],
                )
            ),
        )
        snap = state.snapshot()
        self.assertEqual(snap["kill_chains"][0]["phase"], "Engage")
        self.assertEqual(snap["mission_thread"]["phase_counts"]["Engage"], 1)
        self.assertTrue(any(t["target_id"] == "tgt-scud-1" for t in snap["fkcm_targets"]))
        self.assertTrue(any(t["phase"] == "Engage" for t in snap["fkcm_targets"]))

    def test_oms_state_fills_route_geometries_and_platform_type(self) -> None:
        state = BusPictureState()
        state.ingest(
            TOPIC_PLATFORM_STATUS,
            build_platform_status_xml(
                PlatformStatusReport(
                    platform_id="COAL-F15C-01",
                    callsign="EAGLE01",
                    platform_type="F-15C",
                    latitude=28.5,
                    longitude=48.0,
                    fuel_percent=70.0,
                    weapons_remaining=4,
                    operational_role="CAP",
                    route_name="EAST_CAP",
                )
            ),
        )
        state.ingest(
            TOPIC_OMS_STATE,
            build_oms_state_xml(
                OmsStateSnapshot(
                    routes=[
                        OmsRouteState(
                            route_name="EAST_CAP",
                            source="derived",
                            platform_ids=["COAL-F15C-01"],
                            waypoints=[(28.4, 48.0), (28.6, 48.2), (28.5, 48.4)],
                        )
                    ]
                )
            ),
        )
        snap = state.snapshot()
        plat = snap["platforms"][0]
        self.assertEqual(plat["platform_type"], "F-15C")
        self.assertEqual(plat["operational_role"], "CAP")
        self.assertEqual(plat["affiliation"], "COALITION")
        self.assertIn("EAST_CAP", snap["route_geometries"])
        self.assertEqual(len(snap["route_geometries"]["EAST_CAP"]["waypoints"]), 3)

    def test_subscribes_oms_and_f2t2ea(self) -> None:
        topics = subscribe_topics()
        self.assertIn(TOPIC_OMS_STATE, topics)
        self.assertIn(TOPIC_F2T2EA_STATE, topics)
        self.assertIn(TOPIC_TARGET_GENERATED, topics)


if __name__ == "__main__":
    unittest.main()
