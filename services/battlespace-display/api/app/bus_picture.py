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
                    self._tasks[task.task_id] = {
                        "task_id": task.task_id,
                        "target_entity_id": task.target_entity_id,
                        "assigned_platform_id": task.assigned_platform_id,
                        "role": task.role,
                        "priority": task.priority,
                        "status": self._tasks.get(task.task_id, {}).get("status", "assigned"),
                    }
                elif channel == TOPIC_TASK_STATUS:
                    st = parse_task_status_xml(xml_body)
                    if st.task_id in self._tasks:
                        self._tasks[st.task_id]["status"] = st.status
                        self._tasks[st.task_id]["reason"] = st.reason
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
        except Exception:
            logger.exception("Bus picture ingest failed on %s", channel)

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
        active_tasks = sum(1 for t in tasks if t.get("status") not in ("complete", "cancelled"))
        task_rows = [
            {
                "task_id": t.get("task_id", ""),
                "target_entity_id": t.get("target_entity_id", ""),
                "role": t.get("role", ""),
                "priority": t.get("priority", 1),
                "status": t.get("status", "assigned"),
                "platform_id": t.get("assigned_platform_id", ""),
            }
            for t in tasks
        ]
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
            "threat_picture": {"entity_count": len(entities), "active_tasks": active_tasks},
            "fusion_rows": [],
            "task_rows": task_rows,
            "raw_tracks": [],
            "mission_thread": {"f2t2ea_phases": [], "phase_counts": {}},
            "entity_registry": [],
            "feed_status": feed_status,
            "attention_queue": [],
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
