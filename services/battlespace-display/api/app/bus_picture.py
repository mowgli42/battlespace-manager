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

try:
    from uci_common.f2t2ea_messages import (
        parse_f2t2ea_state_xml,
        parse_target_allocated_xml,
        parse_target_generated_xml,
    )
    from uci_common.topics import TOPIC_F2T2EA_STATE, TOPIC_TARGET_ALLOCATED, TOPIC_TARGET_GENERATED
except ImportError:
    TOPIC_F2T2EA_STATE = "uci.f2t2ea.state"
    TOPIC_TARGET_GENERATED = "uci.target.generated"
    TOPIC_TARGET_ALLOCATED = "uci.target.allocated"

    def parse_f2t2ea_state_xml(xml_body: str) -> Any:
        raise ValueError("f2t2ea parser unavailable")

    def parse_target_generated_xml(xml_body: str) -> Any:
        raise ValueError("target generated parser unavailable")

    def parse_target_allocated_xml(xml_body: str) -> Any:
        raise ValueError("target allocated parser unavailable")

try:
    from uci_common.oms_state_messages import parse_oms_state_xml
    from uci_common.topics import TOPIC_OMS_STATE
except ImportError:
    TOPIC_OMS_STATE = "uci.oms.state"

    def parse_oms_state_xml(xml_body: str) -> Any:
        raise ValueError("oms state parser unavailable")

try:
    from uci_common.fkcm import build_fkcm_targets as _build_fkcm_targets
    from uci_common.mission_ui import build_entity_registry as _build_entity_registry
    from uci_common.mission_ui import build_mission_thread as _build_mission_thread
except ImportError:
    _build_fkcm_targets = None  # type: ignore[assignment]
    _build_entity_registry = None  # type: ignore[assignment]
    _build_mission_thread = None  # type: ignore[assignment]

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
_F2T2EA_PHASES = ["Find", "Fix", "Track", "Target", "Engage", "Assess"]
_F2T2EA_PHASE_MAP = {p.upper(): p for p in _F2T2EA_PHASES}
_TRACK_HISTORY_MAX = 40


def _platform_domain(platform_type: str, operational_role: str = "") -> str:
    blob = f"{platform_type} {operational_role}".upper()
    if any(tok in blob for tok in ("SHIP", "CVN", "DDG", "CG-", "FFG", "NAVAL", "CARRIER")):
        return "SURFACE"
    if any(tok in blob for tok in ("ARMOR", "SAM", "SCUD", "GROUND", "CAS")):
        return "AIR" if "CAS" in blob else "GROUND"
    return "AIR"

# Always-visible processor cards on the Sources tab (entity-display registry shape).
_FEED_REGISTRY: list[dict[str, str]] = [
    {"feed_id": "entity-fusion", "label": "Entity fusion", "type": "processor", "role": "correlation"},
    {"feed_id": "entity-sorter", "label": "Entity sorter", "type": "processor", "role": "category"},
]
_FEED_STALE_AFTER_S = 30.0

try:
    from uci_common.view_models import build_fusion_rows as _build_fusion_rows
