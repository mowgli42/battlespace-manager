"""Unified operator timeline: scenario beats + open tasks."""

from __future__ import annotations

from typing import Any


def _event_status(sim_minutes: float, offset: int, fired_offsets: set[int]) -> str:
    if offset in fired_offsets or sim_minutes >= offset + 0.5:
        return "past"
    if sim_minutes >= offset - 2:
        return "imminent"
    return "future"


def _task_status(sim_minutes: float, task: dict[str, Any]) -> str:
    lc = task.get("lifecycle_state", "")
    if lc in ("EXECUTED", "ABORTED"):
        return "past"
    assigned = task.get("assigned_at_sim")
    if assigned is not None and float(assigned) <= sim_minutes:
        return "active"
    return "open"


def build_timeline_view(
    *,
    sim_minutes: float,
    scenario_timeline: list[dict[str, Any]],
    fired_offsets: set[int] | list[int],
    task_rows: list[dict[str, Any]],
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
        assigned = task.get("assigned_at_sim")
        offset = int(float(assigned)) if assigned is not None else int(sim_minutes)
        status = _task_status(sim_minutes, task)
        detail_parts = [lc, f"F2T2EA {task.get('kill_chain_phase', '—')}"]
        if task.get("platform_callsign"):
            detail_parts.append(task["platform_callsign"])
        if task.get("is_time_sensitive") and task.get("tst_minutes_remaining") is not None:
            detail_parts.append(f"TST {float(task['tst_minutes_remaining']):.1f}m")
        items.append(
            {
                "id": f"task-{task.get('task_id', '')}",
                "kind": "task",
                "sim_offset": offset,
                "title": f"{task.get('role', 'TASK')} → {task.get('target_name', '')}",
                "detail": " · ".join(detail_parts),
                "status": status,
                "entity_id": task.get("target_entity_id", ""),
                "task_id": task.get("task_id", ""),
                "lifecycle_state": lc,
                "is_tst": bool(task.get("is_time_sensitive")),
                "tst_remaining": task.get("tst_minutes_remaining"),
                "priority": int(task.get("priority", 5)),
            }
        )

    items.sort(key=lambda x: (x["sim_offset"], 0 if x["kind"] == "scenario" else 1, x.get("priority", 5)))

    horizon = max((i["sim_offset"] for i in items), default=int(sim_minutes)) + 10
    upcoming = [
        i
        for i in items
        if i["status"] in ("future", "imminent", "open")
        or (i["kind"] == "task" and i["status"] == "active")
    ]

    return {
        "sim_minutes": round(sim_minutes, 1),
        "horizon_minutes": horizon,
        "items": items,
        "upcoming": upcoming[:40],
        "upcoming_count": len(upcoming),
        "scenario_count": sum(1 for i in items if i["kind"] == "scenario"),
        "task_count": sum(1 for i in items if i["kind"] == "task"),
    }
