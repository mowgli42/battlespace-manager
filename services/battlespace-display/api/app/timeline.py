"""Unified operator timeline: aligned per-aircraft tracks + debrief markers.

Matches o-my-mission-plan aligned TOT lanes (one row per aircraft, shared time
axis) and o-my-debrief marker glyphs: ⚑ launch/on-station, ◆ collect/ISR, ▼ strike.
"""

from __future__ import annotations

from typing import Any

# Debrief marker vocabulary (o-my-debrief Timeline.svelte / api.markerGlyph).
MARKER_FLAG = "flag"  # ⚑ launch / on-station / recover
MARKER_DIAMOND = "diamond"  # ◆ collect / ISR
MARKER_CARET = "caret"  # ▼ strike
MARKER_CIRCLE = "circle"  # ● threat / other

_MAX_EVENTS_PER_TRACK = 12
_PAST_FRACTION = 0.25
_DEFAULT_SPAN_MIN = 60.0
_CRUISE_KT = 420.0
# Client zoom steps (minutes). Default window is 25% behind NOW, 75% ahead.
ZOOM_SPANS_MINUTES = (10, 30, 60, 180, 360, 720)

_ROLE_ORDER = {
    "AWACS": 0,
    "ISR": 1,
    "SIGINT": 2,
    "CAP": 3,
    "SEAD": 4,
    "EW": 5,
    "STRIKE": 6,
    "CAS": 7,
    "TANKER": 8,
}


def _event_status(sim_minutes: float, offset: float, fired_offsets: set[int]) -> str:
    if int(offset) in fired_offsets or sim_minutes >= offset + 0.5:
        return "past"
    if sim_minutes >= offset - 2:
        return "imminent"
    return "future"


def _task_status(sim_minutes: float, task: dict[str, Any]) -> str:
    lc = str(task.get("lifecycle_state", "")).upper()
    if lc in ("EXECUTED", "ABORTED", "COMPLETE", "CANCELLED"):
        return "past"
    assigned = task.get("assigned_at_sim", task.get("first_seen_sim"))
    if assigned is not None and float(assigned) <= sim_minutes:
        return "active"
    return "open"


def _task_time(task: dict[str, Any], sim_minutes: float) -> float:
    for key in ("assigned_at_sim", "first_seen_sim", "sim_offset"):
        val = task.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return float(sim_minutes)


def _task_tot_time(task: dict[str, Any], sim_minutes: float) -> float:
    """When the assigned task should appear on the upcoming (75%) side of NOW."""
    lc = str(task.get("lifecycle_state", "")).upper()
    if lc in ("IN_PROGRESS", "EXECUTING", "ACTIVE"):
        return float(sim_minutes)
    assigned = task.get("assigned_at_sim")
    if assigned is not None:
        try:
            when = float(assigned)
            if when > sim_minutes + 0.25:
                return when
        except (TypeError, ValueError):
            pass
    cost = task.get("cost_nm")
    if cost not in (None, "", 0, 0.0):
        try:
            eta = (float(cost) / _CRUISE_KT) * 60.0
            if eta >= 0.5:
                return float(sim_minutes) + eta
        except (TypeError, ValueError):
            pass
    tst = task.get("tst_minutes_remaining")
    if tst is not None:
        try:
            rem = float(tst)
            if rem > 0:
                return float(sim_minutes) + rem
        except (TypeError, ValueError):
            pass
    # Still queued with no ETA: stagger by priority so markers do not stack on the playhead.
    try:
        priority = max(0, min(9, int(task.get("priority", 5))))
    except (TypeError, ValueError):
        priority = 5
    return float(sim_minutes) + 4.0 + priority * 3.0


def _marker_for_role(role: str) -> str:
    r = (role or "").upper()
    if r in ("STRIKE", "SEAD", "CAS", "ENGAGE"):
        return MARKER_CARET
    if r in ("ISR", "COLLECT", "SIGINT", "AWACS"):
        return MARKER_DIAMOND
    return MARKER_CIRCLE


def _pid(task: dict[str, Any]) -> str:
    return str(task.get("assigned_platform_id") or task.get("platform_id") or "")


