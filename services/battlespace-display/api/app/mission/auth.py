"""Backend role checks for mission-management APIs (Phase 1 header context)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException

from app.mission.models import ROLES

# Incomplete for production: header identity is forgeable without a gateway/SSO.
# Documented in MISSION-MANAGEMENT-ASSESSMENT.md and OPENSPEC.md.

ROLE_RANK = {
    "analyst": 1,
    "operator": 2,
    "team_supervisor": 3,
    "mission_supervisor": 4,
    "admin": 5,
}

WRITE_ROLES = frozenset({"operator", "team_supervisor", "mission_supervisor", "admin"})
SUPERVISOR_ROLES = frozenset({"team_supervisor", "mission_supervisor", "admin"})
REASSIGN_ROLES = frozenset({"mission_supervisor", "admin", "team_supervisor"})
ADMIN_OVERRIDE_ROLES = frozenset({"admin", "mission_supervisor"})


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str

    @property
    def is_authenticated(self) -> bool:
        return bool(self.actor_id) and self.role in ROLES


def parse_actor(
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_actor_role: str | None = Header(default=None, alias="X-Actor-Role"),
) -> ActorContext:
    actor_id = (x_actor_id or "").strip()
    role = (x_actor_role or "").strip().lower()
    if role and role not in ROLES:
        raise HTTPException(400, f"Unknown role: {role}")
    return ActorContext(actor_id=actor_id, role=role)


def require_authenticated(actor: ActorContext) -> ActorContext:
    if not actor.is_authenticated:
        raise HTTPException(401, "Authentication required (X-Actor-Id and X-Actor-Role)")
    return actor


def require_roles(actor: ActorContext, allowed: frozenset[str]) -> ActorContext:
    require_authenticated(actor)
    if actor.role not in allowed:
        raise HTTPException(403, f"Role {actor.role} not permitted for this operation")
    return actor


def can_read_fleet(actor: ActorContext) -> bool:
    if not actor.is_authenticated:
        # Harness convenience: anonymous read of fleet snapshot
        return True
    return actor.role in ROLES


def require_write(actor: ActorContext) -> ActorContext:
    return require_roles(actor, WRITE_ROLES)


def require_reassign(actor: ActorContext) -> ActorContext:
    return require_roles(actor, REASSIGN_ROLES)


def can_admin_override(actor: ActorContext) -> bool:
    return actor.is_authenticated and actor.role in ADMIN_OVERRIDE_ROLES
