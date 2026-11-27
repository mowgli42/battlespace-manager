"""FastAPI routes for /api/mission/*."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.mission.auth import (
    ActorContext,
    parse_actor,
    require_reassign,
    require_roles,
    require_write,
)
from app.mission.service import MissionError, MissionService, get_mission_service

router = APIRouter(prefix="/api/mission", tags=["mission"])


class ReassignBody(BaseModel):
    new_owner_id: str
    reason: str = ""
    admin_override: bool = False
    request_id: str = ""
    platform_id: str = ""
    team_id: str = ""


class AckBody(BaseModel):
    accept: bool = True
    reason: str = ""


class CompleteBody(BaseModel):
    evidence: str = ""
    reason: str = ""


class SupportBody(BaseModel):
    operator_id: str
    reason: str = ""


class PrimaryBody(BaseModel):
    team_id: str
    operator_id: str = ""
    reason: str = ""


class TaskCreateBody(BaseModel):
    mission_id: str
    description: str
    completion_criteria: str
    task_id: str | None = None
    priority: int = 3
    required_capabilities: list[str] = Field(default_factory=list)
    planned_start: str = ""
    due_time: str = ""
    accountable_owner_id: str = ""
    supporting_operator_ids: list[str] = Field(default_factory=list)
    supporting_team_ids: list[str] = Field(default_factory=list)
    associated_platform_ids: list[str] = Field(default_factory=list)
    status: str = "CREATED"
    requires_evidence: bool = False
    external_task_id: str = ""
    reason: str = ""


def _svc() -> MissionService:
    return get_mission_service()


def _picture_provider() -> Callable[[], dict[str, Any]] | None:
    return getattr(router, "picture_provider", None)


def _current_picture() -> dict[str, Any]:
    provider = _picture_provider()
    if provider is None:
        return {}
    try:
        return provider() or {}
    except Exception:
        return {}


def _http(exc: MissionError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.get("/health")
def mission_health(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {
        "ok": True,
        "seeded": svc.store.get_meta("seeded") == "1",
        "teams": len(svc.store.list_teams()),
        "platforms": len(svc.store.list_platforms()),
        "tasks": len(svc.store.list_tasks()),
    }


@router.get("/fleet")
def fleet_overview(
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    # Anonymous read allowed for harness; authenticated any known role also OK
    if actor.actor_id and actor.role and actor.role not in (
        "mission_supervisor",
        "team_supervisor",
        "operator",
        "analyst",
        "admin",
    ):
        raise HTTPException(403, "Role not permitted")
    return svc.build_fleet_overview(_current_picture())


@router.get("/platforms/{platform_id}")
def platform_detail(
    platform_id: str,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    try:
        return svc.platform_detail(platform_id, _current_picture())
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/platforms/{platform_id}/primary")
def set_primary(
    platform_id: str,
    body: PrimaryBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_roles(actor, frozenset({"mission_supervisor", "admin", "team_supervisor"}))
    try:
        plat = svc.set_platform_primary(
            platform_id,
            team_id=body.team_id,
            operator_id=body.operator_id,
            actor=actor,
            reason=body.reason,
        )
        return plat.to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/platforms/{platform_id}/support")
def add_support(
    platform_id: str,
    body: SupportBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_roles(actor, frozenset({"mission_supervisor", "admin", "team_supervisor"}))
    try:
        plat = svc.add_platform_support(
            platform_id, body.operator_id, actor=actor, reason=body.reason
        )
        return plat.to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.get("/teams")
def list_teams(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {"teams": [t.to_dict() for t in svc.store.list_teams()]}


@router.get("/operators")
def list_operators(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {"operators": [o.to_dict() for o in svc.store.list_operators()]}


@router.get("/operators/{operator_id}/workload")
def operator_workload(
    operator_id: str,
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    try:
        return svc.build_operator_workload(operator_id)
    except MissionError as exc:
        raise _http(exc) from exc


@router.get("/missions")
def list_missions(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {"missions": [m.to_dict() for m in svc.store.list_missions()]}


@router.get("/missions/{mission_id}/progress")
def mission_progress(mission_id: str, svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    try:
        return svc.build_mission_progress(mission_id)
    except MissionError as exc:
        raise _http(exc) from exc


@router.get("/tasks")
def list_tasks(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {"tasks": [t.to_dict() for t in svc.store.list_tasks()]}


@router.post("/tasks")
def create_task(
    body: TaskCreateBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_write(actor)
    try:
        task = svc.create_task(body.model_dump(), actor=actor)
        return task.to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/tasks/{task_id}/reassign")
def reassign_task(
    task_id: str,
    body: ReassignBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_reassign(actor)
    try:
        return svc.reassign_task(
            task_id,
            new_owner_id=body.new_owner_id,
            actor=actor,
            reason=body.reason,
            admin_override=body.admin_override,
            request_id=body.request_id,
            platform_id=body.platform_id,
            team_id=body.team_id,
        )
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/tasks/{task_id}/acknowledge")
def acknowledge_task(
    task_id: str,
    body: AckBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_write(actor)
    try:
        task = svc.acknowledge_task(task_id, actor=actor, accept=body.accept, reason=body.reason)
        return task.to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    body: CompleteBody,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_write(actor)
    try:
        task = svc.complete_task(task_id, actor=actor, evidence=body.evidence, reason=body.reason)
        return task.to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.get("/alerts")
def list_alerts(svc: MissionService = Depends(_svc)) -> dict[str, Any]:
    return {"alerts": [a.to_dict() for a in svc.store.list_alerts()]}


@router.post("/alerts/{alert_id}/acknowledge")
def ack_alert(
    alert_id: str,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_write(actor)
    try:
        return svc.acknowledge_alert(alert_id, actor=actor).to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_roles(actor, frozenset({"mission_supervisor", "admin", "team_supervisor"}))
    try:
        return svc.resolve_alert(alert_id, actor=actor).to_dict()
    except MissionError as exc:
        raise _http(exc) from exc


@router.get("/audit")
def list_audit(
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: ActorContext = Depends(parse_actor),
    svc: MissionService = Depends(_svc),
) -> dict[str, Any]:
    require_roles(actor, frozenset({"mission_supervisor", "admin", "analyst", "team_supervisor"}))
    events = svc.store.list_audit(entity_type, entity_id)
    return {"events": [e.to_dict() for e in events]}