def build_timeline_view(
    *,
    sim_minutes: float,
    scenario_timeline: list[dict[str, Any]],
    fired_offsets: set[int] | list[int],
    task_rows: list[dict[str, Any]],
    platforms: list[dict[str, Any]] | None = None,
    route_threats: list[dict[str, Any]] | None = None,
    fkcm_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fired = set(int(x) for x in fired_offsets)
    items: list[dict[str, Any]] = []

    for ev in sorted(scenario_timeline, key=lambda e: int(e.get("simOffsetMinutes", 0))):
        offset = int(ev.get("simOffsetMinutes", 0))
        items.append(
            {
                "id": f"scenario-{offset}-{ev.get('event', 'EV')}",
                "kind": "scenario",
                "sim_offset": offset,
                "title": ev.get("event", "EVENT"),
                "detail": ev.get("narrative", ""),
                "status": _event_status(sim_minutes, offset, fired),
                "feed_id": ev.get("feedId", ""),
                "entity_id": ev.get("entityId", ""),
                "cue_id": ev.get("cueId", ""),
            }
        )

    for task in task_rows:
        lc = task.get("lifecycle_state", "")
        if lc in ("EXECUTED", "ABORTED"):
            continue
        assigned = task.get("assigned_at_sim", task.get("first_seen_sim"))
        offset = float(assigned) if assigned is not None else float(sim_minutes)
        status = _task_status(sim_minutes, task)
        detail_parts = [lc, f"F2T2EA {task.get('kill_chain_phase', '—')}"]
        if task.get("platform_callsign"):
            detail_parts.append(task["platform_callsign"])
        if task.get("is_time_sensitive") and task.get("tst_minutes_remaining") is not None:
            detail_parts.append(f"TST {float(task['tst_minutes_remaining']):.1f}m")
        role = str(task.get("role", "TASK"))
        items.append(
            {
                "id": f"task-{task.get('task_id', '')}",
                "kind": "task",
                "sim_offset": offset,
                "title": f"{role} → {task.get('target_name', '')}",
                "detail": " · ".join(p for p in detail_parts if p),
                "status": status,
                "entity_id": task.get("target_entity_id", ""),
                "task_id": task.get("task_id", ""),
                "lifecycle_state": lc,
                "is_tst": bool(task.get("is_time_sensitive")),
                "tst_remaining": task.get("tst_minutes_remaining"),
                "priority": int(task.get("priority", 5)),
                "platform_id": _pid(task),
                "marker": _marker_for_role(role),
                "event_kind": "strike" if _marker_for_role(role) == MARKER_CARET else "collect" if _marker_for_role(role) == MARKER_DIAMOND else "task",
            }
        )

    items.sort(key=lambda x: (float(x["sim_offset"]), 0 if x["kind"] == "scenario" else 1, x.get("priority", 5)))

    tracks = _build_aligned_tracks(
        sim_minutes=sim_minutes,
        platforms=platforms or [],
        task_rows=task_rows,
        route_threats=route_threats or [],
        fkcm_targets=fkcm_targets or [],
        scenario_items=[i for i in items if i["kind"] == "scenario"],
    )

    span = float(_DEFAULT_SPAN_MIN)
    axis_start = max(0.0, float(sim_minutes) - span * _PAST_FRACTION)
    axis_max = float(sim_minutes) + span * (1.0 - _PAST_FRACTION)

    if platforms:
        # Don't ship thousands of duplicate popup-strikes — milestone list follows lanes.
        items = _items_from_tracks(tracks, sim_minutes)

    upcoming = [
        i
        for i in items
        if i["status"] in ("future", "imminent", "open")
        or (i["kind"] == "task" and i["status"] == "active")
    ]

    return {
        "sim_minutes": round(sim_minutes, 1),
        "horizon_minutes": axis_max,
        "axis_start_minutes": round(axis_start, 1),
        "axis_max_minutes": round(axis_max, 1),
        "items": items,
        "upcoming": upcoming[:40],
        "upcoming_count": len(upcoming),
        "scenario_count": sum(1 for i in items if i["kind"] == "scenario"),
        "task_count": sum(1 for i in items if i.get("kind") in ("task", "strike", "collect")),
        "tracks": tracks,
        "past_fraction": _PAST_FRACTION,
        "zoom_spans_minutes": list(ZOOM_SPANS_MINUTES),
        "note": "25% behind NOW · 75% upcoming assigned · ◆ collect · ▼ strike · ● threat",
    }


def _items_from_tracks(tracks: list[dict[str, Any]], sim_minutes: float) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tr in tracks:
        for ev in tr.get("events") or []:
            items.append(
                {
                    "id": ev.get("id"),
                    "kind": ev.get("kind") or "task",
                    "sim_offset": ev.get("t_min"),
                    "title": ev.get("label") or "",
                    "detail": " · ".join(p for p in (tr.get("label"), ev.get("detail")) if p),
                    "status": ev.get("status") or _event_status(sim_minutes, float(ev.get("t_min") or 0), set()),
                    "entity_id": ev.get("entity_id") or tr.get("aircraft_id") or "",
                    "task_id": ev.get("task_id") or "",
                    "platform_id": tr.get("aircraft_id") or "",
                    "marker": ev.get("marker") or MARKER_CIRCLE,
                    "event_kind": ev.get("kind") or "task",
                    "is_tst": bool(ev.get("is_tst")),
                }
            )
    items.sort(key=lambda x: (float(x.get("sim_offset") or 0), x.get("title") or ""))
    return items


def _build_aligned_tracks(
    *,
    sim_minutes: float,
    platforms: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    route_threats: list[dict[str, Any]],
    fkcm_targets: list[dict[str, Any]],
    scenario_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks_by_pid: dict[str, list[dict[str, Any]]] = {}
    for task in task_rows:
        pid = _pid(task)
        if not pid:
            continue
        tasks_by_pid.setdefault(pid, []).append(task)

    threats_by_pid: dict[str, list[dict[str, Any]]] = {}
    threats_by_route: dict[str, list[dict[str, Any]]] = {}
    for row in route_threats:
        for pid in row.get("platform_ids") or []:
            threats_by_pid.setdefault(str(pid), []).append(row)
        rn = str(row.get("route_name") or "")
        if rn:
            threats_by_route.setdefault(rn, []).append(row)

    tracks: list[dict[str, Any]] = []
    for plat in platforms:
        pid = str(plat.get("platform_id") or "")
        if not pid:
            continue
        tracks.append(
            _platform_track(
                plat,
                sim_minutes=sim_minutes,
                tasks=tasks_by_pid.get(pid, []),
                threats=threats_by_pid.get(pid, []) or threats_by_route.get(str(plat.get("route_name") or ""), []),
                fkcm=[t for t in fkcm_targets if t.get("assigned_platform_id") == pid],
            )
        )

    tracks.sort(
        key=lambda tr: (
            _ROLE_ORDER.get(str(tr.get("operational_role") or "").upper(), 50),
            tr.get("label") or tr.get("aircraft_id") or "",
        )
    )

    unassigned = [t for t in task_rows if not _pid(t) and str(t.get("lifecycle_state", "")).upper() not in ("EXECUTED", "ABORTED", "COMPLETE", "CANCELLED")]
    mission_events: list[dict[str, Any]] = []
    for i, ev in enumerate(scenario_items[:20]):
        mission_events.append(
            {
                "id": ev.get("id") or f"scenario-{i}",
                "t_min": float(ev.get("sim_offset") or 0),
                "kind": "scenario",
                "marker": MARKER_FLAG,
                "label": ev.get("title") or "EVENT",
                "detail": ev.get("detail") or "",
                "entity_id": ev.get("entity_id") or "",
                "status": ev.get("status") or "future",
            }
        )
    picked_unassigned = _pick_track_tasks(unassigned, active_task_id="", sim_minutes=sim_minutes, limit=8)
    for task, t_min in picked_unassigned:
        mission_events.append(_task_event(task, t_min, sim_minutes))
    if mission_events:
        tracks.insert(
            0,
            {
                "aircraft_id": "MISSION",
                "label": "Mission",
                "aircraft_type": "scenario",
                "operational_role": "",
                "status": "live",
                "route_name": "",
                "total_minutes": sim_minutes,
                "segments": [{"t0": 0.0, "t1": sim_minutes, "from_id": "T+0", "to_id": "NOW"}],
                "events": mission_events,
            },
        )
    return tracks


def _platform_track(
    plat: dict[str, Any],
    *,
    sim_minutes: float,
    tasks: list[dict[str, Any]],
    threats: list[dict[str, Any]],
    fkcm: list[dict[str, Any]],
) -> dict[str, Any]:
    pid = str(plat.get("platform_id") or "")
    callsign = plat.get("callsign") or pid
    route = str(plat.get("route_name") or "")
    events: list[dict[str, Any]] = []
    active_id = str(plat.get("active_task_id") or "")
    for task, _seen in _pick_track_tasks(tasks, active_task_id=active_id, sim_minutes=sim_minutes):
        events.append(_task_event(task, _task_tot_time(task, sim_minutes), sim_minutes))

    seen_threats: set[str] = set()
    for row in threats:
        key = str(row.get("assessment_id") or f"{row.get('route_name')}-{row.get('threat_entity_id')}")
        if key in seen_threats:
            continue
        seen_threats.add(key)
        ttc = row.get("time_to_closest_sec")
        t_min = float(sim_minutes)
        if ttc is not None:
            try:
                t_min = float(sim_minutes) + float(ttc) / 60.0
            except (TypeError, ValueError):
                t_min = float(sim_minutes)
        nm = row.get("closest_approach_nm")
        nm_s = f"{float(nm):.1f} nm" if nm is not None else ""
        events.append(
            {
                "id": f"threat-{key}",
                "t_min": round(t_min, 2),
                "kind": "threat",
                "marker": MARKER_CIRCLE,
                "label": f"Threat {row.get('threat_entity_id') or key}",
                "detail": " · ".join(p for p in (row.get("severity"), nm_s, row.get("recommended_action")) if p),
                "entity_id": row.get("threat_entity_id") or "",
                "status": "imminent" if t_min <= sim_minutes + 2 else "future",
            }
        )

    for tgt in fkcm[:4]:
        phase = str(tgt.get("phase") or "")
        if phase in ("Target", "Engage", "Assess"):
            t_min = float(sim_minutes) + 8.0
            status = "future"
        else:
            t_min = float(sim_minutes)
            status = "active"
        events.append(
            {
                "id": f"fkcm-{tgt.get('target_id')}",
                "t_min": round(t_min, 2),
                "kind": "f2t2ea",
                "marker": MARKER_DIAMOND if phase in ("Find", "Fix", "Track") else MARKER_CARET,
                "label": f"{phase or 'F2T2EA'} · {tgt.get('target_name') or tgt.get('target_id')}",
                "detail": tgt.get("assigned_task") or tgt.get("classification") or "",
                "entity_id": tgt.get("target_id") or "",
                "status": status,
            }
        )

    events.sort(key=lambda e: (float(e.get("t_min") or 0), e.get("kind") or ""))
    if len(events) > _MAX_EVENTS_PER_TRACK:
        events = events[:_MAX_EVENTS_PER_TRACK]

    t0 = 0.0
    return {
        "aircraft_id": pid,
        "label": callsign,
        "aircraft_type": plat.get("platform_type") or "",
        "operational_role": plat.get("operational_role") or "",
        "status": plat.get("readiness") or "live",
        "route_name": route,
        "total_minutes": round(float(sim_minutes), 2),
        "segments": [{"t0": round(t0, 2), "t1": round(float(sim_minutes), 2), "from_id": "on-station", "to_id": "now"}],
        "events": events,
    }


def _pick_track_tasks(
    tasks: list[dict[str, Any]],
    *,
    active_task_id: str,
    sim_minutes: float,
    limit: int = 8,
) -> list[tuple[dict[str, Any], float]]:
    """Dedup by target; prefer active + TST + priority."""
    by_target: dict[str, dict[str, Any]] = {}
    for task in tasks:
        lc = str(task.get("lifecycle_state", "")).upper()
        if lc in ("EXECUTED", "ABORTED", "COMPLETE", "CANCELLED"):
            continue
        key = str(task.get("target_entity_id") or task.get("task_id") or "")
        if not key:
            continue
        prior = by_target.get(key)
        if prior is None:
            by_target[key] = task
            continue
        # Prefer the active task, then TST, then higher priority (lower number).
        if str(task.get("task_id")) == active_task_id:
            by_target[key] = task
        elif str(prior.get("task_id")) != active_task_id and bool(task.get("is_time_sensitive")) and not prior.get("is_time_sensitive"):
            by_target[key] = task
        elif str(prior.get("task_id")) != active_task_id and int(task.get("priority", 5)) < int(prior.get("priority", 5)):
            by_target[key] = task

    picked = list(by_target.values())
    picked.sort(
        key=lambda t: (
            0 if str(t.get("task_id")) == active_task_id else 1,
            0 if t.get("is_time_sensitive") else 1,
            int(t.get("priority", 5)),
            _task_time(t, sim_minutes),
        )
    )
    out: list[tuple[dict[str, Any], float]] = []
    for task in picked[:limit]:
        out.append((task, _task_tot_time(task, sim_minutes)))
    return out


def _task_event(task: dict[str, Any], t_min: float, sim_minutes: float) -> dict[str, Any]:
    role = str(task.get("role", "TASK"))
    marker = _marker_for_role(role)
    kind = "strike" if marker == MARKER_CARET else "collect" if marker == MARKER_DIAMOND else "task"
    return {
        "id": f"task-{task.get('task_id', '')}",
        "t_min": round(float(t_min), 2),
        "kind": kind,
        "marker": marker,
        "label": f"{role} · {task.get('target_name') or task.get('target_entity_id') or task.get('task_id')}",
        "detail": " · ".join(
            p
            for p in (
                task.get("lifecycle_state"),
                f"TST {float(task['tst_minutes_remaining']):.1f}m" if task.get("is_time_sensitive") and task.get("tst_minutes_remaining") is not None else "",
            )
            if p
        ),
        "entity_id": task.get("target_entity_id") or "",
        "task_id": task.get("task_id") or "",
        "status": _task_status(sim_minutes, task),
        "is_tst": bool(task.get("is_time_sensitive")),
    }
