"""Phase 3 performance intelligence: utilization, health, post-flight, bottlenecks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.mission.models import TASK_ACTIVE_STATUSES, TASK_TERMINAL_STATUSES, map_technical_readiness
from app.mission.store import MissionStore, new_id, utc_now

SAMPLE_MINUTES = 15  # each utilization sample represents this many minutes


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    text = ts.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _minutes_between(start: str, end: str) -> float | None:
    a = _parse_iso(start)
    b = _parse_iso(end)
    if not a or not b:
        return None
    return (b - a).total_seconds() / 60.0


class MissionAnalytics:
    def __init__(self, store: MissionStore, *, sample_minutes: int = SAMPLE_MINUTES) -> None:
        self.store = store
        self.sample_minutes = sample_minutes

    def seed_samples(self, samples: list[dict[str, Any]]) -> int:
        existing_ids = {s.get("sample_id") for s in self.store.list_utilization_samples()}
        n = 0
        for raw in samples:
            sid = raw.get("sample_id") or new_id("US")
            if sid in existing_ids:
                continue
            sample = {
                "sample_id": sid,
                "sampled_at": str(raw.get("sampled_at") or utc_now()),
                "platform_id": str(raw["platform_id"]),
                "technical_readiness": str(raw.get("technical_readiness") or "Unknown"),
                "held_in_reserve": bool(raw.get("held_in_reserve")),
                "committed": bool(raw.get("committed")),
                "scheduled_commitment": bool(raw.get("scheduled_commitment")),
                "mission_assigned": bool(raw.get("mission_assigned", raw.get("committed"))),
                "stale": bool(raw.get("stale")),
                "source": str(raw.get("source") or "seed"),
                "minutes_represented": int(raw.get("minutes_represented") or self.sample_minutes),
            }
            self.store.append_utilization_sample(sample)
            n += 1
        return n

    def record_fleet_sample(self, picture: dict[str, Any] | None = None, *, actor_id: str = "system") -> dict[str, Any]:
        """Snapshot current fleet utilization from org overlay + picture (no invented readiness)."""
        from app.mission.resource_views import ResourceViews

        picture = picture or {}
        views = ResourceViews(self.store)
        sampled_at = utc_now()
        recorded = []
        for plat in self.store.list_platforms():
            detail = views.build_platform_commitments(plat.platform_id, picture)
            tech = detail["technical_readiness"]
            avail = detail["operational_availability"]
            committed = bool(avail.get("committed") or avail.get("state") == "unavailable_for_additional")
            scheduled = bool(detail.get("scheduled_commitments"))
            sample = {
                "sample_id": new_id("US"),
                "sampled_at": sampled_at,
                "platform_id": plat.platform_id,
                "technical_readiness": tech,
                "held_in_reserve": bool(plat.held_in_reserve),
                "committed": committed,
                "scheduled_commitment": scheduled,
                "mission_assigned": committed or bool(detail.get("committing_tasks")),
                "stale": bool(detail.get("stale")),
                "source": "live_sample",
                "actor_id": actor_id,
                "minutes_represented": self.sample_minutes,
            }
            self.store.append_utilization_sample(sample)
            recorded.append(sample)
        return {
            "sampled_at": sampled_at,
            "sample_count": len(recorded),
            "samples": recorded,
            "note": "Each sample represents a fixed interval; readiness is never fabricated.",
        }

    def _filter_samples(
        self, *, platform_id: str | None, start: str | None, end: str | None
    ) -> list[dict[str, Any]]:
        return self.store.list_utilization_samples(platform_id=platform_id, start=start, end=end)

    def build_utilization_report(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        platform_id: str | None = None,
    ) -> dict[str, Any]:
        samples = self._filter_samples(platform_id=platform_id, start=start, end=end)
        by_platform: dict[str, dict[str, Any]] = {}
        totals = {
            "mission_assigned_minutes": 0.0,
            "operationally_available_minutes": 0.0,
            "uncommitted_operational_minutes": 0.0,
            "intentional_reserve_minutes": 0.0,
            "stale_or_unknown_minutes": 0.0,
            "sample_count": len(samples),
        }

        for s in samples:
            mins = float(s.get("minutes_represented") or self.sample_minutes)
            pid = s["platform_id"]
            row = by_platform.setdefault(
                pid,
                {
                    "platform_id": pid,
                    "mission_assigned_minutes": 0.0,
                    "operationally_available_minutes": 0.0,
                    "uncommitted_operational_minutes": 0.0,
                    "intentional_reserve_minutes": 0.0,
                    "stale_or_unknown_minutes": 0.0,
                    "sample_count": 0,
                },
            )
            row["sample_count"] += 1
            tech = s.get("technical_readiness") or "Unknown"
            stale = bool(s.get("stale"))
            if stale or tech in ("Unknown", "Unavailable"):
                row["stale_or_unknown_minutes"] += mins
                totals["stale_or_unknown_minutes"] += mins
                continue
            if tech != "Operational":
                # Degraded: count as available but mark separately via uncommitted rules
                pass
            if bool(s.get("held_in_reserve")):
                row["intentional_reserve_minutes"] += mins
                totals["intentional_reserve_minutes"] += mins
                # Reserved excluded from utilization denominator
                continue
            if tech in ("Operational", "Degraded"):
                row["operationally_available_minutes"] += mins
                totals["operationally_available_minutes"] += mins
                committed = bool(s.get("committed") or s.get("scheduled_commitment") or s.get("mission_assigned"))
                if committed:
                    row["mission_assigned_minutes"] += mins
                    totals["mission_assigned_minutes"] += mins
                else:
                    row["uncommitted_operational_minutes"] += mins
                    totals["uncommitted_operational_minutes"] += mins

        platforms = []
        for pid, row in sorted(by_platform.items()):
            denom = row["operationally_available_minutes"]
            numer = row["mission_assigned_minutes"]
            platforms.append(
                {
                    **row,
                    "utilization": {
                        "numerator": numer,
                        "denominator": denom,
                        "units": "sample-minutes",
                        "ratio": (numer / denom) if denom > 0 else None,
                        "reporting_period": {"start": start or "", "end": end or ""},
                        "inclusion": "Operational/Degraded samples excluding held_in_reserve and stale/unknown",
                        "exclusion": "held_in_reserve counted only as intentional_reserve_minutes; stale/unknown excluded",
                    },
                }
            )

        denom = totals["operationally_available_minutes"]
        numer = totals["mission_assigned_minutes"]
        return {
            "metric": "platform_utilization",
            "definition": {
                "numerator": "Mission-assigned platform sample-minutes while Operational/Degraded",
                "denominator": "Operationally available sample-minutes excluding held_in_reserve",
                "units": "sample-minutes / ratio",
                "reporting_period": {"start": start or "", "end": end or ""},
                "sample_minutes_per_point": self.sample_minutes,
            },
            "fleet": {
                **totals,
                "utilization_ratio": (numer / denom) if denom > 0 else None,
            },
            "uncommitted_operational_time": {
                "minutes": totals["uncommitted_operational_minutes"],
                "intentional_reserve_minutes": totals["intentional_reserve_minutes"],
                "note": "Reserved aircraft are not classified as inefficiently utilized.",
            },
            "platforms": platforms,
            "generated_at": utc_now(),
        }

    def build_task_metrics(self, *, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        tasks = self.store.list_tasks()
        eligible = []
        for t in tasks:
            if not t.due_time:
                continue
            if t.status in ("CANCELLED", "UNABLE_TO_COMPLETE"):
                continue
            if start and t.due_time < start:
                continue
            if end and t.due_time > end:
                continue
            eligible.append(t)

        completed_on_time = []
        completed_late = []
        delays = []
        for t in eligible:
            if t.status != "COMPLETED":
                continue
            # Prefer completion evidence audit timestamp
            completed_at = ""
            for ev in self.store.list_audit("task", t.task_id):
                if ev.event_type == "task.completed":
                    completed_at = ev.event_timestamp
            if not completed_at:
                completed_at = t.due_time  # unknown actual — treat as on-time only if due exists; mark estimated
            delay = _minutes_between(t.due_time, completed_at)
            # delay = actual - due; negative means early
            if delay is None:
                continue
            # If we fell back to due_time, delay is 0 but mark estimated
            estimated = completed_at == t.due_time and not any(
                e.event_type == "task.completed" for e in self.store.list_audit("task", t.task_id)
            )
            entry = {
                "task_id": t.task_id,
                "due_time": t.due_time,
                "completed_at": completed_at,
                "delay_minutes": delay,
                "completion_time_estimated": estimated,
            }
            delays.append(entry)
            if delay <= 0:
                completed_on_time.append(t)
            else:
                completed_late.append(t)

        due_in_period = [t for t in eligible if t.status == "COMPLETED" or t.status in TASK_ACTIVE_STATUSES]
        # Eligible tasks due in period that reached a completion decision or are still open past due
        denom_tasks = [t for t in eligible if t.status == "COMPLETED" or (t.status in TASK_ACTIVE_STATUSES and t.due_time < utc_now())]
        # Spec: eligible tasks due in reporting period — use all with due_time in window that are completed or overdue
        if not denom_tasks:
            denom_tasks = [t for t in eligible if t.status == "COMPLETED"]

        numer = len(completed_on_time)
        denom = len([t for t in eligible if t.status == "COMPLETED"])
        return {
            "metric": "task_on_time_completion",
            "definition": {
                "numerator": "Eligible tasks completed by due_time",
                "denominator": "Eligible tasks completed in reporting period",
                "units": "tasks / ratio",
                "reporting_period": {"start": start or "", "end": end or ""},
                "exclusion": "CANCELLED and UNABLE_TO_COMPLETE excluded; tasks without due_time excluded",
            },
            "on_time": {
                "numerator": numer,
                "denominator": denom,
                "ratio": (numer / denom) if denom > 0 else None,
            },
            "task_delay": {
                "definition": "actual_completion_time minus due_time (minutes; negative = early)",
                "items": delays,
                "average_delay_minutes": (
                    sum(d["delay_minutes"] for d in delays) / len(delays) if delays else None
                ),
            },
            "late_count": len(completed_late),
            "open_due_in_period": len(due_in_period),
            "generated_at": utc_now(),
        }

    def build_milestone_analytics(self, mission_id: str | None = None) -> dict[str, Any]:
        missions = self.store.list_missions()
        if mission_id:
            missions = [m for m in missions if m.mission_id == mission_id]
        rows = []
        total_completed = 0
        total_required = 0
        for m in missions:
            required = list(m.required_milestones or [])
            completed = [x for x in required if x.get("status") == "completed"]
            total_completed += len(completed)
            total_required += len(required)
            rows.append(
                {
                    "mission_id": m.mission_id,
                    "name": m.name,
                    "completed": len(completed),
                    "total": len(required),
                    "ratio": (len(completed) / len(required)) if required else None,
                    "milestones": required,
                }
            )
        return {
            "metric": "mission_milestone_completion",
            "definition": {
                "numerator": "Completed required milestones",
                "denominator": "Total required milestones in selected mission scope",
                "units": "milestones / ratio",
                "reporting_period": "mission_scope",
                "exclusion": "Non-required milestones excluded",
            },
            "aggregate": {
                "numerator": total_completed,
                "denominator": total_required,
                "ratio": (total_completed / total_required) if total_required else None,
            },
            "missions": rows,
            "note": "Aircraft activity alone does not complete milestones.",
            "generated_at": utc_now(),
        }

    def build_health_overview(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        picture = picture or {}
        pic_map = {p.get("platform_id"): p for p in (picture.get("platforms") or []) if p.get("platform_id")}
        rows = []
        for plat in self.store.list_platforms():
            pic = pic_map.get(plat.platform_id) or {}
            tech = map_technical_readiness(pic.get("readiness") if pic else None)
            if not pic:
                tech = "Unknown"
            subsystems = pic.get("subsystems") if isinstance(pic.get("subsystems"), dict) else {}
            degraded_sensors = [
                name
                for name, state in subsystems.items()
                if str(state).upper() not in ("ONLINE", "OK", "GREEN", "NOMINAL", "")
            ]
            rows.append(
                {
                    "platform_id": plat.platform_id,
                    "callsign": pic.get("callsign") or "",
                    "technical_readiness": tech,
                    "fuel_percent": pic.get("fuel_percent"),
                    "weapons_remaining": pic.get("weapons_remaining"),
                    "subsystems": subsystems,
                    "degraded_sensors": degraded_sensors,
                    "health_source": "picture" if pic else "missing",
                    "invented": False,
                }
            )
        return {
            "platforms": rows,
            "degraded_count": sum(1 for r in rows if r["technical_readiness"] == "Degraded" or r["degraded_sensors"]),
            "unknown_count": sum(1 for r in rows if r["technical_readiness"] == "Unknown"),
            "note": "Health values come only from COP picture fields; missing subsystems are empty, not invented.",
            "generated_at": utc_now(),
        }

    def build_post_flight_review(self, mission_id: str) -> dict[str, Any]:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            from app.mission.service import MissionError

            raise MissionError(f"Unknown mission {mission_id}", 404)
        tasks = [t for t in self.store.list_tasks() if t.mission_id == mission_id]
        completed = [t for t in tasks if t.status == "COMPLETED"]
        incomplete = [t for t in tasks if t.status not in TASK_TERMINAL_STATUSES]
        terminal_other = [t for t in tasks if t.status in TASK_TERMINAL_STATUSES and t.status != "COMPLETED"]

        reviews = []
        for t in tasks:
            audit = [e.to_dict() for e in self.store.list_audit("task", t.task_id)]
            completed_at = next(
                (e["event_timestamp"] for e in audit if e.get("event_type") == "task.completed"),
                "",
            )
            delay = _minutes_between(t.due_time, completed_at) if t.due_time and completed_at else None
            assignments = [a.to_dict() for a in self.store.list_assignments(t.task_id)]
            reviews.append(
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "status": t.status,
                    "accountable_owner_id": t.accountable_owner_id,
                    "platforms": list(t.associated_platform_ids),
                    "due_time": t.due_time,
                    "completed_at": completed_at,
                    "delay_minutes": delay,
                    "completion_evidence": t.completion_evidence,
                    "requires_evidence": t.requires_evidence,
                    "blocker_reason": t.blocker_reason,
                    "assignment_history_count": len(assignments),
                    "audit_event_count": len(audit),
                }
            )

        milestones = self.build_milestone_analytics(mission_id)
        return {
            "mission": mission.to_dict(),
            "summary": {
                "total_tasks": len(tasks),
                "completed": len(completed),
                "incomplete": len(incomplete),
                "terminal_other": len(terminal_other),
                "milestone_ratio": milestones["aggregate"]["ratio"],
            },
            "task_reviews": reviews,
            "milestones": milestones["missions"][0] if milestones["missions"] else None,
            "note": "Post-flight review uses durable task/assignment/audit records; telemetry alone does not mark success.",
            "generated_at": utc_now(),
        }

    def build_bottleneck_analysis(self, picture: dict[str, Any] | None = None) -> dict[str, Any]:
        from app.mission.resource_views import ResourceViews

        views = ResourceViews(self.store)
        conflicts = views.build_resource_conflicts(picture)
        util = self.build_utilization_report()
        health = self.build_health_overview(picture)
        ow = views.build_operators_workload_overview()

        bottlenecks: list[dict[str, Any]] = []

        # From conflicts
        for c in conflicts.get("conflicts") or []:
            severity_rank = {"Critical": 3, "Attention": 2, "Informational": 1}.get(c.get("severity"), 0)
            bottlenecks.append(
                {
                    "bottleneck_id": f"conflict-{c.get('conflict_id')}",
                    "kind": c.get("kind"),
                    "severity": c.get("severity"),
                    "rank_score": severity_rank * 10,
                    "entity_type": c.get("entity_type"),
                    "entity_id": c.get("entity_id"),
                    "description": c.get("description"),
                    "recommendation": c.get("recommendation"),
                    "source": "conflicts",
                    "auto_action": None,
                }
            )

        # Low utilization is NOT a bottleneck for reserved platforms
        for p in util.get("platforms") or []:
            ratio = (p.get("utilization") or {}).get("ratio")
            if (
                p["operationally_available_minutes"] > 0
                and ratio is not None
                and ratio < 0.25
                and p["intentional_reserve_minutes"] == 0
            ):
                bottlenecks.append(
                    {
                        "bottleneck_id": f"util-low-{p['platform_id']}",
                        "kind": "low_utilization",
                        "severity": "Informational",
                        "rank_score": 5,
                        "entity_type": "platform",
                        "entity_id": p["platform_id"],
                        "description": f"{p['platform_id']} utilization ratio {ratio:.2f} with uncommitted operational time",
                        "recommendation": "Review whether additional mission tasks are appropriate; reserved aircraft are excluded.",
                        "source": "utilization",
                        "auto_action": None,
                    }
                )
            if p["mission_assigned_minutes"] > 0 and ratio is not None and ratio >= 0.9:
                bottlenecks.append(
                    {
                        "bottleneck_id": f"util-high-{p['platform_id']}",
                        "kind": "high_commitment",
                        "severity": "Attention",
                        "rank_score": 15,
                        "entity_type": "platform",
                        "entity_id": p["platform_id"],
                        "description": f"{p['platform_id']} near-saturated utilization ({ratio:.2f})",
                        "recommendation": "Avoid additional commitments until estimated availability opens.",
                        "source": "utilization",
                        "auto_action": None,
                    }
                )

        for h in health.get("platforms") or []:
            if h["degraded_sensors"] or h["technical_readiness"] in ("Degraded", "Unavailable"):
                bottlenecks.append(
                    {
                        "bottleneck_id": f"health-{h['platform_id']}",
                        "kind": "health",
                        "severity": "Attention" if h["technical_readiness"] != "Unavailable" else "Critical",
                        "rank_score": 20 if h["technical_readiness"] == "Unavailable" else 12,
                        "entity_type": "platform",
                        "entity_id": h["platform_id"],
                        "description": f"{h['platform_id']} health {h['technical_readiness']} sensors={h['degraded_sensors']}",
                        "recommendation": "Confirm sensor/platform health before additional tasking.",
                        "source": "health",
                        "auto_action": None,
                    }
                )

        for op in ow.get("operators") or []:
            if op.get("conflict_indicator"):
                bottlenecks.append(
                    {
                        "bottleneck_id": f"op-{op['operator']['operator_id']}",
                        "kind": "operator_workload",
                        "severity": "Attention",
                        "rank_score": 14,
                        "entity_type": "operator",
                        "entity_id": op["operator"]["operator_id"],
                        "description": f"{op['operator']['name']} primary+support workload conflict",
                        "recommendation": "Rebalance via authorized human assignment only.",
                        "source": "workload",
                        "auto_action": None,
                    }
                )

        bottlenecks.sort(key=lambda b: (-b["rank_score"], b["bottleneck_id"]))
        return {
            "bottlenecks": bottlenecks,
            "total": len(bottlenecks),
            "note": "Bottlenecks are ranked indicators for supervisors; the system never auto-assigns from them.",
            "generated_at": utc_now(),
        }
