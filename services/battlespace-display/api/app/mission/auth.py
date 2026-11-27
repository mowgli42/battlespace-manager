"""Mission-management identity: header harness + production JWT/OIDC SSO.

``MISSION_AUTH_MODE``:
  - ``header`` (default): ``X-Actor-Id`` / ``X-Actor-Role`` for local harness.
  - ``jwt``: Bearer JWT required. Validates HS256 (``MISSION_JWT_SECRET``) or
    RS256/ES256 via JWKS (``MISSION_JWT_JWKS_URL`` / OIDC discovery).
    Optional ``MISSION_AUTH_ALLOW_HEADER_FALLBACK=1`` keeps harness headers when
    no Bearer token is present (tests / dual-mode gateways).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Header, HTTPException, Request

from app.mission.models import ROLES

logger = logging.getLogger("mission-auth")

# Incomplete for production when mode=header: identity is forgeable without a gateway/SSO.

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

_jwks_cache: dict[str, Any] = {"fetched_at": 0.0, "keys": None}
_JWKS_TTL_SECONDS = 3600


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str
    auth_source: str = "anonymous"

    @property
    def is_authenticated(self) -> bool:
        return bool(self.actor_id) and self.role in ROLES


def auth_mode() -> str:
    return (os.getenv("MISSION_AUTH_MODE") or "header").strip().lower()


def allow_header_fallback() -> bool:
    return os.getenv("MISSION_AUTH_ALLOW_HEADER_FALLBACK", "").lower() in ("1", "true", "yes")


def _normalize_role(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, list):
        # Prefer highest-ranked known role from a list claim
        best = ""
        best_rank = -1
        for item in raw:
            r = str(item).strip().lower().replace("-", "_").replace(" ", "_")
            # Map common IdP group names
            aliases = {
                "mission_supervisor": "mission_supervisor",
                "missionsupervisor": "mission_supervisor",
                "team_supervisor": "team_supervisor",
                "teamsupervisor": "team_supervisor",
                "operator": "operator",
                "analyst": "analyst",
                "admin": "admin",
                "administrator": "admin",
            }
            mapped = aliases.get(r, r)
            if mapped in ROLES and ROLE_RANK.get(mapped, 0) > best_rank:
                best = mapped
                best_rank = ROLE_RANK[mapped]
        return best
    r = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "missionsupervisor": "mission_supervisor",
        "teamsupervisor": "team_supervisor",
        "administrator": "admin",
    }
    return aliases.get(r, r)


def _actor_from_claims(claims: dict[str, Any]) -> ActorContext:
    actor_claim = os.getenv("MISSION_JWT_ACTOR_CLAIM", "sub")
    role_claim = os.getenv("MISSION_JWT_ROLE_CLAIM", "role")
    actor_id = str(claims.get(actor_claim) or claims.get("preferred_username") or "").strip()
    role = _normalize_role(claims.get(role_claim) or claims.get("roles") or claims.get("realm_access", {}).get("roles"))
    if not actor_id:
        raise HTTPException(401, "JWT missing actor claim")
    if role and role not in ROLES:
        raise HTTPException(403, f"JWT role not permitted: {role}")
    if not role:
        raise HTTPException(403, "JWT missing role claim")
    return ActorContext(actor_id=actor_id, role=role, auth_source="jwt")


def _fetch_jwks(url: str) -> dict[str, Any]:
    now = time.time()
    if _jwks_cache["keys"] is not None and now - float(_jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]  # type: ignore[return-value]
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — URL from env config
        data = json.loads(resp.read().decode("utf-8"))
    _jwks_cache["keys"] = data
    _jwks_cache["fetched_at"] = now
    return data


def _jwks_url() -> str:
    explicit = (os.getenv("MISSION_JWT_JWKS_URL") or "").strip()
    if explicit:
        return explicit
    issuer = (os.getenv("MISSION_JWT_ISSUER") or "").rstrip("/")
    if issuer:
        # OIDC discovery
        try:
            disc_url = f"{issuer}/.well-known/openid-configuration"
            req = urllib.request.Request(disc_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                disc = json.loads(resp.read().decode("utf-8"))
            jwks = disc.get("jwks_uri")
            if jwks:
                return str(jwks)
        except Exception:
            logger.exception("OIDC discovery failed for %s", issuer)
            return f"{issuer}/protocol/openid-connect/certs"
    return ""


def _decode_jwt(token: str) -> dict[str, Any]:
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise HTTPException(503, "PyJWT not installed; cannot validate SSO tokens") from exc

    options = {"require": ["exp", "sub"]}
    issuer = (os.getenv("MISSION_JWT_ISSUER") or "").strip() or None
    audience = (os.getenv("MISSION_JWT_AUDIENCE") or "").strip() or None
    secret = (os.getenv("MISSION_JWT_SECRET") or "").strip()
    algorithms_env = (os.getenv("MISSION_JWT_ALGORITHMS") or "").strip()

    decode_kwargs: dict[str, Any] = {"options": options}
    if issuer:
        decode_kwargs["issuer"] = issuer
    if audience:
        decode_kwargs["audience"] = audience

    if secret:
        algs = [a.strip() for a in algorithms_env.split(",") if a.strip()] or ["HS256"]
        return jwt.decode(token, secret, algorithms=algs, **decode_kwargs)

    jwks = _jwks_url()
    if not jwks:
        raise HTTPException(
            503,
            "JWT mode requires MISSION_JWT_SECRET or MISSION_JWT_JWKS_URL / MISSION_JWT_ISSUER",
        )
    algs = [a.strip() for a in algorithms_env.split(",") if a.strip()] or ["RS256", "ES256"]
    try:
        client = PyJWKClient(jwks, cache_keys=True, lifespan=_JWKS_TTL_SECONDS)
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=algs, **decode_kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(401, "Invalid or expired token") from exc


def _bearer_token(authorization: str | None, request: Request | None) -> str | None:
    header = authorization
    if not header and request is not None:
        header = request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _from_headers(x_actor_id: str | None, x_actor_role: str | None) -> ActorContext:
    actor_id = (x_actor_id or "").strip()
    role = (x_actor_role or "").strip().lower()
    if role and role not in ROLES:
        raise HTTPException(400, f"Unknown role: {role}")
    source = "header" if actor_id and role else "anonymous"
    return ActorContext(actor_id=actor_id, role=role, auth_source=source)


async def parse_actor(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
) -> ActorContext:
    mode = auth_mode()
    token = _bearer_token(authorization, request)

    if mode == "jwt":
        if token:
            claims = _decode_jwt(token)
            return _actor_from_claims(claims)
        if allow_header_fallback():
            return _from_headers(x_actor_id, x_actor_role)
        raise HTTPException(401, "Bearer token required (MISSION_AUTH_MODE=jwt)")

    # header mode (default) — still accept Bearer if present for dual-stack clients
    if token and os.getenv("MISSION_AUTH_ACCEPT_JWT_IN_HEADER_MODE", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        try:
            return _actor_from_claims(_decode_jwt(token))
        except HTTPException:
            pass
    return _from_headers(x_actor_id, x_actor_role)


def require_authenticated(actor: ActorContext) -> ActorContext:
    if not actor.is_authenticated:
        raise HTTPException(401, "Authentication required")
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


def clear_jwks_cache_for_tests() -> None:
    _jwks_cache["keys"] = None
    _jwks_cache["fetched_at"] = 0.0
