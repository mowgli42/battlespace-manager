"""Mission management business rules and fleet overview assembly."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.mission.auth import ActorContext, can_admin_override
from app.mission.models import (
    TASK_ACTIVE_STATUSES,
    Alert,
    Assignment,
    AuditEvent,
    Mission,
    Operator,
    PlatformOrg,
    Task,
    Team,
    map_technical_readiness,
)
from app.mission.analytics import MissionAnalytics
from app.mission.resource_views import ResourceViews
from app.mission.store import MissionStore, new_id, utc_now

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_SEED = _REPO_ROOT / "fixtures" / "mission-management-seed-v1.json"
_STALE_SECONDS_DEFAULT = 120

_service: MissionService | None = None


class MissionError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class MissionService:
    def __init__(self, store: MissionStore, *, stale_seconds: int | None = None) -> None:
        self.store = store
        self.stale_seconds = stale_seconds or int(os.getenv("MISSION_STALE_SECONDS", _STALE_SECONDS_DEFAULT))
        self.resources = ResourceViews(store, stale_seconds=self.stale_seconds)
        self.analytics = MissionAnalytics(store)

    def ensure_seeded(self, seed_path: Path | None = None) -> bool:
        path = seed_path or Path(os.getenv("MISSION_SEED_PATH", str(_DEFAULT_SEED)))
        seed_version = "1.0"
        if path.is_file():
            try:
                seed_version = str(json.loads(path.read_text(encoding="utf-8")).get("version") or "1.0")
            except json.JSONDecodeError:
                seed_version = "1.0"
        # Re-seed when fixture version changes (Phase 2 bumped content under same major when needed)
        if self.store.get_meta("seeded") == "1" and self.store.get_meta("seed_version") == seed_version:
            return False
        if not path.is_file():
            self.store.set_meta("seeded", "1")
            self.store.set_meta("seed_version", seed_version)
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        for raw in data.get("teams") or []:
            self.store.upsert_team(Team(**raw))
        for raw in data.get("operators") or []:
            self.store.upsert_operator(Operator(**raw))
        for raw in data.get("missions") or []:
            self.store.upsert_mission(Mission(**raw))
        for raw in data.get("platforms") or []:
            self.store.upsert_platform(PlatformOrg(**raw))
        for raw in data.get("tasks") or []:
            self.store.upsert_task(Task(**raw))
        for raw in data.get("assignments") or []:
            self.store.upsert_assignment(Assignment(**raw))
        for raw in data.get("alerts") or []:
            self.store.upsert_alert(Alert(**raw))
        self._rebuild_operator_platform_lists()
        # Phase 3 utilization history (idempotent by sample_id)
        self.analytics.seed_samples(list(data.get("utilization_samples") or []))
        self.store.set_meta("seeded", "1")
        self.store.set_meta("seed_version", str(data.get("version") or seed_version))
        return True

    def _audit(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        previous_value: Any,
        new_value: Any,
        reason: str = "",
        source: str = "mission-api",
        event_timestamp: str | None = None,
    ) -> AuditEvent:
        now = utc_now()
        event = AuditEvent(
            event_id=new_id("EVT"),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            event_timestamp=event_timestamp or now,
            received_timestamp=now,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            source=source,
        )
        self.store.append_audit(event)
        return event

    def _rebuild_operator_platform_lists(self) -> None:
        ops = {o.operator_id: o for o in self.store.list_operators()}
        for op in ops.values():
            op.primary_platform_ids = []
            op.support_platform_ids = []
        for plat in self.store.list_platforms():
            if plat.primary_operator_id and plat.primary_operator_id in ops:
                ops[plat.primary_operator_id].primary_platform_ids.append(plat.platform_id)
            for sid in plat.support_operator_ids:
                if sid in ops and sid != plat.primary_operator_id:
                    ops[sid].support_platform_ids.append(plat.platform_id)
        for op in ops.values():
            self.store.upsert_operator(op)

    def set_platform_primary(
        self,
        platform_id: str,
        *,
        team_id: str,
        operator_id: str = "",
        actor: ActorContext,
        reason: str = "",
    ) -> PlatformOrg:
        plat = self.store.get_platform(platform_id)
        if plat is None:
            raise MissionError(f"Unknown platform {platform_id}", 404)
        if not team_id:
            raise MissionError("primary_team_id is required")
        if self.store.get_team(team_id) is None:
            raise MissionError(f"Unknown team {team_id}", 404)
        if operator_id and self.store.get_operator(operator_id) is None:
            raise MissionError(f"Unknown operator {operator_id}", 404)
        previous = plat.to_dict()
        # Support must not steal primary: remove operator from support if becoming primary
        if operator_id and operator_id in plat.support_operator_ids:
            plat.support_operator_ids = [s for s in plat.support_operator_ids if s != operator_id]
        plat.primary_team_id = team_id
        plat.primary_operator_id = operator_id
        self.store.upsert_platform(plat)
        self._rebuild_operator_platform_lists()
        self._audit(
            event_type="platform.primary_updated",
            entity_type="platform",
            entity_id=platform_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=plat.to_dict(),
            reason=reason,
        )
        return plat

    def add_platform_support(
        self,
        platform_id: str,
        operator_id: str,
        *,
        actor: ActorContext,
        reason: str = "",
    ) -> PlatformOrg:
        plat = self.store.get_platform(platform_id)
        if plat is None:
            raise MissionError(f"Unknown platform {platform_id}", 404)
        if self.store.get_operator(operator_id) is None:
            raise MissionError(f"Unknown operator {operator_id}", 404)
        if operator_id == plat.primary_operator_id:
            raise MissionError("Primary operator cannot also be listed only as support; already primary")
        previous = plat.to_dict()
        if operator_id not in plat.support_operator_ids:
            plat.support_operator_ids = list(plat.support_operator_ids) + [operator_id]
            self.store.upsert_platform(plat)
            self._rebuild_operator_platform_lists()
            self._audit(
                event_type="platform.support_added",
                entity_type="platform",
                entity_id=platform_id,
                actor_id=actor.actor_id,
                previous_value=previous,
                new_value=plat.to_dict(),
                reason=reason,
            )
        return plat

    def create_task(self, payload: dict[str, Any], *, actor: ActorContext) -> Task:
        task_id = str(payload.get("task_id") or new_id("TSK-M"))
        if self.store.get_task(task_id):
            raise MissionError(f"Task {task_id} already exists", 409)
        mission_id = str(payload.get("mission_id") or "")
        if not mission_id or self.store.get_mission(mission_id) is None:
            raise MissionError("Valid mission_id is required")
        owner = str(payload.get("accountable_owner_id") or "")
        status = str(payload.get("status") or "CREATED")
        if status in TASK_ACTIVE_STATUSES and status not in ("CREATED", "REVIEWED") and not owner:
            raise MissionError("Active tasks beyond REVIEWED require accountable_owner_id")
        criteria = str(payload.get("completion_criteria") or "").strip()
        if not criteria:
            raise MissionError("completion_criteria is required")
        task = Task(
            task_id=task_id,
            mission_id=mission_id,
            description=str(payload.get("description") or ""),
            priority=int(payload.get("priority") or 3),
            required_capabilities=list(payload.get("required_capabilities") or []),
            planned_start=str(payload.get("planned_start") or ""),
            due_time=str(payload.get("due_time") or ""),
            accountable_owner_id=owner,
            supporting_operator_ids=[
                s for s in list(payload.get("supporting_operator_ids") or []) if s != owner
            ],
            supporting_team_ids=list(payload.get("supporting_team_ids") or []),
            associated_platform_ids=list(payload.get("associated_platform_ids") or []),
            status=status,
            completion_criteria=criteria,
            requires_evidence=bool(payload.get("requires_evidence")),
            completion_evidence=str(payload.get("completion_evidence") or ""),
            blocker_reason=str(payload.get("blocker_reason") or ""),
            external_task_id=str(payload.get("external_task_id") or ""),
        )
        if task.status == "BLOCKED" and not task.blocker_reason:
            raise MissionError("blocker_reason is required when status is BLOCKED")
        self.store.upsert_task(task)
        self._audit(
            event_type="task.created",
            entity_type="task",
            entity_id=task.task_id,
            actor_id=actor.actor_id,
            previous_value=None,
            new_value=task.to_dict(),
            reason=str(payload.get("reason") or ""),
        )
        return task

    def reassign_task(
        self,
        task_id: str,
        *,
        new_owner_id: str,
        actor: ActorContext,
        reason: str = "",
        admin_override: bool = False,
        request_id: str = "",
        platform_id: str = "",
        team_id: str = "",
    ) -> dict[str, Any]:
        if request_id:
            existing = self.store.find_assignment_by_request_id(request_id)
            if existing:
                task = self.store.get_task(task_id)
                return {"task": task.to_dict() if task else None, "assignment": existing.to_dict(), "idempotent": True}

        task = self.store.get_task(task_id)
        if task is None:
            raise MissionError(f"Unknown task {task_id}", 404)
        if self.store.get_operator(new_owner_id) is None:
            raise MissionError(f"Unknown operator {new_owner_id}", 404)
        if task.status not in TASK_ACTIVE_STATUSES:
            raise MissionError(f"Cannot reassign task in status {task.status}")

        previous = task.to_dict()
        now = utc_now()

        # Supersede current active primary assignment for this task
        for asg in self.store.list_assignments(task_id):
            if asg.responsibility_type == "primary" and asg.assignment_status in ("active", "pending_ack"):
                asg.assignment_status = "superseded"
                asg.effective_end = now
                self.store.upsert_assignment(asg)

        use_override = bool(admin_override) and can_admin_override(actor)
        if use_override:
            task.accountable_owner_id = new_owner_id
            task.pending_owner_id = ""
            if task.status in ("CREATED", "REVIEWED"):
                task.status = "ASSIGNED"
            ack = "acknowledged"
            asg_status = "active"
        else:
            task.pending_owner_id = new_owner_id
            # Ownership not transferred yet
            ack = "pending"
            asg_status = "pending_ack"
            if task.status in ("CREATED", "REVIEWED"):
                task.status = "ASSIGNED"

        assignment = Assignment(
            assignment_id=new_id("ASG"),
            task_id=task_id,
            platform_id=platform_id or (task.associated_platform_ids[0] if task.associated_platform_ids else ""),
            operator_id=new_owner_id,
            team_id=team_id,
            responsibility_type="primary",
            effective_start=now,
            acknowledgement_status=ack,
            assignment_status=asg_status,
            assigned_by=actor.actor_id,
            assignment_reason=reason,
            request_id=request_id,
        )
        self.store.upsert_task(task)
        self.store.upsert_assignment(assignment)
        self._audit(
            event_type="task.reassign_override" if use_override else "task.reassign_pending",
            entity_type="task",
            entity_id=task_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value={"task": task.to_dict(), "assignment": assignment.to_dict()},
            reason=reason,
        )
        return {"task": task.to_dict(), "assignment": assignment.to_dict(), "idempotent": False}

    def acknowledge_task(
        self,
        task_id: str,
        *,
        actor: ActorContext,
        accept: bool = True,
        reason: str = "",
    ) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise MissionError(f"Unknown task {task_id}", 404)
        previous = task.to_dict()
        pending = task.pending_owner_id or task.accountable_owner_id
        if actor.role not in ("admin", "mission_supervisor") and actor.actor_id != pending:
            raise MissionError("Only the pending/accountable owner (or supervisor override) may acknowledge", 403)

        active_pending = [
            a
            for a in self.store.list_assignments(task_id)
            if a.assignment_status == "pending_ack" and a.responsibility_type == "primary"
        ]
        now = utc_now()
        if not accept:
            for asg in active_pending:
                asg.acknowledgement_status = "rejected"
                asg.assignment_status = "cancelled"
                asg.effective_end = now
                self.store.upsert_assignment(asg)
            task.pending_owner_id = ""
            self.store.upsert_task(task)
            self._audit(
                event_type="task.ack_rejected",
                entity_type="task",
                entity_id=task_id,
                actor_id=actor.actor_id,
                previous_value=previous,
                new_value=task.to_dict(),
                reason=reason,
            )
            return task

        # Accept → finalize ownership transfer
        if task.pending_owner_id:
            task.accountable_owner_id = task.pending_owner_id
            task.pending_owner_id = ""
        if not task.accountable_owner_id:
            raise MissionError("No accountable owner to acknowledge")
        if task.status in ("ASSIGNED", "CREATED", "REVIEWED"):
            task.status = "ACCEPTED"
        for asg in active_pending:
            asg.acknowledgement_status = "acknowledged"
            asg.assignment_status = "active"
            asg.operator_id = task.accountable_owner_id
            self.store.upsert_assignment(asg)
        # If no pending assignment row (initial assign already active owner)
        if not active_pending and task.accountable_owner_id:
            for asg in self.store.list_assignments(task_id):
                if asg.responsibility_type == "primary" and asg.assignment_status == "active":
                    asg.acknowledgement_status = "acknowledged"
                    self.store.upsert_assignment(asg)
        self.store.upsert_task(task)
        self._audit(
            event_type="task.acknowledged",
            entity_type="task",
            entity_id=task_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=task.to_dict(),
            reason=reason,
        )
        return task

    def complete_task(
        self,
        task_id: str,
        *,
        actor: ActorContext,
        evidence: str = "",
        reason: str = "",
    ) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise MissionError(f"Unknown task {task_id}", 404)
        if actor.role not in ("admin", "mission_supervisor") and actor.actor_id != task.accountable_owner_id:
            raise MissionError("Only accountable owner may complete task", 403)
        if task.requires_evidence and not (evidence or task.completion_evidence).strip():
            raise MissionError("completion evidence is required for this task")
        previous = task.to_dict()
        if evidence:
            task.completion_evidence = evidence
        task.status = "COMPLETED"
        task.blocker_reason = ""
        now = utc_now()
        for asg in self.store.list_assignments(task_id):
            if asg.assignment_status == "active":
                asg.effective_end = now
                self.store.upsert_assignment(asg)
        self.store.upsert_task(task)
        self._audit(
            event_type="task.completed",
            entity_type="task",
            entity_id=task_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=task.to_dict(),
            reason=reason,
        )
        return task

    def acknowledge_alert(self, alert_id: str, *, actor: ActorContext) -> Alert:
        alert = self.store.get_alert(alert_id)
        if alert is None:
            raise MissionError(f"Unknown alert {alert_id}", 404)
        previous = alert.to_dict()
        alert.acknowledgement_status = "acknowledged"
        # Acknowledgement must not auto-resolve
        self.store.upsert_alert(alert)
        self._audit(
            event_type="alert.acknowledged",
            entity_type="alert",
            entity_id=alert_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=alert.to_dict(),
        )
        return alert

    def resolve_alert(self, alert_id: str, *, actor: ActorContext, reason: str = "") -> Alert:
        alert = self.store.get_alert(alert_id)
        if alert is None:
            raise MissionError(f"Unknown alert {alert_id}", 404)
        previous = alert.to_dict()
        alert.resolution_status = "resolved"
        self.store.upsert_alert(alert)
        self._audit(
            event_type="alert.resolved",
            entity_type="alert",
            entity_id=alert_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=alert.to_dict(),
            reason=reason,
        )
        return alert

    def _parse_last_update(self, raw: Any) -> float | None:
        if raw is None or raw == "":
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        try:
            # Accept Zulu ISO
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            from datetime import datetime

            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None

    def _operational_availability(
        self,
        tech: str,
        plat: PlatformOrg,
        *,
        active_task_count: int,
    ) -> dict[str, Any]:
        """Can the platform accept an additional commitment? Separate from technical readiness."""
        if tech in ("Unavailable", "Unknown"):
            return {
                "state": "unavailable",
                "reason": f"technical readiness is {tech}",
                "held_in_reserve": plat.held_in_reserve,
                "committed": False,
            }
        # Intentional reserve is not "inefficient utilization" and is not treated as fully committed.
        if plat.held_in_reserve and active_task_count == 0:
            return {
                "state": "available_reserved",
                "reason": "held in reserve",
                "held_in_reserve": True,
                "committed": False,
            }
        commitments = list(plat.active_commitments or [])
        committed = active_task_count > 0 or len(commitments) > 0
        if committed:
            return {
                "state": "unavailable_for_additional",
                "reason": "active commitment or task",
                "held_in_reserve": False,
                "committed": True,
            }
        return {
            "state": "available",
            "reason": "operationally available",
            "held_in_reserve": False,
            "committed": False,
        }

    def build_fleet_overview(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        picture = picture or {}
        platforms_pic = {p.get("platform_id"): p for p in (picture.get("platforms") or []) if p.get("platform_id")}
        now_ts = __import__("time").time()
        rows: list[dict[str, Any]] = []
        counts = {
            "total": 0,
            "operational": 0,
            "degraded": 0,
            "unavailable": 0,
            "unknown": 0,
            "committed": 0,
            "uncommitted_operational": 0,
            "upcoming_availability": 0,
            "stale_telemetry": 0,
        }
        org_platforms = self.store.list_platforms()
        # Include picture-only platforms as Unknown ownership until seeded
        seen = {p.platform_id for p in org_platforms}
        for pid, prow in platforms_pic.items():
            if pid not in seen:
                org_platforms.append(
                    PlatformOrg(
                        platform_id=pid,
                        platform_type=str(prow.get("platform_type") or ""),
                    )
                )

        tasks = self.store.list_tasks()
        for plat in org_platforms:
            pic = platforms_pic.get(plat.platform_id) or {}
            tech = map_technical_readiness(pic.get("readiness") if pic else None)
            if not pic:
                tech = "Unknown"
            last_raw = pic.get("last_update_time") or pic.get("updated_at") or picture.get("received_at")
            last_ts = self._parse_last_update(last_raw)
            stale = False
            if pic and last_ts is not None:
                stale = (now_ts - last_ts) > self.stale_seconds
            elif pic and last_ts is None and picture.get("harness_mode"):
                # Harness pictures often omit last_update_time — treat as fresh unless marked
                stale = bool(pic.get("stale"))
            elif not pic:
                stale = True
                tech = "Unknown"

            # DEFERRED / CREATED / REVIEWED do not consume operational availability the way
            # ASSIGNED+ executing work does; reserve-hold tasks are typically DEFERRED.
            committing_statuses = frozenset({"ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"})
            active_tasks = [
                t
                for t in tasks
                if plat.platform_id in (t.associated_platform_ids or []) and t.status in committing_statuses
            ]
            # Also count COP active_task_id as commitment signal
            cop_active = 1 if pic.get("active_task_id") else 0
            # Seeded active_commitments on reserve platforms are informational only when held_in_reserve
            commitment_signal = len(active_tasks) + cop_active
            if plat.held_in_reserve and commitment_signal == 0:
                # Ignore org overlay commitment labels used only to document the reserve hold
                pass
            avail = self._operational_availability(
                tech, plat, active_task_count=commitment_signal
            )
            exceptions = []
            if stale:
                exceptions.append({"severity": "Attention", "code": "stale_telemetry", "message": "Telemetry stale or missing"})
            if tech == "Unknown":
                exceptions.append({"severity": "Informational", "code": "unknown_readiness", "message": "Technical readiness unknown"})
            if tech == "Degraded":
                exceptions.append({"severity": "Attention", "code": "degraded", "message": "Platform degraded"})
            if tech == "Unavailable":
                exceptions.append({"severity": "Critical", "code": "unavailable", "message": "Platform unavailable"})

            team = self.store.get_team(plat.primary_team_id) if plat.primary_team_id else None
            owner = self.store.get_operator(plat.primary_operator_id) if plat.primary_operator_id else None
            row = {
                "platform_id": plat.platform_id,
                "callsign": pic.get("callsign") or "",
                "platform_type": plat.platform_type or pic.get("platform_type") or "",
                "technical_readiness": tech,
                "operational_availability": avail,
                "current_mission_id": next((t.mission_id for t in active_tasks), ""),
                "current_commitment": pic.get("active_task_id") or (active_tasks[0].task_id if active_tasks else ""),
                "primary_team_id": plat.primary_team_id,
                "primary_team_name": team.name if team else "",
                "primary_operator_id": plat.primary_operator_id,
                "primary_operator_name": owner.name if owner else "",
                "support_operator_ids": list(plat.support_operator_ids),
                "active_task_count": len(active_tasks) + cop_active,
                "last_update_time": last_raw or "",
                "stale": stale,
                "held_in_reserve": plat.held_in_reserve,
                "exceptions": exceptions,
            }
            rows.append(row)
            counts["total"] += 1
            key = tech.lower()
            if key in counts:
                counts[key] += 1
            if avail.get("committed"):
                counts["committed"] += 1
            if tech == "Operational" and not avail.get("committed"):
                counts["uncommitted_operational"] += 1
            if any(c.get("estimated_available_at") for c in (plat.active_commitments or [])):
                counts["upcoming_availability"] += 1
            if stale:
                counts["stale_telemetry"] += 1

        return {
            "counts": counts,
            "platforms": rows,
            "stale_threshold_seconds": self.stale_seconds,
            "generated_at": utc_now(),
        }

    def build_operator_workload(self, operator_id: str) -> dict[str, Any]:
        op = self.store.get_operator(operator_id)
        if op is None:
            raise MissionError(f"Unknown operator {operator_id}", 404)
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
                or (a.entity_type == "platform" and a.entity_id in (op.primary_platform_ids + op.support_platform_ids))
            )
        ]
        conflict = len(op.primary_platform_ids) >= 1 and len(op.support_platform_ids) >= 1 and len(active) >= 2
        factors = {
            "primary_aircraft": list(op.primary_platform_ids),
            "supported_aircraft": list(op.support_platform_ids),
            "active_tasks": len(active),
            "pending_acknowledgements": len(pending_ack),
            "pending_decisions": len(pending_ack),
            "time_sensitive_tasks": len(time_sensitive),
            "unresolved_exceptions": len(alerts),
            "availability_state": op.availability_state,
        }
        return {
            "operator": op.to_dict(),
            "factors": factors,
            "conflict_indicator": conflict,
            "workload_score": None,
            "workload_score_label": "not_computed",
            "note": "Phase 1 exposes contributing factors only; no validated capacity score.",
            "tasks": [t.to_dict() for t in tasks],
            "alerts": [a.to_dict() for a in alerts],
        }

    def build_mission_progress(self, mission_id: str) -> dict[str, Any]:
        # Phase 2: enriched criteria-based progress with dependencies and constraints
        return self.resources.build_mission_progress_enriched(mission_id)

    def build_team_console(self, team_id: str, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resources.build_team_console(team_id, picture)

    def build_teams_overview(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resources.build_teams_overview(picture)

    def build_operators_workload_overview(self) -> dict[str, Any]:
        return self.resources.build_operators_workload_overview()

    def build_resource_conflicts(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resources.build_resource_conflicts(picture)

    def build_platform_commitments(
        self, platform_id: str, picture: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.resources.build_platform_commitments(platform_id, picture)

    def upsert_platform_commitment(
        self,
        platform_id: str,
        payload: dict[str, Any],
        *,
        actor: ActorContext,
    ) -> dict[str, Any]:
        previous = None
        plat = self.store.get_platform(platform_id)
        if plat:
            previous = list(plat.active_commitments or [])
        entry = self.resources.upsert_commitment(platform_id, payload, actor_id=actor.actor_id)
        self._audit(
            event_type="platform.commitment_upserted",
            entity_type="platform",
            entity_id=platform_id,
            actor_id=actor.actor_id,
            previous_value=previous,
            new_value=entry,
            reason=str(payload.get("reason") or ""),
        )
        return entry

    # --- Phase 3 analytics ---

    def record_utilization_sample(
        self, picture: dict[str, Any] | None = None, *, actor: ActorContext
    ) -> dict[str, Any]:
        result = self.analytics.record_fleet_sample(picture, actor_id=actor.actor_id)
        self._audit(
            event_type="analytics.sample_recorded",
            entity_type="fleet",
            entity_id="fleet",
            actor_id=actor.actor_id,
            previous_value=None,
            new_value={"sample_count": result.get("sample_count"), "sampled_at": result.get("sampled_at")},
        )
        return result

    def build_utilization_report(
        self, *, start: str | None = None, end: str | None = None, platform_id: str | None = None
    ) -> dict[str, Any]:
        return self.analytics.build_utilization_report(start=start, end=end, platform_id=platform_id)

    def build_task_metrics(
        self, *, start: str | None = None, end: str | None = None
    ) -> dict[str, Any]:
        return self.analytics.build_task_metrics(start=start, end=end)

    def build_milestone_analytics(self, mission_id: str | None = None) -> dict[str, Any]:
        return self.analytics.build_milestone_analytics(mission_id)

    def build_health_overview(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.analytics.build_health_overview(picture)

    def build_post_flight_review(self, mission_id: str) -> dict[str, Any]:
        return self.analytics.build_post_flight_review(mission_id)

    def build_bottleneck_analysis(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.analytics.build_bottleneck_analysis(picture)

    def platform_detail(self, platform_id: str, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        plat = self.store.get_platform(platform_id)
        if plat is None:
            raise MissionError(f"Unknown platform {platform_id}", 404)
        fleet = self.build_fleet_overview(picture)
        row = next((r for r in fleet["platforms"] if r["platform_id"] == platform_id), None)
        tasks = [
            t.to_dict()
            for t in self.store.list_tasks()
            if platform_id in (t.associated_platform_ids or [])
        ]
        history = [a.to_dict() for a in self.store.list_assignments() if a.platform_id == platform_id]
        audit = [e.to_dict() for e in self.store.list_audit("platform", platform_id)]
        return {
            "organization": plat.to_dict(),
            "fleet_row": row,
            "tasks": tasks,
            "assignment_history": history,
            "audit": audit,
        }


def get_mission_service(store_path: str | None = None) -> MissionService:
    global _service
    if _service is not None and store_path is None:
        return _service
    path = store_path or os.getenv(
        "MISSION_STORE_PATH",
        str(_REPO_ROOT / "services" / "battlespace-display" / "data" / "mission.db"),
    )
    store = MissionStore(path)
    svc = MissionService(store)
    svc.ensure_seeded()
    if store_path is None:
        _service = svc
    return svc


def reset_mission_service_for_tests() -> None:
    global _service
    _service = None
