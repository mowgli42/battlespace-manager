"""Logical domain models for mission management (Phase 1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TASK_ACTIVE_STATUSES = frozenset(
    {"CREATED", "REVIEWED", "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED", "DEFERRED"}
)
TASK_TERMINAL_STATUSES = frozenset({"COMPLETED", "UNABLE_TO_COMPLETE", "CANCELLED"})
TASK_STATUSES = TASK_ACTIVE_STATUSES | TASK_TERMINAL_STATUSES

TECH_READINESS = frozenset({"Operational", "Degraded", "Unavailable", "Unknown"})
RESPONSIBILITY = frozenset({"primary", "support"})
ACK_STATUSES = frozenset({"not_required", "pending", "acknowledged", "rejected"})
ASSIGNMENT_STATUSES = frozenset({"proposed", "pending_ack", "active", "superseded", "cancelled"})
ALERT_SEVERITIES = frozenset({"Critical", "Attention", "Informational"})
ROLES = frozenset({"mission_supervisor", "team_supervisor", "operator", "analyst", "admin"})


def _list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return list(val)
    return list(val)


@dataclass
class Team:
    team_id: str
    name: str
    supervisor_id: str = ""
    membership: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Operator:
    operator_id: str
    name: str
    team_memberships: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    availability_state: str = "available"
    primary_platform_ids: list[str] = field(default_factory=list)
    support_platform_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Mission:
    mission_id: str
    name: str
    description: str = ""
    objectives: list[str] = field(default_factory=list)
    priority: int = 3
    planned_start: str = ""
    planned_end: str = ""
    status: str = "active"
    required_milestones: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformOrg:
    """Organizational overlay for a COP/OMS platform_id."""

    platform_id: str
    platform_type: str = ""
    capabilities: list[str] = field(default_factory=list)
    primary_team_id: str = ""
    primary_operator_id: str = ""
    support_operator_ids: list[str] = field(default_factory=list)
    held_in_reserve: bool = False
    active_commitments: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    task_id: str
    mission_id: str
    description: str
    priority: int = 3
    required_capabilities: list[str] = field(default_factory=list)
    planned_start: str = ""
    due_time: str = ""
    accountable_owner_id: str = ""
    supporting_operator_ids: list[str] = field(default_factory=list)
    supporting_team_ids: list[str] = field(default_factory=list)
    associated_platform_ids: list[str] = field(default_factory=list)
    status: str = "CREATED"
    completion_criteria: str = ""
    requires_evidence: bool = False
    completion_evidence: str = ""
    blocker_reason: str = ""
    pending_owner_id: str = ""
    external_task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Assignment:
    assignment_id: str
    task_id: str
    platform_id: str = ""
    operator_id: str = ""
    team_id: str = ""
    responsibility_type: str = "primary"
    effective_start: str = ""
    effective_end: str = ""
    acknowledgement_status: str = "pending"
    assignment_status: str = "pending_ack"
    assigned_by: str = ""
    assignment_reason: str = ""
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    event_timestamp: str
    received_timestamp: str
    previous_value: Any = None
    new_value: Any = None
    reason: str = ""
    source: str = "mission-api"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Alert:
    alert_id: str
    severity: str
    entity_type: str
    entity_id: str
    description: str
    required_action: str = ""
    acknowledgement_status: str = "pending"
    resolution_status: str = "open"
    created_at: str = ""
    consolidated_of: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def map_technical_readiness(raw: Any) -> str:
    """Map OMS/harness readiness tokens to Phase 1 technical readiness enum."""
    if raw is None or raw == "":
        return "Unknown"
    token = str(raw).strip().upper()
    if token in ("GREEN", "OPERATIONAL", "READY", "GO"):
        return "Operational"
    if token in ("YELLOW", "AMBER", "DEGRADED", "PARTIAL"):
        return "Degraded"
    if token in ("RED", "UNAVAILABLE", "DOWN", "NOGO", "BLACK"):
        return "Unavailable"
    if token in ("UNKNOWN", "STALE", "N/A", "NA"):
        return "Unknown"
    # Preserve already-normalized values
    if str(raw) in TECH_READINESS:
        return str(raw)
    return "Unknown"
