from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from uci_common.advisor_bridge import merge_advisor_attention, run_embedded_evaluation
from uci_common.llm_adapter import get_llm_adapter

from app.battlespace_harness import all_features_pass, build_harness_picture, verify_battlespace_features
from app.timeline import build_timeline_view

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

_engine: GulfWarEngine | None = None
_lock = threading.Lock()
_advisor_suggestions: list[dict[str, Any]] = []
_advisor_isr: list[dict[str, Any]] = []
_advisor_dedup: set[str] = set()
_advisor_eval_lock = threading.Lock()


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

ADVISOR_EMBEDDED = os.getenv("ADVISOR_EMBEDDED", "1").lower() in ("1", "true", "yes")
ADVISOR_URL = os.getenv("ADVISOR_URL", "").rstrip("/")
EXTERNAL_PROCESSING = os.getenv("GULFWAR_EXTERNAL_PROCESSING", "0").lower() in ("1", "true", "yes")
TASK_ALLOCATOR_URL = os.getenv("TASK_ALLOCATOR_URL", "http://127.0.0.1:8018").rstrip("/")
_llm = get_llm_adapter()


def _request_task(target_entity_id: str, role: str, priority: int, sim_minutes: float) -> str:
    """Monolith: engine allocates in-process. Microservices: UCI ScenarioEvent XML → task-allocator."""
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


def _fetch_remote_advisor() -> dict[str, Any] | None:
    if not ADVISOR_URL:
        return None
    try:
        req = urllib.request.Request(f"{ADVISOR_URL}/api/advisor/snapshot", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _refresh_advisor(snap: Any) -> None:
    global _advisor_suggestions, _advisor_isr, _advisor_dedup
    remote = _fetch_remote_advisor()
    if remote is not None:
        _advisor_suggestions = list(remote.get("suggestions", []))
        _advisor_isr = list(remote.get("isr_assignments", []))
        return

    if not ADVISOR_EMBEDDED or _engine is None:
        return

    with _advisor_eval_lock:
        def _enhance(actions: list) -> list:
            return _llm.enhance_actions(actions, {"sim_minutes": snap.sim_minutes})

        suggestions, isr, _advisor_dedup = run_embedded_evaluation(
            snap,
            dedup_keys=_advisor_dedup,
            publish=None,
            auto_isr=False,
            suggest_strike=True,
            llm_enhance=_enhance if os.getenv("LLM_PROVIDER", "rules") != "rules" else None,
        )
        # Merge new suggestions (keep accepted history)
        open_ids = {s["suggestion_id"] for s in suggestions}
        kept = [s for s in _advisor_suggestions if s.get("status") == "accepted" and s["suggestion_id"] not in open_ids]
        _advisor_suggestions = kept + suggestions
        _advisor_isr = isr


def _picture_payload() -> dict[str, Any]:
    if _harness_mode:
        return build_harness_picture()
    if _engine is None:
        return {"sim_minutes": 0, "entities": [], "narrative": "Engine not started"}
    snap = _engine.snapshot()
    _refresh_advisor(snap)
    attention = merge_advisor_attention(list(snap.attention_queue), _open_advisor_suggestions(snap.sim_minutes))
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
        "advisor_suggestions": _open_advisor_suggestions(snap.sim_minutes),
        "advisor_isr_assignments": list(_advisor_isr),
        "advisor_mode": "remote" if ADVISOR_URL else ("embedded" if ADVISOR_EMBEDDED else "off"),
        "timeline_view": timeline_view,
    }


def _picture_json() -> str:
    return json.dumps(_picture_payload())


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    """Battlespace API has no SPA at / — point operators to the Vite UI."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Battlespace Manager API</title></head>
<body style="font-family:system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem">
  <h1>Battlespace Display API</h1>
  <p>This port serves JSON/SSE only. The operator UI is a separate Vite app.</p>
  <h2>Start the UI</h2>
  <pre>cd services/battlespace-display/web
npm install
npm run dev</pre>
  <p>Then open <a href="http://localhost:5173">http://localhost:5173</a> (not this port).</p>
  <h2>API</h2>
  <ul>
    <li><a href="/health">/health</a></li>
    <li><a href="/api/picture">/api/picture</a></li>
    <li><a href="/api/stream">/api/stream</a> (SSE)</li>
    <li><a href="/docs">/docs</a></li>
  </ul>
</body>
</html>"""


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "service": "battlespace-display-api", "harness_mode": _harness_mode}


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
    if _engine is None:
        raise HTTPException(503, "Engine not started")
    role = (sug.get("suggested_role") or "STRIKE").upper()
    if role in ("ISR", "ISR_COLLECTION", "RECON"):
        raise HTTPException(400, "ISR tasks are auto-assigned; use strike suggestions only")
    snap = _engine.snapshot()
    task_id = _request_task(
        sug["target_entity_id"],
        role,
        int(sug.get("priority", 2)),
        snap.sim_minutes,
    )
    sug["status"] = "accepted"
    sug["accepted_task_id"] = task_id
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