except ImportError:
    _build_fusion_rows = None  # type: ignore[assignment]


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
        self._feed_ticks: dict[str, dict[str, float | int]] = {}
        self._route_threats: dict[str, dict[str, Any]] = {}
        self._attention: dict[str, dict[str, Any]] = {}
        self._route_geometries: dict[str, dict[str, Any]] = {}
        self._track_history: dict[str, list[list[float]]] = {}
        self._generated_targets: dict[str, dict[str, Any]] = {}
        self._target_alloc: dict[str, str] = {}

    def ingest(self, channel: str, xml_body: str) -> None:
        try:
            with self._lock:
                if channel == TOPIC_SCENARIO_CLOCK:
                    self._sim_minutes = float(parse_scenario_clock_xml(xml_body).sim_minutes)
                elif channel == TOPIC_CORRELATED_ENTITY:
                    ent = parse_correlated_entity_xml(xml_body)
                    self._entities[ent.entity_id] = self._entity_from_correlated(ent)
                    self._record_history(ent.entity_id, ent.latitude, ent.longitude)
                    self._tick_feed("entity-fusion")
                elif channel == TOPIC_ENTITY:
                    tr = parse_track_report_xml(xml_body)
                    self._ingest_entity_track(tr)
                    self._tick_feed("entity-sorter")
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
                    self._tick_feed("entity-sorter")
                elif channel == TOPIC_CORRELATION_EVENT:
                    ev = parse_correlation_event_xml(xml_body)
                    self._correlation_events.append(
                        {
                            "event_type": ev.event_type,
                            "track_id": ev.track_id,
                            "entity_id": ev.entity_id,
                            "score": ev.score,
                            "source_feed": ev.source_feed,
                            "sim_minutes": self._sim_minutes,
                        }
                    )
                    self._correlation_events = self._correlation_events[-200:]
                    if ev.source_feed:
                        self._tick_feed(ev.source_feed)
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
                    self._ingest_platform_status(parse_platform_status_xml(xml_body))
                elif channel == TOPIC_OMS_STATE:
                    self._ingest_oms_state(parse_oms_state_xml(xml_body))
                elif channel == TOPIC_F2T2EA_STATE:
                    self._ingest_f2t2ea_state(parse_f2t2ea_state_xml(xml_body))
                elif channel == TOPIC_TARGET_GENERATED:
                    self._ingest_target_generated(parse_target_generated_xml(xml_body))
                elif channel == TOPIC_TARGET_ALLOCATED:
                    self._ingest_target_allocated(parse_target_allocated_xml(xml_body))
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

    def _record_history(self, eid: str, lat: float, lon: float) -> None:
        if not eid or lat is None or lon is None:
            return
        hist = self._track_history.setdefault(eid, [])
        point = [float(lat), float(lon)]
        if hist and hist[-1][0] == point[0] and hist[-1][1] == point[1]:
            return
        hist.append(point)
        if len(hist) > _TRACK_HISTORY_MAX:
            del hist[: len(hist) - _TRACK_HISTORY_MAX]

    def _ingest_entity_track(self, tr: Any) -> None:
        eid = tr.track_id
        fused = next(
            (row for row in self._entities.values() if eid in (row.get("sources") or [])),
            None,
        )
        if fused is not None:
            fused["latitude"] = tr.latitude
            fused["longitude"] = tr.longitude
            fused["altitude_feet"] = tr.altitude_feet
            self._record_history(fused["entity_id"], tr.latitude, tr.longitude)
            return
        existing = self._entities.get(eid, {})
        self._entities[eid] = {
            **existing,
            "entity_id": eid,
            "latitude": tr.latitude,
            "longitude": tr.longitude,
            "altitude_feet": tr.altitude_feet,
            "callsign": (tr.callsign or existing.get("callsign") or "").strip(),
            "platform_type": existing.get("platform_type") or getattr(tr, "aircraft_type", "") or "",
            "sources": existing.get("sources") or [eid],
        }
        self._record_history(eid, tr.latitude, tr.longitude)

    def _ingest_platform_status(self, plat: Any) -> None:
        existing = self._platforms.get(plat.platform_id, {})
        self._platforms[plat.platform_id] = {
            **existing,
            "platform_id": plat.platform_id,
            "callsign": plat.callsign or existing.get("callsign", ""),
            "platform_type": plat.platform_type or existing.get("platform_type", ""),
            "latitude": plat.latitude,
            "longitude": plat.longitude,
            "altitude_feet": getattr(plat, "altitude_feet", 0) or existing.get("altitude_feet", 0),
            "fuel_percent": plat.fuel_percent,
            "weapons_remaining": plat.weapons_remaining,
            "active_task_count": plat.active_task_count,
            "readiness": plat.readiness,
            "operational_role": plat.operational_role or existing.get("operational_role", ""),
            "route_name": plat.route_name or existing.get("route_name", ""),
            "active_task_id": plat.active_task_id or existing.get("active_task_id", ""),
            "affiliation": "COALITION",
            "domain": existing.get("domain") or _platform_domain(plat.platform_type, plat.operational_role),
        }
        self._record_history(f"plt-{plat.platform_id}", plat.latitude, plat.longitude)

    def _ingest_oms_state(self, snap: Any) -> None:
        for route in snap.routes or []:
            name = route.route_name
            if not name or not route.waypoints:
                continue
            existing = self._route_geometries.get(name, {})
            pids = list(route.platform_ids or existing.get("platform_ids") or [])
            self._route_geometries[name] = {
                "route_name": name,
                "platform_id": (pids[0] if pids else existing.get("platform_id", "")),
                "platform_ids": pids,
                "waypoints": [[lat, lon] for lat, lon in route.waypoints],
                "description": route.source or existing.get("description", "derived"),
            }
        for plat in snap.platforms or []:
            existing = self._platforms.get(plat.platform_id, {})
            self._platforms[plat.platform_id] = {
                **existing,
                "platform_id": plat.platform_id,
                "callsign": plat.callsign or existing.get("callsign", ""),
                "latitude": plat.latitude or existing.get("latitude", 0),
                "longitude": plat.longitude or existing.get("longitude", 0),
                "route_name": plat.route_name or existing.get("route_name", ""),
                "active_task_count": plat.active_task_count,
                "active_task_id": plat.active_task_id or existing.get("active_task_id", ""),
                "weapons_remaining": plat.weapons_remaining,
                "fuel_percent": plat.fuel_percent,
                "readiness": plat.readiness or existing.get("readiness", ""),
                "operational_role": plat.operational_role or existing.get("operational_role", ""),
                "affiliation": "COALITION",
                "domain": existing.get("domain") or _platform_domain("", plat.operational_role),
            }

    def _ingest_f2t2ea_state(self, state: Any) -> None:
        tid = state.target_id
        if not tid:
            return
        phase = _F2T2EA_PHASE_MAP.get((state.current_phase or "").upper(), "Find")
        geo = self._generated_targets.get(tid, {})
        prior = self._kill_chains.get(tid, {})
        self._kill_chains[tid] = {
            "target_entity_id": tid,
            "target_name": geo.get("target_name") or prior.get("target_name") or tid,
            "phase": phase,
            "active_task_id": prior.get("active_task_id", ""),
            "notes": state.status or prior.get("notes", ""),
        }

    def _ingest_target_generated(self, tgt: Any) -> None:
        tid = tgt.target_id
        if not tid:
            return
        self._generated_targets[tid] = {
            "entity_id": tid,
            "latitude": tgt.latitude,
            "longitude": tgt.longitude,
            "altitude_feet": 0.0,
            "domain": "GROUND",
            "affiliation": "OPFOR",
            "platform_type": tgt.weaponeering or "TARGET",
            "confidence": 0.8,
            "sources": [tgt.source_assessment_id] if tgt.source_assessment_id else [],
            "target_name": tid,
        }
        if tid not in self._entities:
            self._entities[tid] = dict(self._generated_targets[tid])
        if tid not in self._kill_chains:
            self._kill_chains[tid] = {
                "target_entity_id": tid,
                "target_name": tid,
                "phase": "Target",
                "active_task_id": "",
                "notes": "target generated",
            }
        self._record_history(tid, tgt.latitude, tgt.longitude)

    def _ingest_target_allocated(self, alloc: Any) -> None:
        tid = alloc.target_id
        if not tid:
            return
        self._target_alloc[tid] = alloc.platform_id
        if tid in self._kill_chains:
            self._kill_chains[tid]["active_task_id"] = self._kill_chains[tid].get("active_task_id") or ""
            self._kill_chains[tid]["notes"] = alloc.allocation_status or self._kill_chains[tid].get("notes", "")
        for task in self._tasks.values():
            if task.get("target_entity_id") == tid and alloc.platform_id:
                task["assigned_platform_id"] = alloc.platform_id

    def _tick_feed(self, feed_id: str) -> None:
        if not feed_id:
            return
        entry = self._feed_ticks.setdefault(feed_id, {"count": 0, "last_seen": 0.0})
        entry["count"] = int(entry["count"]) + 1
        entry["last_seen"] = time.time()

    def _feed_status_list(self) -> list[dict[str, Any]]:
        now = time.time()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        registry_ids = {meta["feed_id"] for meta in _FEED_REGISTRY}
        for meta in _FEED_REGISTRY:
            rows.append(self._feed_row(meta, now=now))
            seen.add(meta["feed_id"])
        for fid in sorted(self._feed_ticks):
            if fid in seen or fid in registry_ids:
                continue
            rows.append(
                self._feed_row(
                    {"feed_id": fid, "label": fid, "type": "sensor", "role": "ingest"},
                    now=now,
                )
            )
        return rows

    def _feed_row(self, meta: dict[str, str], *, now: float) -> dict[str, Any]:
        fid = meta["feed_id"]
        tick = self._feed_ticks.get(fid, {})
        last = float(tick.get("last_seen", 0) or 0)
        count = int(tick.get("count", 0) or 0)
        age = now - last if last else None
        active = age is not None and age < _FEED_STALE_AFTER_S
        return {
            "feed_id": fid,
            "label": meta.get("label", fid),
            "type": meta.get("type", "sensor"),
            "role": meta.get("role", ""),
            "active": active,
            "message_count": count,
            "tracks_last_tick": count,
            "last_seen_age_s": round(age, 1) if age is not None else None,
            "status": "live" if active else ("stale" if last else "idle"),
        }

    def _fusion_rows(self, entities: list[dict[str, Any]], corr: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if _build_fusion_rows is not None:
            return _build_fusion_rows(
                correlation_events=corr,
                entities=entities,
                cues=[],
                raw_tracks=[],
            )
        entity_by_id = {e.get("entity_id"): e for e in entities}
        rows = []
        for ev in corr:
            eid = ev.get("entity_id", "")
            rows.append(
                {
                    "row_id": f"corr-{ev.get('track_id')}-{ev.get('sim_minutes')}",
                    "kind": "CORRELATION",
                    "event_type": ev.get("event_type", ""),
                    "source_feed": ev.get("source_feed", ""),
                    "track_id": ev.get("track_id", ""),
                    "entity_id": eid,
                    "score": ev.get("score"),
                    "sim_minutes": ev.get("sim_minutes", 0),
                    "summary": f"{ev.get('event_type')} · {ev.get('source_feed')}",
                    "entity": entity_by_id.get(eid, {}),
                    "signal": None,
                    "track": None,
                }
            )
        return rows[-200:]

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
                if not (row.get("affiliation") or row.get("domain") or str(eid).startswith("ENT-")):
                    continue
                entities.append(row)
            for tid, tgt in self._generated_targets.items():
                if any(e.get("entity_id") == tid for e in entities):
                    continue
                if tgt.get("latitude") or tgt.get("longitude"):
                    entities.append(dict(tgt))
            tasks = list(self._tasks.values())
            kill_chains = list(self._kill_chains.values())
            platforms = list(self._platforms.values())
            sim = self._sim_minutes
            narrative = self._narrative
            corr = list(self._correlation_events)
            feed_status = self._feed_status_list()
            fusion_rows = self._fusion_rows(entities, corr)
            track_history = {k: list(v) for k, v in self._track_history.items() if v}
            hvt_lookup = {
                e["entity_id"]: {
                    "name": e.get("callsign") or e.get("platform_type") or e["entity_id"],
                    "type": e.get("platform_type", ""),
                    "affiliation": e.get("affiliation", "OPFOR"),
                }
                for e in entities
                if (e.get("affiliation") or "").upper() in ("OPFOR", "HOSTILE")
            }
            entity_meta = dict(self._entity_meta)
            for e in entities:
                eid = e.get("entity_id", "")
                if eid:
                    entity_meta.setdefault(eid, {})["last_updated_sim"] = sim
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
        if _build_fkcm_targets is not None:
            fkcm_targets = _build_fkcm_targets(
                sim_minutes=sim,
                kill_chains=kill_chains,
                entities=entities,
                tasks=tasks,
                hvt_lookup=hvt_lookup,
                entity_meta=entity_meta,
            )
        else:
            fkcm_targets = [
                {
                    "target_id": kc.get("target_entity_id", ""),
                    "target_name": kc.get("target_name") or kc.get("target_entity_id", ""),
                    "phase": kc.get("phase", "Find"),
                    "phase_color": "#3b82f6",
                    "latitude": 0.0,
                    "longitude": 0.0,
                }
                for kc in kill_chains
            ]
        if _build_entity_registry is not None:
            entity_registry = _build_entity_registry(
                entities=entities,
                fkcm_targets=fkcm_targets,
                entity_meta=entity_meta,
                sim_minutes=sim,
            )
        else:
            entity_registry = [
                {**e, "kill_chain_phase": "—", "staleness": "recent", "last_updated_sim": sim}
                for e in entities
            ]
        if _build_mission_thread is not None:
            mission_thread = _build_mission_thread(
                sim_minutes=sim,
                narrative=narrative,
                timeline=[],
                fired_offsets=set(),
                kill_chains=kill_chains,
            )
        else:
            counts = {ph: 0 for ph in _F2T2EA_PHASES}
            for kc in kill_chains:
                ph = kc.get("phase", "Find")
                if ph in counts:
                    counts[ph] += 1
            mission_thread = {
                "sim_minutes": sim,
                "narrative": narrative,
                "timeline_events": [],
                "f2t2ea_phases": list(_F2T2EA_PHASES),
                "phase_counts": counts,
                "dominant_phase": max(counts, key=counts.get) if kill_chains else "Find",
            }
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
            "fkcm_targets": fkcm_targets,
            "track_history": track_history,
            "threat_picture": {
                "entity_count": len(entities),
                "active_tasks": active_tasks,
                "route_threats": len(route_threats),
            },
            "fusion_rows": fusion_rows,
            "task_rows": task_rows,
            "raw_tracks": [],
            "mission_thread": mission_thread,
            "entity_registry": entity_registry,
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
        TOPIC_OMS_STATE,
        TOPIC_F2T2EA_STATE,
        TOPIC_TARGET_GENERATED,
        TOPIC_TARGET_ALLOCATED,
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
