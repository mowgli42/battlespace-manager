"""Battlespace operator picture from UCI bus (no GulfWarEngine truth)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from uci_common.bus import RedisBus
from uci_common.messages import parse_categorized_entity_xml, parse_track_report_xml
from uci_common.platform_messages import parse_platform_status_xml
from uci_common.sensing_messages import parse_correlated_entity_xml, parse_correlation_event_xml
from uci_common.tasking_messages import parse_task_status_xml, parse_task_xml
from uci_common.topics import (
    TOPIC_CORRELATED_ENTITY,
    TOPIC_CORRELATION_EVENT,
    TOPIC_ENTITY,
    TOPIC_ENTITY_NOTIFICATION,
    TOPIC_PLATFORM_STATUS,
    TOPIC_TASK,
    TOPIC_TASK_STATUS,
)

logger = logging.getLogger("bus-picture")

try:
    from uci_common.gulfwar_sim.messages import parse_scenario_clock_xml
    from uci_common.topics import TOPIC_SCENARIO_CLOCK
except ImportError:
    TOPIC_SCENARIO_CLOCK = "uci.scenario.clock"

    def parse_scenario_clock_xml(xml_body: str) -> Any:
        raise ValueError("scenario clock parser unavailable")

try:
    from uci_common.gw_messages import parse_killchain_xml
    from uci_common.topics import TOPIC_KILLCHAIN
except ImportError:
    TOPIC_KILLCHAIN = "uci.killchain.state"

    def parse_killchain_xml(xml_body: str) -> Any:
        raise ValueError("killchain parser unavailable")

try:
    from uci_common.notification_messages import parse_threat_notification_xml, to_attention_kind
    from uci_common.route_messages import parse_route_definition_xml
    from uci_common.route_threat_messages import parse_route_threat_xml
    from uci_common.topics import TOPIC_PLATFORM_ROUTE, TOPIC_ROUTE_THREAT, TOPIC_THREAT_NOTIFICATION
except ImportError:
    TOPIC_ROUTE_THREAT = "uci.route.threat"
    TOPIC_THREAT_NOTIFICATION = "uci.threat.notification"
    TOPIC_PLATFORM_ROUTE = "uci.platform.route"

    def parse_route_threat_xml(xml_body: str) -> Any:
        raise ValueError("route threat parser unavailable")

    def parse_threat_notification_xml(xml_body: str) -> Any:
        raise ValueError("threat notification parser unavailable")

    def parse_route_definition_xml(xml_body: str) -> Any:
        raise ValueError("route definition parser unavailable")

    def to_attention_kind(kind: str) -> str:
        return {"TST": "TST", "BDA_REQUIRED": "TARGET"}.get(kind, "POPUP")


_URGENCY_RANK = {"immediate": 0, "priority": 1, "routine": 2}


class BusPictureState:
    """Accumulates bus messages into an operator picture snapshot."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sim_minutes = 0.0
        self._narrative = "Bus picture mode — o-my processors own fusion"
        self._entities: dict[str, dict[str, Any]] = {}
        self._entity_meta: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._kill_chains: dict[str, dict[str, Any]] = {}
        self._platforms: dict[str, dict[str, Any]] = {}
        self._correlation_events: list[dict[str, Any]] = []
        self._feed_ticks: dict[str, int] = {}
        self._route_threats: dict[str, dict[str, Any]] = {}
        self._attention: dict[str, dict[str, Any]] = {}
        self._route_geometries: dict[str, dict[str, Any]] = {}

    def ingest(self, channel: str, xml_body: str) -> None:
        try:
            with self._lock:
                if channel == TOPIC_SCENARIO_CLOCK:
                    self._sim_minutes = float(parse_scenario_clock_xml(xml_body).sim_minutes)
                elif channel == TOPIC_CORRELATED_ENTITY:
                    ent = parse_correlated_entity_xml(xml_body)
                    self._entities[ent.entity_id] = self._entity_from_correlated(ent)
                    self._feed_ticks["entity-fusion"] = self._feed_ticks.get("entity-fusion", 0) + 1
                elif channel == TOPIC_ENTITY:
                    tr = parse_track_report_xml(xml_body)
                    eid = tr.track_id
                    existing = self._entities.get(eid, {})
                    self._entities[eid] = {
                        **existing,
                        "entity_id": eid,
                        "latitude": tr.latitude,
                        "longitude": tr.longitude,
                        "altitude_feet": tr.altitude_feet,
                        "callsign": tr.callsign.strip(),
                        "sources": existing.get("sources", [tr.track_id]),
                    }
                    self._feed_ticks["entity-sorter"] = self._feed_ticks.get("entity-sorter", 0) + 1
                elif channel == TOPIC_ENTITY_NOTIFICATION:
                    cat = parse_categorized_entity_xml(xml_body)
                    eid = cat.original_track_id
                    meta = self._entity_meta.setdefault(eid, {})
                    meta.update(
                        {
                            "primary_category": cat.primary_category,
                            "sub_category": cat.sub_category,
                            "threat_level": cat.threat_level,
                            "tags": list(cat.tags),
                        }
                    )
                elif channel == TOPIC_CORRELATION_EVENT:
                    ev = parse_correlation_event_xml(xml_body)
                    self._correlation_events.append(
                        {
                            "event_type": ev.event_type,
                            "track_id": ev.track_id,
                            "entity_id": ev.entity_id,
                            "score": ev.score,
                            "source_feed": ev.source_feed,
                        }
                    )
                    self._correlation_events = self._correlation_events[-200:]
                elif channel == TOPIC_TASK:
                    task = parse_task_xml(xml_body)
                    prior = self._tasks.get(task.task_id, {})
                    self._tasks[task.task_id] = {
                        "task_id": task.task_id,
                        "target_entity_id": task.target_entity_id,
                        "assigned_platform_id": task.assigned_platform_id,
                        "role": task.role,
                        "priority": task.priority,
                        "status": prior.get("status", "assigned"),
                        "lifecycle_state": prior.get("lifecycle_state", "QUEUED"),
                        "latitude": task.latitude,
                        "longitude": task.longitude,
                        "route_name": task.route_name,
                        "required_weapon": task.required_weapon,
                        "is_time_sensitive": bool(task.time_sensitive),
                        "tst_minutes_remaining": float(task.tst_window_minutes or 0) or None,
                        "cost_nm": task.cost_nm or None,
                        "target_name": task.target_name or task.target_entity_id,
                        "target_type": task.target_type,
                    }
                elif channel == TOPIC_TASK_STATUS:
                    st = parse_task_status_xml(xml_body)
                    if st.task_id in self._tasks:
                        self._tasks[st.task_id]["status"] = st.status
                        self._tasks[st.task_id]["lifecycle_state"] = st.status
                        self._tasks[st.task_id]["reason"] = st.reason
                        if st.blocking_reasons:
                            self._tasks[st.task_id]["blocking_reasons"] = list(st.blocking_reasons)
                elif channel == TOPIC_KILLCHAIN:
                    kc = parse_killchain_xml(xml_body)
                    self._kill_chains[kc.target_entity_id] = {
                        "target_entity_id": kc.target_entity_id,
                        "target_name": kc.target_name,
                        "phase": kc.phase,
                        "active_task_id": kc.active_task_id,
                        "notes": kc.notes,
                    }
                elif channel == TOPIC_PLATFORM_STATUS:
                    plat = parse_platform_status_xml(xml_body)
                    self._platforms[plat.platform_id] = {
                        "platform_id": plat.platform_id,
                        "callsign": plat.callsign,
                        "latitude": plat.latitude,
                        "longitude": plat.longitude,
                        "readiness": plat.readiness,
                        "route_name": plat.route_name,
                    }
                elif channel == TOPIC_ROUTE_THREAT:
                    self._ingest_route_threat(parse_route_threat_xml(xml_body))
                elif channel == TOPIC_THREAT_NOTIFICATION:
                    self._ingest_threat_notification(parse_threat_notification_xml(xml_body))
                elif channel == TOPIC_PLATFORM_ROUTE:
                    route = parse_route_definition_xml(xml_body)
                    self._route_geometries[route.route_name] = {
                        "route_name": route.route_name,
                        "platform_id": route.platform_id,
                        "waypoints": [[lat, lon] for lat, lon in route.waypoints],
                        "description": route.description,
                    }
                    # Attach geometry to any matching live route threats.
                    for key, row in self._route_threats.items():
                        if row.get("route_name") == route.route_name and not row.get("waypoints"):
                            row["waypoints"] = [[lat, lon] for lat, lon in route.waypoints]
        except Exception:
            logger.exception("Bus picture ingest failed on %s", channel)

    def _ingest_route_threat(self, threat: Any) -> None:
        key = f"{threat.route_name}|{threat.threat_entity_id}"
        geom = self._route_geometries.get(threat.route_name) or {}
        waypoints = list(geom.get("waypoints") or [])
        row = {
            "assessment_id": threat.assessment_id,
            "route_name": threat.route_name,
            "threat_entity_id": threat.threat_entity_id,
            "closest_approach_nm": threat.closest_approach_nm,
            "severity": threat.severity,
            "classification": threat.classification,
            "threat_score": threat.threat_score,
            "platform_ids": list(threat.platform_ids),
            "task_ids": list(threat.task_ids),
            "recommended_action": threat.recommended_action,
            "latitude": threat.latitude,
            "longitude": threat.longitude,
            "time_to_closest_sec": threat.time_to_closest_sec,
            "waypoints": waypoints,
            "impacted_segment_count": max(0, len(waypoints) - 1) if waypoints else 0,
            "updated_at": time.time(),
        }
        self._route_threats[key] = row
        # Fallback attention cue when threat-notifier is offline.
        attn_id = f"route-threat-{key}"
        if attn_id not in self._attention:
            nm = threat.closest_approach_nm
            self._attention[attn_id] = {
                "id": attn_id,
                "priority": 0 if threat.severity in ("HIGH", "CRITICAL") else 1,
                "kind": "POPUP",
                "title": f"Route threat · {threat.route_name}",
                "detail": (
                    f"{threat.threat_entity_id} @ {nm:.1f} nm · {threat.severity}"
                    + (f" · {threat.recommended_action}" if threat.recommended_action else "")
                ),
                "entity_id": threat.threat_entity_id,
                "route_name": threat.route_name,
                "urgency": 0 if threat.severity in ("HIGH", "CRITICAL") else 1,
                "closest_approach_nm": nm,
            }

    def _ingest_threat_notification(self, note: Any) -> None:
        kind = to_attention_kind(note.kind)
        urgency = _URGENCY_RANK.get((note.urgency or "").lower(), 2)
        self._attention[note.notification_id] = {
            "id": note.notification_id,
            "priority": int(note.priority),
            "kind": kind,
            "title": note.title,
            "detail": note.detail,
            "entity_id": note.entity_id or None,
            "route_name": note.route_name or None,
            "urgency": urgency,
            "minutes_remaining": note.minutes_remaining if note.minutes_remaining >= 0 else None,
            "sim_minutes": note.sim_minutes if note.sim_minutes >= 0 else None,
        }

    @staticmethod
    def _entity_from_correlated(ent: Any) -> dict[str, Any]:
        return {
            "entity_id": ent.entity_id,
            "latitude": ent.latitude,
            "longitude": ent.longitude,
            "altitude_feet": 0.0,
            "domain": ent.domain,
            "affiliation": ent.affiliation,
            "platform_type": ent.platform_type,
            "confidence": ent.confidence,
            "sources": list(ent.contributor_track_ids),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            entities = []
            for eid, ent in self._entities.items():
                row = dict(ent)
                row.update(self._entity_meta.get(eid, {}))
                entities.append(row)
            tasks = list(self._tasks.values())
            kill_chains = list(self._kill_chains.values())
            platforms = list(self._platforms.values())
            sim = self._sim_minutes
            narrative = self._narrative
            corr = list(self._correlation_events)
            feed_status = [
                {"feed_id": fid, "label": fid, "message_count": count, "status": "live"}
                for fid, count in sorted(self._feed_ticks.items())
            ]
            route_threats = sorted(
                self._route_threats.values(),
                key=lambda r: float(r.get("closest_approach_nm") or 1e9),
            )
            # Ensure waypoints from geometry store when assessments arrived first.
            for row in route_threats:
                if not row.get("waypoints"):
                    geom = self._route_geometries.get(row.get("route_name") or "")
                    if geom and geom.get("waypoints"):
                        row["waypoints"] = list(geom["waypoints"])
                        row["impacted_segment_count"] = max(0, len(row["waypoints"]) - 1)
            attention_queue = sorted(
                self._attention.values(),
                key=lambda a: (int(a.get("urgency", 99)), int(a.get("priority", 99))),
            )
            route_geometries = dict(self._route_geometries)
        active_tasks = sum(
            1
            for t in tasks
            if str(t.get("status", "")).upper() not in ("COMPLETE", "CANCELLED", "ABORTED", "EXECUTED")
            and str(t.get("lifecycle_state", "")).upper() not in ("COMPLETE", "ABORTED", "EXECUTED")
        )
        plat_by_id = {p.get("platform_id"): p for p in platforms}
        task_rows = []
        for t in tasks:
            pid = t.get("assigned_platform_id", "")
            plat = plat_by_id.get(pid) or {}
            task_rows.append(
                {
                    "task_id": t.get("task_id", ""),
                    "target_entity_id": t.get("target_entity_id", ""),
                    "target_name": t.get("target_name") or t.get("target_entity_id", ""),
                    "target_type": t.get("target_type", ""),
                    "role": t.get("role", ""),
                    "priority": t.get("priority", 1),
                    "status": t.get("status", "assigned"),
                    "lifecycle_state": t.get("lifecycle_state") or t.get("status", "QUEUED"),
                    "platform_id": pid,
                    "assigned_platform_id": pid,
                    "platform_callsign": plat.get("callsign", ""),
                    "route_name": t.get("route_name") or plat.get("route_name", ""),
                    "required_weapon": t.get("required_weapon") or "",
                    "is_time_sensitive": bool(t.get("is_time_sensitive")),
                    "tst_minutes_remaining": t.get("tst_minutes_remaining"),
                    "cost_nm": t.get("cost_nm"),
                    "blocking_reasons": list(t.get("blocking_reasons") or []),
                    "notes": t.get("reason") or "",
                }
            )
        return {
            "sim_minutes": sim,
            "narrative": narrative,
            "entities": entities,
            "cues": [],
            "correlation_events": corr,
            "platforms": platforms,
            "tasks": tasks,
            "kill_chains": kill_chains,
            "fkcm_targets": [],
            "track_history": {},
            "threat_picture": {
                "entity_count": len(entities),
                "active_tasks": active_tasks,
                "route_threats": len(route_threats),
            },
            "fusion_rows": [],
            "task_rows": task_rows,
            "raw_tracks": [],
            "mission_thread": {"f2t2ea_phases": [], "phase_counts": {}},
            "entity_registry": [],
            "feed_status": feed_status,
            "attention_queue": attention_queue,
            "route_threats": route_threats,
            "route_geometries": route_geometries,
            "bda_items": [],
            "platform_context": platforms,
        }


_subscriber_started = False


def subscribe_topics() -> list[str]:
    return [
        TOPIC_SCENARIO_CLOCK,
        TOPIC_CORRELATED_ENTITY,
        TOPIC_CORRELATION_EVENT,
        TOPIC_ENTITY,
        TOPIC_ENTITY_NOTIFICATION,
        TOPIC_TASK,
        TOPIC_TASK_STATUS,
        TOPIC_KILLCHAIN,
        TOPIC_PLATFORM_STATUS,
        TOPIC_ROUTE_THREAT,
        TOPIC_THREAT_NOTIFICATION,
        TOPIC_PLATFORM_ROUTE,
    ]


def start_bus_picture_subscriber(state: BusPictureState, bus: RedisBus) -> None:
    global _subscriber_started
    if _subscriber_started:
        return
    topics = subscribe_topics()

    def _loop() -> None:
        logger.info("Bus picture subscribing to %s", ", ".join(topics))
        bus.subscribe(topics, state.ingest)

    threading.Thread(target=_loop, daemon=True).start()
    _subscriber_started = True
