"""Phase 2 resource-management views: team console, workload comparison, conflicts."""

from __future__ import annotations

from typing import Any

from app.mission.models import TASK_ACTIVE_STATUSES, PlatformOrg, map_technical_readiness
from app.mission.store import MissionStore, new_id, utc_now

COMMITTING = frozenset({"ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"})


class ResourceViews:
    """Read-model builders over MissionStore + optional COP picture."""

    def __init__(self, store: MissionStore, *, stale_seconds: int = 120) -> None:
        self.store = store
        self.stale_seconds = stale_seconds

    def _pic_platforms(self, picture: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        picture = picture or {}
        return {p.get("platform_id"): p for p in (picture.get("platforms") or []) if p.get("platform_id")}

    def _platform_freshness(
        self, plat: PlatformOrg, pic: dict[str, Any], picture: dict[str, Any]
    ) -> dict[str, Any]:
        import time
        from datetime import datetime

        tech = map_technical_readiness(pic.get("readiness") if pic else None)
        if not pic:
            tech = "Unknown"
        last_raw = pic.get("last_update_time") or pic.get("updated_at") or picture.get("received_at") or ""
        stale = False
        if pic and last_raw:
            try:
                text = str(last_raw)
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                stale = (time.time() - datetime.fromisoformat(text).timestamp()) > self.stale_seconds
            except ValueError:
                stale = bool(pic.get("stale"))
        elif pic and picture.get("harness_mode"):
            stale = bool(pic.get("stale"))
        elif not pic:
            stale = True
        return {
            "technical_readiness": tech,
            "last_update_time": last_raw,
            "stale": stale,
            "callsign": pic.get("callsign") or "",
            "cop_active_task_id": pic.get("active_task_id") or "",
        }

    def _operator_factors(self, operator_id: str) -> dict[str, Any]:
        op = self.store.get_operator(operator_id)
        if op is None:
            return {}
        tasks = [
            t
            for t in self.store.list_tasks()
            if t.accountable_owner_id == operator_id
            or operator_id in (t.supporting_operator_ids or [])
            or t.pending_owner_id == operator_id
        ]
        active = [t for t in tasks if t.status in TASK_ACTIVE_STATUSES]
        pending_ack = [t for t in tasks if t.pending_owner_id == operator_id]
        time_sensitive = [t for t in active if t.priority <= 2]
        alerts = [
            a
            for a in self.store.list_alerts()
            if a.resolution_status == "open"
            and (
                (a.entity_type == "operator" and a.entity_id == operator_id)
                or (
                    a.entity_type == "platform"
                    and a.entity_id in (op.primary_platform_ids + op.support_platform_ids)
                )
            )
        ]
        conflict = (
            len(op.primary_platform_ids) >= 1
            and len(op.support_platform_ids) >= 1
            and len(active) >= 2
        )
        return {
            "operator_id": operator_id,
            "name": op.name,
            "availability_state": op.availability_state,
            "primary_aircraft": list(op.primary_platform_ids),
            "supported_aircraft": list(op.support_platform_ids),
            "active_tasks": len(active),
            "pending_acknowledgements": len(pending_ack),
            "time_sensitive_tasks": len(time_sensitive),
            "unresolved_exceptions": len(alerts),
            "conflict_indicator": conflict,
            "workload_score": None,
        }

    def build_team_console(self, team_id: str, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        team = self.store.get_team(team_id)
        if team is None:
            from app.mission.service import MissionError

            raise MissionError(f"Unknown team {team_id}", 404)

        picture = picture or {}
        pic_map = self._pic_platforms(picture)
        primary_platforms: list[dict[str, Any]] = []
        supported_platforms: list[dict[str, Any]] = []

        for plat in self.store.list_platforms():
            fresh = self._platform_freshness(plat, pic_map.get(plat.platform_id) or {}, picture)
            row = {
                "platform_id": plat.platform_id,
                "platform_type": plat.platform_type,
                "primary_operator_id": plat.primary_operator_id,
                "support_operator_ids": list(plat.support_operator_ids),
                "held_in_reserve": plat.held_in_reserve,
                "active_commitments": list(plat.active_commitments or []),
                **fresh,
            }
            if plat.primary_team_id == team_id:
                primary_platforms.append(row)
            elif any(
                self.store.get_operator(oid)
                and team_id in (self.store.get_operator(oid).team_memberships if self.store.get_operator(oid) else [])
                for oid in plat.support_operator_ids
            ):
                # Support via team members supporting other teams' platforms
                supported_platforms.append(row)

        # Also include platforms where team is in task supporting_team_ids but not primary
        for plat in self.store.list_platforms():
            if plat.primary_team_id == team_id:
                continue
            if any(p["platform_id"] == plat.platform_id for p in supported_platforms):
                continue
            for t in self.store.list_tasks():
                if team_id in (t.supporting_team_ids or []) and plat.platform_id in (
                    t.associated_platform_ids or []
                ):
                    fresh = self._platform_freshness(plat, pic_map.get(plat.platform_id) or {}, picture)
                    supported_platforms.append(
                        {
                            "platform_id": plat.platform_id,
                            "platform_type": plat.platform_type,
                            "primary_operator_id": plat.primary_operator_id,
                            "support_operator_ids": list(plat.support_operator_ids),
                            "held_in_reserve": plat.held_in_reserve,
                            "active_commitments": list(plat.active_commitments or []),
                            **fresh,
                        }
                    )
                    break

        members = []
        primary_ops: list[str] = []
        support_ops: list[str] = []
        for oid in team.membership:
            op = self.store.get_operator(oid)
            if not op:
                continue
            factors = self._operator_factors(oid)
            members.append({"operator": op.to_dict(), "factors": factors})
            if op.primary_platform_ids:
                primary_ops.append(oid)
            if op.support_platform_ids:
                support_ops.append(oid)

        team_tasks = [
            t
            for t in self.store.list_tasks()
            if team_id in (t.supporting_team_ids or [])
            or any(
                self.store.get_platform(pid) and self.store.get_platform(pid).primary_team_id == team_id
                for pid in (t.associated_platform_ids or [])
            )
        ]
        active = [t for t in team_tasks if t.status in TASK_ACTIVE_STATUSES]
        pending_ack = [t for t in team_tasks if t.pending_owner_id]
        blocked = [t for t in team_tasks if t.status == "BLOCKED"]
        mission_ids = sorted({t.mission_id for t in team_tasks if t.mission_id})

        alerts = [
            a
            for a in self.store.list_alerts()
            if a.resolution_status == "open"
            and (
                (a.entity_type == "team" and a.entity_id == team_id)
                or (
                    a.entity_type == "platform"
                    and a.entity_id in {p["platform_id"] for p in primary_platforms + supported_platforms}
                )
                or (a.entity_type == "operator" and a.entity_id in team.membership)
            )
        ]

        workload = {
            "active_tasks": len(active),
            "pending_acknowledgements": len(pending_ack),
            "blocked_tasks": len(blocked),
            "primary_platforms": len(primary_platforms),
            "supported_platforms": len(supported_platforms),
            "operators_with_conflict": sum(
                1 for m in members if m["factors"].get("conflict_indicator")
            ),
            "unresolved_exceptions": len(alerts),
            "stale_platforms": sum(
                1 for p in primary_platforms + supported_platforms if p.get("stale")
            ),
            "workload_score": None,
            "note": "Team workload uses factor aggregates only; not a validated capacity score.",
        }

        return {
            "team": team.to_dict(),
            "primary_aircraft": primary_platforms,
            "supported_aircraft": supported_platforms,
            "primary_operators": primary_ops,
            "supporting_operators": support_ops,
            "members": members,
            "current_missions": [
                m.to_dict() for m in self.store.list_missions() if m.mission_id in mission_ids
            ],
            "active_tasks": [t.to_dict() for t in active],
            "pending_acknowledgements": [t.to_dict() for t in pending_ack],
            "blocked_tasks": [t.to_dict() for t in blocked],
            "alerts": [a.to_dict() for a in alerts],
            "workload": workload,
            "generated_at": utc_now(),
            "note": "Primary ownership is listed separately from support; supporting another platform does not hide primary responsibilities.",
        }

    def build_teams_overview(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        teams = []
        for team in self.store.list_teams():
            console = self.build_team_console(team.team_id, picture)
            teams.append(
                {
                    "team_id": team.team_id,
                    "name": team.name,
                    "supervisor_id": team.supervisor_id,
                    "status": team.status,
                    "workload": console["workload"],
                    "primary_aircraft_count": len(console["primary_aircraft"]),
                    "supported_aircraft_count": len(console["supported_aircraft"]),
                    "active_task_count": console["workload"]["active_tasks"],
                    "pending_actions": console["workload"]["pending_acknowledgements"]
                    + console["workload"]["blocked_tasks"],
                    "unresolved_exceptions": console["workload"]["unresolved_exceptions"],
                    "imbalance_indicator": console["workload"]["operators_with_conflict"] > 0
                    or console["workload"]["blocked_tasks"] > 0,
                }
            )
        # Comparison: flag teams above median active tasks as higher load (factor-based, not a score)
        active_counts = sorted(t["active_task_count"] for t in teams) or [0]
        median = active_counts[len(active_counts) // 2]
        for t in teams:
            t["relative_load"] = (
                "higher"
                if t["active_task_count"] > median
                else ("lower" if t["active_task_count"] < median else "typical")
            )
            t["relative_load_note"] = (
                f"Compared to team median active_tasks={median}; not a capacity score."
            )
        return {
            "teams": teams,
            "median_active_tasks": median,
            "generated_at": utc_now(),
            "note": "Team comparisons use explicit factor aggregates only.",
        }

    def build_operators_workload_overview(self) -> dict[str, Any]:
        rows = []
        for op in self.store.list_operators():
            # Skip pure supervisors with no platform responsibilities for cleaner overview
            factors = self._operator_factors(op.operator_id)
            rows.append(
                {
                    "operator": op.to_dict(),
                    "factors": factors,
                    "conflict_indicator": factors.get("conflict_indicator", False),
                    "workload_score": None,
                }
            )
        conflicted = [r for r in rows if r["conflict_indicator"]]
        return {
            "operators": rows,
            "conflict_count": len(conflicted),
            "generated_at": utc_now(),
            "workload_score": None,
            "note": "Estimated contributing factors only; do not treat as validated human-factors capacity.",
        }

    def build_platform_commitments(
        self, platform_id: str, picture: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        plat = self.store.get_platform(platform_id)
        if plat is None:
            from app.mission.service import MissionError

            raise MissionError(f"Unknown platform {platform_id}", 404)
        picture = picture or {}
        pic = self._pic_platforms(picture).get(platform_id) or {}
        fresh = self._platform_freshness(plat, pic, picture)
        tasks = [
            t
            for t in self.store.list_tasks()
            if platform_id in (t.associated_platform_ids or []) and t.status in COMMITTING
        ]
        commitments = list(plat.active_commitments or [])
        scheduled = [c for c in commitments if c.get("status") == "scheduled"]
        active = [c for c in commitments if c.get("status", "active") == "active"]
        estimated = [
            c.get("estimated_available_at")
            for c in commitments
            if c.get("estimated_available_at")
        ]
        committing = len(tasks) + (1 if pic.get("active_task_id") else 0)
        if plat.held_in_reserve and committing == 0:
            avail_state = "available_reserved"
            avail_reason = "held in reserve"
            can_accept = True
        elif fresh["technical_readiness"] in ("Unavailable", "Unknown"):
            avail_state = "unavailable"
            avail_reason = f"technical readiness is {fresh['technical_readiness']}"
            can_accept = False
        elif committing > 0 or active:
            avail_state = "unavailable_for_additional"
            avail_reason = "active commitment or task"
            can_accept = False
        else:
            avail_state = "available"
            avail_reason = "operationally available"
            can_accept = True

        return {
            "platform_id": platform_id,
            "technical_readiness": fresh["technical_readiness"],
            "operational_availability": {
                "state": avail_state,
                "reason": avail_reason,
                "can_accept_additional": can_accept,
                "held_in_reserve": plat.held_in_reserve,
                "estimated_available_at": estimated[0] if estimated else "",
            },
            "active_commitments": active,
            "scheduled_commitments": scheduled,
            "committing_tasks": [t.to_dict() for t in tasks],
            "cop_active_task_id": fresh["cop_active_task_id"],
            "stale": fresh["stale"],
            "last_update_time": fresh["last_update_time"],
            "note": "Technical readiness and operational availability are separate concepts.",
        }

    def upsert_commitment(
        self,
        platform_id: str,
        payload: dict[str, Any],
        *,
        actor_id: str,
    ) -> dict[str, Any]:
        plat = self.store.get_platform(platform_id)
        if plat is None:
            from app.mission.service import MissionError

            raise MissionError(f"Unknown platform {platform_id}", 404)
        cid = str(payload.get("commitment_id") or new_id("C"))
        entry = {
            "commitment_id": cid,
            "label": str(payload.get("label") or ""),
            "kind": str(payload.get("kind") or "scheduled"),
            "task_id": str(payload.get("task_id") or ""),
            "effective_start": str(payload.get("effective_start") or ""),
            "effective_end": str(payload.get("effective_end") or ""),
            "estimated_available_at": str(payload.get("estimated_available_at") or ""),
            "status": str(payload.get("status") or "scheduled"),
            "updated_by": actor_id,
            "updated_at": utc_now(),
        }
        commitments = [c for c in (plat.active_commitments or []) if c.get("commitment_id") != cid]
        commitments.append(entry)
        plat.active_commitments = commitments
        # Scheduled/active work clears reserve unless explicitly reserved hold
        if entry["kind"] != "reserve_hold" and entry["status"] in ("active", "scheduled"):
            if entry["status"] == "active":
                plat.held_in_reserve = False
        self.store.upsert_platform(plat)
        return entry

    def build_resource_conflicts(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        picture = picture or {}
        conflicts: list[dict[str, Any]] = []

        # Operator primary+support overload
        for op in self.store.list_operators():
            factors = self._operator_factors(op.operator_id)
            if factors.get("conflict_indicator"):
                conflicts.append(
                    {
                        "conflict_id": f"op-load-{op.operator_id}",
                        "severity": "Attention",
                        "kind": "operator_workload",
                        "entity_type": "operator",
                        "entity_id": op.operator_id,
                        "description": (
                            f"{op.name} has primary and support aircraft with multiple active tasks"
                        ),
                        "factors": factors,
                        "recommendation": "Review task priority before assigning additional work; do not auto-reassign.",
                        "auto_action": None,
                    }
                )

        # Platform operational but fully committed vs request window
        for plat in self.store.list_platforms():
            detail = self.build_platform_commitments(plat.platform_id, picture)
            if detail["operational_availability"]["state"] == "unavailable_for_additional":
                if detail["technical_readiness"] == "Operational":
                    conflicts.append(
                        {
                            "conflict_id": f"plat-commit-{plat.platform_id}",
                            "severity": "Informational",
                            "kind": "platform_fully_committed",
                            "entity_type": "platform",
                            "entity_id": plat.platform_id,
                            "description": f"{plat.platform_id} is operational but unavailable for additional commitment",
                            "factors": detail["operational_availability"],
                            "recommendation": "Select an uncommitted operational platform or wait for estimated_available_at.",
                            "auto_action": None,
                        }
                    )
            if detail.get("stale"):
                conflicts.append(
                    {
                        "conflict_id": f"plat-stale-{plat.platform_id}",
                        "severity": "Attention",
                        "kind": "stale_telemetry",
                        "entity_type": "platform",
                        "entity_id": plat.platform_id,
                        "description": f"{plat.platform_id} telemetry is stale or missing",
                        "factors": {"last_update_time": detail.get("last_update_time")},
                        "recommendation": "Treat readiness as uncertain until a fresh update arrives.",
                        "auto_action": None,
                    }
                )

        # Blocked tasks without owner attention
        for task in self.store.list_tasks():
            if task.status == "BLOCKED":
                conflicts.append(
                    {
                        "conflict_id": f"task-block-{task.task_id}",
                        "severity": "Critical",
                        "kind": "blocked_task",
                        "entity_type": "task",
                        "entity_id": task.task_id,
                        "description": task.blocker_reason or "Task blocked",
                        "factors": {
                            "accountable_owner_id": task.accountable_owner_id,
                            "platforms": list(task.associated_platform_ids),
                        },
                        "recommendation": "Resolve blocker or reassign with acknowledgement.",
                        "auto_action": None,
                    }
                )
            if task.pending_owner_id:
                conflicts.append(
                    {
                        "conflict_id": f"task-ack-{task.task_id}",
                        "severity": "Attention",
                        "kind": "pending_acknowledgement",
                        "entity_type": "task",
                        "entity_id": task.task_id,
                        "description": f"Reassignment pending acknowledgement by {task.pending_owner_id}",
                        "factors": {
                            "current_owner": task.accountable_owner_id,
                            "pending_owner": task.pending_owner_id,
                        },
                        "recommendation": "Await acknowledgement; ownership has not transferred.",
                        "auto_action": None,
                    }
                )

        # Team imbalance: relative_load higher + conflict operators
        overview = self.build_teams_overview(picture)
        for t in overview["teams"]:
            if t.get("imbalance_indicator") and t.get("relative_load") == "higher":
                conflicts.append(
                    {
                        "conflict_id": f"team-imbalance-{t['team_id']}",
                        "severity": "Attention",
                        "kind": "team_imbalance",
                        "entity_type": "team",
                        "entity_id": t["team_id"],
                        "description": f"{t['name']} has higher-than-median active tasks with unresolved workload conflicts",
                        "factors": t["workload"],
                        "recommendation": "Compare team factors; rebalance only via authorized human assignment.",
                        "auto_action": None,
                    }
                )

        by_sev = {"Critical": 0, "Attention": 0, "Informational": 0}
        for c in conflicts:
            by_sev[c["severity"]] = by_sev.get(c["severity"], 0) + 1

        return {
            "conflicts": conflicts,
            "counts": by_sev,
            "total": len(conflicts),
            "generated_at": utc_now(),
            "note": "Conflicts are indicators and recommendations only; the system never auto-assigns or reassigns.",
        }

    def build_mission_progress_enriched(self, mission_id: str) -> dict[str, Any]:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            from app.mission.service import MissionError

            raise MissionError(f"Unknown mission {mission_id}", 404)
        tasks = [t for t in self.store.list_tasks() if t.mission_id == mission_id]
        milestones = list(mission.required_milestones or [])
        completed_ms = [m for m in milestones if m.get("status") == "completed"]
        now = utc_now()
        by_status = {
            "completed": [t for t in tasks if t.status == "COMPLETED"],
            "in_progress": [t for t in tasks if t.status in ("IN_PROGRESS", "ACCEPTED", "ASSIGNED")],
            "blocked": [t for t in tasks if t.status == "BLOCKED"],
            "deferred": [t for t in tasks if t.status == "DEFERRED"],
            "overdue": [
                t
                for t in tasks
                if t.due_time and t.status in TASK_ACTIVE_STATUSES and t.due_time < now
            ],
            "upcoming": [
                t
                for t in tasks
                if t.due_time and t.status in TASK_ACTIVE_STATUSES and t.due_time >= now
            ],
        }
        # Dependencies: blocked tasks that name another task in blocker_reason or supporting links
        dependencies = []
        for t in tasks:
            for other in tasks:
                if other.task_id != t.task_id and other.task_id in (t.blocker_reason or ""):
                    dependencies.append(
                        {
                            "task_id": t.task_id,
                            "depends_on": other.task_id,
                            "reason": t.blocker_reason,
                        }
                    )
            if t.status == "BLOCKED" and t.blocker_reason:
                dependencies.append(
                    {
                        "task_id": t.task_id,
                        "depends_on": "",
                        "reason": t.blocker_reason,
                    }
                )

        resource_constraints = []
        for t in tasks:
            if t.status in COMMITTING:
                for pid in t.associated_platform_ids or []:
                    plat = self.store.get_platform(pid)
                    if plat and plat.held_in_reserve:
                        resource_constraints.append(
                            {
                                "task_id": t.task_id,
                                "platform_id": pid,
                                "constraint": "platform_held_in_reserve",
                            }
                        )
            for pid in t.associated_platform_ids or []:
                plat = self.store.get_platform(pid)
                if not plat:
                    resource_constraints.append(
                        {
                            "task_id": t.task_id,
                            "platform_id": pid,
                            "constraint": "missing_platform_org",
                        }
                    )

        return {
            "mission": mission.to_dict(),
            "objectives": list(mission.objectives),
            "required_milestones": milestones,
            "milestone_completion": {
                "completed": len(completed_ms),
                "total": len(milestones),
                "numerator": len(completed_ms),
                "denominator": len(milestones),
                "units": "milestones",
                "reporting_period": "mission_scope",
                "inclusion": "required_milestones with status=completed",
            },
            "task_counts": {k: len(v) for k, v in by_status.items()},
            "tasks": [t.to_dict() for t in tasks],
            "dependencies": dependencies,
            "resource_constraints": resource_constraints,
            "upcoming_deadlines": [t.to_dict() for t in by_status["upcoming"][:10]],
            "note": "Progress is criteria-based; aircraft activity alone does not complete the mission.",
            "generated_at": utc_now(),
        }
