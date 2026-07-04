"""Deterministic battlespace-display harness focused on F2T2EA / TST / tasking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.oms_ai_services import build_offline_registry_rows, load_service_registry
from app.picture_contract import assert_picture_contract
from app.timeline import build_timeline_view

_REPO_ROOT = Path(__file__).resolve().parents[4]
_HARNESS_SCENARIO = _REPO_ROOT / "fixtures" / "battlespace-harness-scenario-v1.json"

BATTLESPACE_FEATURE_CHECKS: list[tuple[str, str]] = [
    ("picture_contract", "picture passes contract validation"),
    ("tst_tasks", "TST tasks in task_rows"),
    ("unassigned_tasks", "unassigned tasks present"),
    ("high_priority_unassigned", "high-priority unassigned tasks"),
    ("fkcm_targets", "FKCM targets with F2T2EA phases"),
    ("mission_thread", "mission_thread F2T2EA phases"),
    ("attention_tst", "TST items in attention queue"),
    ("timeline_view", "timeline_view populated"),
]


def load_harness_document() -> dict[str, Any]:
    return json.loads(_HARNESS_SCENARIO.read_text(encoding="utf-8"))


def _is_unassigned_task(row: dict[str, Any]) -> bool:
    lc = row.get("lifecycle_state", "NEW")
    if lc in ("EXECUTED", "ABORTED"):
        return False
    return not row.get("assigned_platform_id")


def _is_high_priority(row: dict[str, Any], max_priority: int = 2) -> bool:
    return int(row.get("priority", 99)) <= max_priority


def build_harness_picture(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    data = doc or load_harness_document()
    base = dict(data.get("picture") or {})
    sim_minutes = float(data.get("sim_minutes", base.get("sim_minutes", 0)))
    timeline = data.get("scenario_timeline") or []
    fired = {int(ev.get("simOffsetMinutes", 0)) for ev in timeline if sim_minutes >= float(ev.get("simOffsetMinutes", 0))}

    timeline_view = build_timeline_view(
        sim_minutes=sim_minutes,
        scenario_timeline=timeline,
        fired_offsets=fired,
        task_rows=list(base.get("task_rows") or []),
    )

    picture = {
        **base,
        "sim_minutes": sim_minutes,
        "timeline_view": timeline_view,
        "harness_mode": True,
        "advisor_mode": "off",
        "advisor_suggestions": [],
        "advisor_isr_assignments": [],
        "oms_ai_services": base.get("oms_ai_services")
        or build_offline_registry_rows(),
        "oms_ai_summary": base.get("oms_ai_summary")
        or {
            "live_count": 0,
            "total_services": len(load_service_registry()),
            "offline_count": len(load_service_registry()),
            "unconfigured_count": 0,
            "open_recommendations": 0,
            "isr_assignments": 0,
            "any_live": False,
        },
    }
    assert_picture_contract(picture)
    return picture


def verify_battlespace_features(picture: dict[str, Any], expected: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    expected = expected or load_harness_document().get("expected_features") or {}
    results: list[dict[str, Any]] = []

    def _add(check_id: str, label: str, passed: bool, detail: str = "") -> None:
        results.append({"id": check_id, "label": label, "passed": passed, "detail": detail})

    contract_errors: list[str] = []
    try:
        assert_picture_contract(picture)
    except AssertionError as exc:
        contract_errors = [str(exc)]
    _add("picture_contract", BATTLESPACE_FEATURE_CHECKS[0][1], not contract_errors, "; ".join(contract_errors))

    tasks = picture.get("task_rows") or []
    tst = [t for t in tasks if t.get("is_time_sensitive") and t.get("lifecycle_state") != "EXECUTED"]
    _add(
        "tst_tasks",
        BATTLESPACE_FEATURE_CHECKS[1][1],
        len(tst) >= expected.get("min_tst_tasks", 1),
        f"tst={len(tst)}",
    )

    unassigned = [t for t in tasks if _is_unassigned_task(t)]
    _add(
        "unassigned_tasks",
        BATTLESPACE_FEATURE_CHECKS[2][1],
        len(unassigned) >= expected.get("min_unassigned_tasks", 1),
        f"unassigned={len(unassigned)}",
    )

    hp_unassigned = [t for t in tasks if _is_unassigned_task(t) and _is_high_priority(t)]
    _add(
        "high_priority_unassigned",
        BATTLESPACE_FEATURE_CHECKS[3][1],
        len(hp_unassigned) >= expected.get("min_high_priority_unassigned", 1),
        f"hp_unassigned={len(hp_unassigned)}",
    )

    fkcm = picture.get("fkcm_targets") or []
    phases = {t.get("phase") for t in fkcm}
    required_phases = set(expected.get("required_phases") or ["Find", "Target"])
    _add(
        "fkcm_targets",
        BATTLESPACE_FEATURE_CHECKS[4][1],
        len(fkcm) >= expected.get("min_fkcm_targets", 1) and required_phases.issubset(phases),
        f"targets={len(fkcm)} phases={sorted(phases)}",
    )

    mt = picture.get("mission_thread") or {}
    _add(
        "mission_thread",
        BATTLESPACE_FEATURE_CHECKS[5][1],
        bool(mt.get("f2t2ea_phases")) and bool(mt.get("phase_counts")),
        f"dominant={mt.get('dominant_phase')}",
    )

    attn_tst = [a for a in (picture.get("attention_queue") or []) if a.get("kind") == "TST"]
    _add(
        "attention_tst",
        BATTLESPACE_FEATURE_CHECKS[6][1],
        len(attn_tst) >= expected.get("min_attention_tst", 1),
        f"attention_tst={len(attn_tst)}",
    )

    tv = picture.get("timeline_view") or {}
    _add(
        "timeline_view",
        BATTLESPACE_FEATURE_CHECKS[7][1],
        "items" in tv and tv.get("sim_minutes") is not None,
        f"items={len(tv.get('items') or [])}",
    )
    return results


def all_features_pass(results: list[dict[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
