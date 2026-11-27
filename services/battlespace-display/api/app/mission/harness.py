"""Mission-management feature checks aligned to Gherkin @check tags."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.mission.auth import ActorContext, require_reassign
from app.mission.service import MissionError, MissionService
from app.mission.store import MissionStore

REPO_ROOT = Path(__file__).resolve().parents[5]
SEED = REPO_ROOT / "fixtures" / "mission-management-seed-v1.json"

MISSION_FEATURE_CHECKS: list[tuple[str, str]] = [
    ("mm_support_multi", "operator support vs primary separated"),
    ("mm_retain_primary", "primary retained when adding support"),
    ("mm_single_owner", "active task has one accountable owner"),
    ("mm_reassign_ack", "reassignment awaits acknowledgement"),
    ("mm_committed", "operational committed platform unavailable for additional"),
    ("mm_reserve", "operational reserve not treated as inefficient"),
    ("mm_workload_conflict", "workload factors and conflict without score"),
    ("mm_stale", "stale telemetry flagged"),
    ("mm_unknown_ready", "unknown readiness not fabricated"),
    ("mm_unauth", "unauthorized reassignment blocked"),
    ("mm_evidence", "completion requires evidence"),
    ("mm_fleet_progress", "supervisor fleet and mission progress"),
    # Phase 2
    ("mm2_team_console", "team console primary vs support"),
    ("mm2_team_compare", "team workload comparison without score"),
    ("mm2_operator_overview", "operator workload overview"),
    ("mm2_commitments", "platform commitments and availability"),
    ("mm2_conflicts", "resource conflicts without auto-assign"),
    ("mm2_mission_progress", "mission progress with dependencies"),
]


def _fresh_service() -> MissionService:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    svc = MissionService(MissionStore(tmp.name), stale_seconds=60)
    svc.ensure_seeded(SEED)
    return svc


def verify_mission_features() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def add(check_id: str, label: str, passed: bool, detail: str = "") -> None:
        results.append({"id": check_id, "label": label, "passed": passed, "detail": detail})

    svc = _fresh_service()
    alpha = svc.store.get_operator("OP-ALPHA")
    f15 = svc.store.get_platform("COAL-F15E-01")
    add(
        "mm_support_multi",
        MISSION_FEATURE_CHECKS[0][1],
        bool(alpha)
        and "COAL-F16C-01" in (alpha.primary_platform_ids if alpha else [])
        and "COAL-F15E-01" in (alpha.support_platform_ids if alpha else [])
        and f15 is not None
        and f15.primary_operator_id == "OP-STRIKE",
        f"primary={alpha.primary_platform_ids if alpha else None}",
    )

    # Retain primary after support add (already seeded; also exercise API)
    before = list(alpha.primary_platform_ids) if alpha else []
    svc.add_platform_support(
        "COAL-A10-01",
        "OP-ALPHA",
        actor=ActorContext("OP-SUPER-1", "mission_supervisor"),
        reason="check",
    )
    alpha2 = svc.store.get_operator("OP-ALPHA")
    add(
        "mm_retain_primary",
        MISSION_FEATURE_CHECKS[1][1],
        bool(alpha2) and set(before).issubset(set(alpha2.primary_platform_ids)),
        f"primary={alpha2.primary_platform_ids if alpha2 else None}",
    )

    task = svc.store.get_task("TSK-M-SEAD-01")
    add(
        "mm_single_owner",
        MISSION_FEATURE_CHECKS[2][1],
        task is not None
        and task.accountable_owner_id == "OP-ALPHA"
        and "OP-ALPHA" not in task.supporting_operator_ids,
        f"owner={task.accountable_owner_id if task else None}",
    )

    svc.reassign_task(
        "TSK-M-SEAD-01",
        new_owner_id="OP-BRAVO",
        actor=ActorContext("OP-SUPER-1", "mission_supervisor"),
        reason="check",
        request_id="harness-reassign",
    )
    task2 = svc.store.get_task("TSK-M-SEAD-01")
    hist = svc.store.list_assignments("TSK-M-SEAD-01")
    add(
        "mm_reassign_ack",
        MISSION_FEATURE_CHECKS[3][1],
        task2 is not None
        and task2.accountable_owner_id == "OP-ALPHA"
        and task2.pending_owner_id == "OP-BRAVO"
        and any(a.assignment_status == "pending_ack" for a in hist)
        and any(a.assignment_status == "superseded" for a in hist),
        f"pending={task2.pending_owner_id if task2 else None}",
    )

    picture = {
        "harness_mode": True,
        "platforms": [
            {
                "platform_id": "COAL-F16C-01",
                "readiness": "GREEN",
                "active_task_id": "TSK-HARNESS-01",
                "callsign": "VIPER01",
            },
            {"platform_id": "COAL-KC135-01", "readiness": "GREEN", "active_task_id": "", "callsign": "TEXACO01"},
            {"platform_id": "COAL-A10-01", "readiness": None, "stale": True, "callsign": "HOG01"},
        ],
    }
    fleet = svc.build_fleet_overview(picture)
    by_id = {r["platform_id"]: r for r in fleet["platforms"]}
    add(
        "mm_committed",
        MISSION_FEATURE_CHECKS[4][1],
        by_id["COAL-F16C-01"]["operational_availability"]["state"] == "unavailable_for_additional"
        and fleet["counts"]["committed"] >= 1,
        str(by_id["COAL-F16C-01"]["operational_availability"]),
    )
    add(
        "mm_reserve",
        MISSION_FEATURE_CHECKS[5][1],
        by_id["COAL-KC135-01"]["held_in_reserve"]
        and by_id["COAL-KC135-01"]["operational_availability"]["state"] == "available_reserved",
        str(by_id["COAL-KC135-01"]["operational_availability"]),
    )

    wl = svc.build_operator_workload("OP-ALPHA")
    add(
        "mm_workload_conflict",
        MISSION_FEATURE_CHECKS[6][1],
        wl.get("workload_score") is None and bool(wl.get("conflict_indicator")) and "primary_aircraft" in wl.get("factors", {}),
        f"conflict={wl.get('conflict_indicator')}",
    )

    add(
        "mm_stale",
        MISSION_FEATURE_CHECKS[7][1],
        bool(by_id["COAL-A10-01"]["stale"]) and by_id["COAL-A10-01"]["technical_readiness"] == "Unknown",
        f"stale={by_id['COAL-A10-01']['stale']}",
    )
    add(
        "mm_unknown_ready",
        MISSION_FEATURE_CHECKS[8][1],
        by_id["COAL-A10-01"]["technical_readiness"] == "Unknown",
        by_id["COAL-A10-01"]["technical_readiness"],
    )

    unauth_ok = False
    try:
        require_reassign(ActorContext("AN-1", "analyst"))
    except Exception as exc:
        unauth_ok = getattr(exc, "status_code", None) == 403
    add("mm_unauth", MISSION_FEATURE_CHECKS[9][1], unauth_ok, "403 expected")

    evidence_ok = False
    try:
        svc.complete_task("TSK-M-STRIKE-01", actor=ActorContext("OP-STRIKE", "operator"), evidence="")
    except MissionError:
        evidence_ok = True
    if evidence_ok:
        done = svc.complete_task(
            "TSK-M-STRIKE-01",
            actor=ActorContext("OP-STRIKE", "operator"),
            evidence="egress confirm",
        )
        evidence_ok = done.status == "COMPLETED" and any(
            e.event_type == "task.completed" for e in svc.store.list_audit("task", "TSK-M-STRIKE-01")
        )
    add("mm_evidence", MISSION_FEATURE_CHECKS[10][1], evidence_ok, "evidence gate")

    prog = svc.build_mission_progress("MSN-GULF-01")
    add(
        "mm_fleet_progress",
        MISSION_FEATURE_CHECKS[11][1],
        fleet["counts"]["total"] >= 3
        and prog["milestone_completion"]["denominator"] >= 1
        and "criteria" in prog["note"].lower(),
        f"total={fleet['counts']['total']} milestones={prog['milestone_completion']}",
    )

    # --- Phase 2 (fresh store so Phase 1 mutations do not mask seed conflicts) ---
    svc2 = _fresh_service()
    team = svc2.build_team_console("TEAM-SEAD")
    add(
        "mm2_team_console",
        MISSION_FEATURE_CHECKS[12][1],
        len(team["primary_aircraft"]) >= 1
        and team["workload"].get("workload_score") is None
        and "Primary ownership" in team.get("note", ""),
        f"primary={len(team['primary_aircraft'])} support={len(team['supported_aircraft'])}",
    )

    teams = svc2.build_teams_overview()
    add(
        "mm2_team_compare",
        MISSION_FEATURE_CHECKS[13][1],
        len(teams["teams"]) >= 2
        and all(t.get("relative_load") in ("higher", "lower", "typical") for t in teams["teams"])
        and all(t["workload"].get("workload_score") is None for t in teams["teams"]),
        f"teams={len(teams['teams'])} median={teams.get('median_active_tasks')}",
    )

    ow = svc2.build_operators_workload_overview()
    add(
        "mm2_operator_overview",
        MISSION_FEATURE_CHECKS[14][1],
        ow.get("workload_score") is None and ow.get("conflict_count", 0) >= 1,
        f"conflict_count={ow.get('conflict_count')}",
    )

    pic = {
        "harness_mode": True,
        "platforms": [
            {"platform_id": "COAL-F16C-01", "readiness": "GREEN", "active_task_id": "TSK-HARNESS-01"},
            {"platform_id": "COAL-KC135-01", "readiness": "GREEN", "active_task_id": ""},
            {"platform_id": "COAL-F15E-01", "readiness": "GREEN", "active_task_id": ""},
        ],
    }
    c_f16 = svc2.build_platform_commitments("COAL-F16C-01", pic)
    c_tank = svc2.build_platform_commitments("COAL-KC135-01", pic)
    c_strike = svc2.build_platform_commitments("COAL-F15E-01", pic)
    add(
        "mm2_commitments",
        MISSION_FEATURE_CHECKS[15][1],
        c_f16["operational_availability"]["state"] == "unavailable_for_additional"
        and c_tank["operational_availability"]["state"] == "available_reserved"
        and bool(c_strike["operational_availability"].get("estimated_available_at")),
        f"f16={c_f16['operational_availability']['state']} tanker={c_tank['operational_availability']['state']}",
    )

    conflicts = svc2.build_resource_conflicts(pic)
    kinds = {c["kind"] for c in conflicts["conflicts"]}
    add(
        "mm2_conflicts",
        MISSION_FEATURE_CHECKS[16][1],
        "blocked_task" in kinds
        and "operator_workload" in kinds
        and all(c.get("auto_action") is None for c in conflicts["conflicts"]),
        f"kinds={sorted(kinds)} total={conflicts['total']}",
    )

    prog2 = svc2.build_mission_progress("MSN-GULF-01")
    add(
        "mm2_mission_progress",
        MISSION_FEATURE_CHECKS[17][1],
        prog2.get("task_counts", {}).get("blocked", 0) >= 1
        and isinstance(prog2.get("dependencies"), list)
        and "criteria" in prog2.get("note", "").lower(),
        f"blocked={prog2.get('task_counts', {}).get('blocked')} deps={len(prog2.get('dependencies') or [])}",
    )
    return results


def all_mission_features_pass(results: list[dict[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
