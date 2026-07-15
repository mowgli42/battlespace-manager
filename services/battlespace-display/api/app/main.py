from __future__ import annotations

import json
import logging
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.battlespace_harness import all_features_pass, build_harness_picture, verify_battlespace_features
from app.oms_ai_services import merge_oms_attention, refresh_oms_ai_services
from app.timeline import build_timeline_view

try:
    from app.bus_picture import BusPictureState, start_bus_picture_subscriber
except ImportError:
    BusPictureState = None  # type: ignore[misc, assignment]
    start_bus_picture_subscriber = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from uci_common.gulfwar_engine import GulfWarEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("battlespace-display-api")

app = FastAPI(title="Battlespace Display API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_portal_dir = Path(__file__).resolve().parents[3] / "display-portal"
try:
    from app.portal_routes import register_portal_routes
except ImportError:
    if _portal_dir.is_dir() and str(_portal_dir) not in sys.path:
        sys.path.insert(0, str(_portal_dir))
    from portal_routes import register_portal_routes  # noqa: E402

register_portal_routes(app, display_id="battlespace", title="Battlespace Display — OMS Portal")

_engine: GulfWarEngine | None = None
_lock = threading.Lock()
_advisor_suggestions: list[dict[str, Any]] = []
_advisor_isr: list[dict[str, Any]] = []
_advisor_dedup: set[str] = set()


def _open_advisor_suggestions(sim_minutes: float) -> list[dict[str, Any]]:
    """Suggestions visible to operator (excludes dismissed and active snoozes)."""
    visible: list[dict[str, Any]] = []
    for s in _advisor_suggestions:
        status = s.get("status", "open")
        if status in ("accepted", "dismissed"):
            continue
        if status == "snoozed" and float(s.get("snooze_until_sim", 0)) > sim_minutes:
            continue
        visible.append(s)
    return visible


def _find_suggestion(suggestion_id: str) -> dict[str, Any] | None:
    return next((s for s in _advisor_suggestions if s.get("suggestion_id") == suggestion_id), None)


_harness_mode = os.getenv("BATTLESPACE_HARNESS", "").lower() in ("1", "true", "yes")

ADVISOR_EMBEDDED = os.getenv("ADVISOR_EMBEDDED", "0").lower() in ("1", "true", "yes")
EXTERNAL_PROCESSING = os.getenv("GULFWAR_EXTERNAL_PROCESSING", "0").lower() in ("1", "true", "yes")
BUS_PICTURE_MODE = os.getenv("BUS_PICTURE_MODE", "0").lower() in ("1", "true", "yes")
TASKING_VIA_BUS = os.getenv("TASKING_VIA_BUS", "0").lower() in ("1", "true", "yes") or BUS_PICTURE_MODE
TASK_ALLOCATOR_URL = os.getenv("TASK_ALLOCATOR_URL", "http://127.0.0.1:8018").rstrip("/")
_bus_picture: BusPictureState | None = BusPictureState() if BUS_PICTURE_MODE and BusPictureState else None
_bus: Any | None = None


def _request_task(target_entity_id: str, role: str, priority: int, sim_minutes: float) -> str:
    """Monolith: engine allocates in-process. Bus mode: publish ScenarioEvent; else HTTP task-allocator."""
    if TASKING_VIA_BUS:
        from uci_common.bus import RedisBus
        from uci_common.gulfwar_sim.messages import ScenarioEventMsg, build_scenario_event_xml

        global _bus
        if _bus is None:
            _bus = RedisBus()
        ev = ScenarioEventMsg(
            event_type="TASK_REQUEST",
            sim_minutes=sim_minutes,
            entity_id=target_entity_id,
            role=role,
            priority=priority,
            narrative="Operator task request (battlespace API, bus)",
        )
        topic = os.getenv("TOPIC_SCENARIO_EVENT", "uci.scenario.event")
        _bus.publish(topic, build_scenario_event_xml(ev))
        return f"TASK-REQ-{target_entity_id}-{int(sim_minutes)}"
    if EXTERNAL_PROCESSING and TASK_ALLOCATOR_URL:
        from uci_common.gulfwar_sim.messages import ScenarioEventMsg, build_scenario_event_xml
        from uci_common.gw_messages import parse_task_xml

        ev = ScenarioEventMsg(
            event_type="TASK_REQUEST",
            sim_minutes=sim_minutes,
            entity_id=target_entity_id,
            role=role,
            priority=priority,
            narrative="Operator task request (battlespace API)",
        )
        xml = build_scenario_event_xml(ev).encode("utf-8")
        req = urllib.request.Request(
            f"{TASK_ALLOCATOR_URL}/api/task/request",
            data=xml,
            headers={"Content-Type": "application/xml"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode()
                if "xml" in (resp.headers.get("content-type") or "").lower():
                    return parse_task_xml(body).task_id
                data = json.loads(body)
                return str(data.get("task_id", ""))
        except urllib.error.URLError as exc:
            raise HTTPException(503, f"Task allocator unavailable: {exc}") from exc
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    return _engine.request_task(target_entity_id, role, priority)


def set_engine(engine: GulfWarEngine) -> None:
    global _engine
    _engine = engine


def _refresh_oms_ai(snap: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    global _advisor_suggestions, _advisor_isr
    with _lock:
        prior = list(_advisor_suggestions)
        dedup = set(_advisor_dedup)
    services, suggestions, isr, summary = refresh_oms_ai_services(
        snap,
        dedup_keys=dedup,
        open_suggestions=prior,
    )
    with _lock:
        _advisor_suggestions = suggestions
        _advisor_isr = isr
    return services, suggestions, isr, summary


def _picture_payload() -> dict[str, Any]:
    if _harness_mode:
        return build_harness_picture()
    if _bus_picture is not None:
        snap_dict = _bus_picture.snapshot()
        oms_services, _, isr, oms_summary = _refresh_oms_ai(None)
        visible = _open_advisor_suggestions(float(snap_dict.get("sim_minutes", 0)))
        attention = merge_oms_attention(
            list(snap_dict.get("attention_queue") or []),
            visible,
            services_live=bool(oms_summary.get("any_live")),
        )
        timeline_view = build_timeline_view(
            sim_minutes=float(snap_dict.get("sim_minutes", 0)),
            scenario_timeline=[],
            fired_offsets=set(),
            task_rows=list(snap_dict.get("task_rows") or []),
        )
        return {
            **snap_dict,
            "attention_queue": attention,
            "advisor_suggestions": visible,
            "advisor_isr_assignments": list(isr),
            "advisor_mode": "oms" if oms_summary.get("any_live") else ("embedded" if ADVISOR_EMBEDDED else "off"),
            "oms_ai_services": oms_services,
            "oms_ai_summary": oms_summary,
            "timeline_view": timeline_view,
            "bus_picture_mode": True,
        }
    if _engine is None:
        return {"sim_minutes": 0, "entities": [], "narrative": "Engine not started"}
    snap = _engine.snapshot()
    oms_services, _, isr, oms_summary = _refresh_oms_ai(snap)
    visible = _open_advisor_suggestions(snap.sim_minutes)
    attention = merge_oms_attention(
        list(snap.attention_queue),
        visible,
        services_live=bool(oms_summary.get("any_live")),
    )
    timeline_view = build_timeline_view(
        sim_minutes=float(snap.sim_minutes),
        scenario_timeline=list(_engine._scenario.get("timeline", [])),
        fired_offsets=_engine._fired_events,
        task_rows=list(snap.task_rows),
    )
    return {
        "sim_minutes": snap.sim_minutes,
        "narrative": snap.narrative,
        "entities": snap.entities,
        "cues": snap.cues,
        "correlation_events": snap.correlation_events,
        "platforms": snap.platforms,
        "tasks": snap.tasks,
        "kill_chains": snap.kill_chains,
        "fkcm_targets": snap.fkcm_targets,
        "track_history": snap.track_history,
        "threat_picture": snap.threat_picture,
        "fusion_rows": snap.fusion_rows,
        "task_rows": snap.task_rows,
        "raw_tracks": snap.raw_tracks,
        "mission_thread": snap.mission_thread,
        "entity_registry": snap.entity_registry,
        "feed_status": snap.feed_status,
        "attention_queue": attention,
        "bda_items": snap.bda_items,
        "platform_context": snap.platform_context,
        "advisor_suggestions": visible,
        "advisor_isr_assignments": list(isr),
        "advisor_mode": "oms" if oms_summary.get("any_live") else ("embedded" if ADVISOR_EMBEDDED else "off"),
        "oms_ai_services": oms_services,
        "oms_ai_summary": oms_summary,
        "timeline_view": timeline_view,
    }


def _picture_json() -> str:
    return json.dumps(_picture_payload())


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "battlespace-display-api",
        "harness_mode": _harness_mode,
        "bus_picture_mode": _bus_picture is not None,
    }


@app.on_event("startup")
def startup() -> None:
    if _bus_picture is not None and start_bus_picture_subscriber is not None:
        from uci_common.bus import RedisBus

        bus = RedisBus()
        start_bus_picture_subscriber(_bus_picture, bus)
        logger.info("BUS_PICTURE_MODE=1 — COP from UCI bus (no GulfWarEngine)")
    try:
        from app.oms_ai_bus import start_oms_ai_bus_subscriber

        start_oms_ai_bus_subscriber()
    except Exception:
        logger.debug("OMS AI bus subscriber not started")
    try:
        from service_status_bus import start_service_status_subscriber

        start_service_status_subscriber()
    except Exception:
        logger.debug("Service status bus subscriber not started")


@app.get("/api/oms-ai/services")
def get_oms_ai_services() -> dict[str, Any]:
    if _harness_mode:
        picture = build_harness_picture()
        return {
            "oms_ai_services": picture.get("oms_ai_services", []),
            "oms_ai_summary": picture.get("oms_ai_summary", {}),
        }
    if _engine is None:
        services, _, _, summary = refresh_oms_ai_services(None)
        return {"oms_ai_services": services, "oms_ai_summary": summary}
    snap = _engine.snapshot()
    services, _, _, summary = _refresh_oms_ai(snap)
    return {"oms_ai_services": services, "oms_ai_summary": summary}


@app.get("/api/harness/verify")
def harness_verify() -> dict[str, Any]:
    picture = _picture_payload()
    results = verify_battlespace_features(picture)
    return {"passed": all_features_pass(results), "harness_mode": _harness_mode, "checks": results}


@app.get("/api/timeline")
def get_timeline() -> dict:
    payload = _picture_payload()
    return payload.get("timeline_view") or {"sim_minutes": 0, "items": [], "upcoming": []}


@app.get("/api/picture")
def get_picture() -> dict:
    return _picture_payload()


@app.get("/api/stream")
async def stream():
    async def gen():
        while True:
            yield f"data: {_picture_json()}\n\n"
            import asyncio

            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/demo/reset")
def demo_reset() -> dict[str, str]:
    global _advisor_suggestions, _advisor_isr, _advisor_dedup
    if _engine is None:
        return {"status": "error", "message": "Engine not started"}
    _engine.reset()
    for fid in ("LINK16-TACTICAL", "AWACS-MAGIC", "AIS-NAG", "MTI-KUWAIT"):
        _engine._active_feeds.add(fid)
    _advisor_suggestions.clear()
    _advisor_isr.clear()
    _advisor_dedup.clear()
    return {"status": "ok", "message": "Scenario reset to T+0"}


@app.get("/api/sim/status")
def sim_status() -> dict[str, Any]:
    if _bus_picture is not None:
        snap = _bus_picture.snapshot()
        return {
            "sim_minutes": snap.get("sim_minutes", 0),
            "running": True,
            "feeds": [],
            "components": [],
            "bookmarks": [],
            "bus_picture_mode": True,
        }
    if _engine is None:
        return {"sim_minutes": 0, "running": False, "feeds": [], "components": [], "bookmarks": []}
    return _engine.sim_control_status(running=True)


@app.post("/api/sim/pause")
def sim_pause() -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    _engine.set_paused(True)
    return _engine.sim_control_status(running=False)


@app.post("/api/sim/resume")
def sim_resume() -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    _engine.set_paused(False)
    return _engine.sim_control_status(running=True)


@app.post("/api/sim/step")
def sim_step() -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    was_paused = _engine._paused
    _engine.set_paused(False)
    _engine.tick(sim_delta_minutes=float(os.getenv("GULFWAR_SIM_DELTA_MIN", "1.0")))
    _engine.set_paused(was_paused)
    return _engine.sim_control_status(running=not was_paused)


@app.post("/api/sim/seek")
def sim_seek(body: dict[str, Any]) -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    offset = float(body.get("offset_minutes", 0))
    global _advisor_suggestions, _advisor_isr, _advisor_dedup
    _engine.seek_to(offset)
    _advisor_suggestions.clear()
    _advisor_isr.clear()
    _advisor_dedup.clear()
    return _engine.sim_control_status(running=not _engine._paused)


@app.post("/api/sim/feeds/{feed_id}")
def sim_toggle_feed(feed_id: str, body: dict[str, Any]) -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    _engine.set_feed_enabled(feed_id, bool(body.get("enabled", True)))
    return _engine.sim_control_status(running=not _engine._paused)


@app.post("/api/sim/components/{component_id}")
def sim_toggle_component(component_id: str, body: dict[str, Any]) -> dict[str, Any]:
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    enabled = bool(body.get("enabled", True))
    _engine.set_component_enabled(component_id, enabled)
    if component_id == "scenario_clock":
        _engine.set_paused(not enabled)
    return _engine.sim_control_status(running=not _engine._paused)


@app.post("/api/advisor/accept")
def accept_suggestion(body: dict[str, Any]) -> dict[str, Any]:
    """Operator accepts AI strike suggestion → engine task request."""
    sid = body.get("suggestion_id", "")
    if not sid:
        raise HTTPException(400, "suggestion_id required")
    sug = next((s for s in _advisor_suggestions if s.get("suggestion_id") == sid), None)
    if not sug:
        raise HTTPException(404, f"Suggestion {sid} not found")
    if _engine is None and _bus_picture is None:
        raise HTTPException(503, "Engine not started")
    role = (sug.get("suggested_role") or "STRIKE").upper()
    if role in ("ISR", "ISR_COLLECTION", "RECON"):
        raise HTTPException(400, "ISR tasks are auto-assigned; use strike suggestions only")
    if _bus_picture is not None:
        sim_minutes = float(_bus_picture.snapshot().get("sim_minutes", 0))
    else:
        sim_minutes = _engine.snapshot().sim_minutes
    task_id = _request_task(
        sug["target_entity_id"],
        role,
        int(sug.get("priority", 2)),
        sim_minutes,
    )
    sug["status"] = "accepted"
    sug["accepted_task_id"] = task_id
    advisor_url = os.getenv("ADVISOR_URL", "http://127.0.0.1:8005").rstrip("/")
    if advisor_url and advisor_url.lower() not in ("none", "off", "0"):
        try:
            req = urllib.request.Request(
                f"{advisor_url}/api/advisor/accept",
                data=json.dumps({"suggestion_id": sid}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except (urllib.error.URLError, TimeoutError):
            pass
    return {
        "status": "ok",
        "suggestion_id": sid,
        "task_id": task_id,
        "target_entity_id": sug["target_entity_id"],
        "role": role,
    }




@app.post("/api/advisor/dismiss")
def dismiss_suggestion(body: dict[str, Any]) -> dict[str, Any]:
    sid = body.get("suggestion_id", "")
    if not sid:
        raise HTTPException(400, "suggestion_id required")
    sug = _find_suggestion(sid)
    if not sug:
        raise HTTPException(404, f"Suggestion {sid} not found")
    sug["status"] = "dismissed"
    sug["dismiss_reason"] = body.get("reason", "operator_dismiss")
    _advisor_dedup.add(f"dismiss:{sid}")
    return {"status": "ok", "suggestion_id": sid}


@app.post("/api/advisor/snooze")
def snooze_suggestion(body: dict[str, Any]) -> dict[str, Any]:
    sid = body.get("suggestion_id", "")
    minutes = float(body.get("minutes", 15))
    if not sid:
        raise HTTPException(400, "suggestion_id required")
    sug = _find_suggestion(sid)
    if not sug:
        raise HTTPException(404, f"Suggestion {sid} not found")
    sim_until = (_engine.snapshot().sim_minutes if _engine else 0) + minutes
    sug["status"] = "snoozed"
    sug["snooze_until_sim"] = sim_until
    sug["snooze_minutes"] = minutes
    _advisor_dedup.add(f"snooze:{sid}:{int(sim_until)}")
    return {"status": "ok", "suggestion_id": sid, "snooze_until_sim": sim_until}


@app.post("/api/route-threat/support")
def route_threat_support(body: dict[str, Any]) -> dict[str, Any]:
    """Operator support request from route timeline (Strike / EJ / Jam).

    Harness mode records a local nomination stub. Bus / engine modes reuse
    ``_request_task`` so later popup-tasker / allocator consumers can take over.
    """
    threat_id = str(body.get("threat_entity_id") or "").strip()
    role = str(body.get("role") or body.get("band") or "STRIKE").upper()
    if role in ("EJ", "JAM"):
        role = "SEAD" if role == "EJ" else "CAP"
    if not threat_id:
        raise HTTPException(400, "threat_entity_id required")
    priority = 0 if role == "STRIKE" else (1 if role == "SEAD" else 2)
    sim = 0.0
    if _harness_mode:
        pic = build_harness_picture()
        sim = float(pic.get("sim_minutes") or 0)
        task_id = f"SUPPORT-{role}-{threat_id}-{int(sim)}"
        return {
            "ok": True,
            "harness": True,
            "task_id": task_id,
            "role": role,
            "route_name": body.get("route_name"),
            "detail": "Harness nomination stub — wire to uci.task when bus-connected",
        }
    if _bus_picture is not None:
        sim = float(_bus_picture.snapshot().get("sim_minutes") or 0)
    elif _engine is not None:
        sim = float(_engine.snapshot().sim_minutes)
    task_id = _request_task(threat_id, role, priority, sim)
    return {
        "ok": True,
        "task_id": task_id,
        "role": role,
        "route_name": body.get("route_name"),
    }


@app.get("/api/stats")
def stats() -> dict:
    if _engine is None:
        return {"entities": 0, "tasks": 0, "kill_chains": 0}
    s = _engine.snapshot()
    opfor = sum(1 for e in s.entities if e.get("affiliation") == "OPFOR")
    return {
        "entities": len(s.entities),
        "opfor": opfor,
        "tasks": len(s.tasks),
        "kill_chains": len(s.kill_chains),
        "sim_minutes": s.sim_minutes,
        "advisor_suggestions_open": len(_open_advisor_suggestions(s.sim_minutes)),
    }
