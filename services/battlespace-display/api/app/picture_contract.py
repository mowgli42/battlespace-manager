"""Operator picture JSON contract for /api/picture and SSE stream."""

from __future__ import annotations

from typing import Any

# Top-level keys required for battlespace-display UI tabs and rails.
PICTURE_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "sim_minutes",
        "entities",
        "threat_picture",
        "mission_thread",
        "attention_queue",
        "fkcm_targets",
        "timeline_view",
        "task_rows",
    }
)

# Keys validated when present (full API payload includes additional fields).
PICTURE_TYPED_KEYS: dict[str, type | tuple[type, ...]] = {
    "sim_minutes": (int, float),
    "entities": list,
    "threat_picture": dict,
    "mission_thread": dict,
    "attention_queue": list,
    "fkcm_targets": list,
    "timeline_view": dict,
    "task_rows": list,
}


def validate_picture(payload: dict[str, Any]) -> list[str]:
    """Return human-readable contract violations (empty if valid)."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a dict"]

    missing = sorted(PICTURE_REQUIRED_KEYS - set(payload.keys()))
    for key in missing:
        errors.append(f"missing required key: {key}")

    for key, expected in PICTURE_TYPED_KEYS.items():
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(expected, tuple):
            if not isinstance(value, expected):
                errors.append(f"{key} must be {expected}, got {type(value).__name__}")
        elif not isinstance(value, expected):
            errors.append(f"{key} must be {expected.__name__}, got {type(value).__name__}")

    tp = payload.get("threat_picture")
    if isinstance(tp, dict):
        for field in ("entity_count", "active_tasks"):
            if field not in tp:
                errors.append(f"threat_picture missing {field}")

    mt = payload.get("mission_thread")
    if isinstance(mt, dict):
        for field in ("f2t2ea_phases", "phase_counts"):
            if field not in mt:
                errors.append(f"mission_thread missing {field}")

    tv = payload.get("timeline_view")
    if isinstance(tv, dict):
        for field in ("sim_minutes", "items", "upcoming_count"):
            if field not in tv:
                errors.append(f"timeline_view missing {field}")

    return errors


def assert_picture_contract(payload: dict[str, Any]) -> None:
    errors = validate_picture(payload)
    if errors:
        raise AssertionError("; ".join(errors))


def picture_from_snapshot(
    snap: Any,
    *,
    scenario_timeline: list[dict[str, Any]] | None = None,
    fired_offsets: set[int] | list[int] | None = None,
    attention_queue: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build contract-shaped picture dict from GulfWarEngine snapshot (no advisor merge)."""
    from app.timeline import build_timeline_view

    timeline = scenario_timeline if scenario_timeline is not None else []
    fired = fired_offsets if fired_offsets is not None else set()
    attention = attention_queue if attention_queue is not None else list(snap.attention_queue)
    timeline_view = build_timeline_view(
        sim_minutes=float(snap.sim_minutes),
        scenario_timeline=timeline,
        fired_offsets=fired,
        task_rows=list(snap.task_rows),
    )
    return {
        "sim_minutes": snap.sim_minutes,
        "entities": snap.entities,
        "threat_picture": snap.threat_picture,
        "mission_thread": snap.mission_thread,
        "attention_queue": attention,
        "fkcm_targets": snap.fkcm_targets,
        "timeline_view": timeline_view,
        "task_rows": snap.task_rows,
    }
