# Deferred Stack Implementation — Bus, SSO, Continuous Sampler

**Branch:** `cursor/mission-management-foundation-b629`  
**Date:** 2026-11-27 (America/New_York)

## Delivered

| Capability | Implementation |
|------------|----------------|
| Redis `uci.mission.*` | `mission/topics.py` + `mission/bus.py`; publish after durable SQLite audit; optional subscribe (`MISSION_BUS_SUBSCRIBE`) with idempotent sample/audit ingest |
| Production SSO | `MISSION_AUTH_MODE=jwt` Bearer validation (HS256 secret or JWKS/OIDC discovery); harness header fallback via `MISSION_AUTH_ALLOW_HEADER_FALLBACK` |
| Continuous sampler | `mission/sampler.py` daemon when `MISSION_SAMPLER_ENABLED=1` (interval `MISSION_SAMPLER_INTERVAL_SECONDS`, default 900) |

## Topic contract (BM-owned until o-my pins)

Avoids collision with o-my `uci.mission.plan*`:

- `uci.mission.event` (umbrella)
- `uci.mission.task` / `assignment` / `ownership` / `alert` / `sample`

SQLite remains authoritative. Bus publish is best-effort and never sole authority (ADR 003).

## Env flags

| Variable | Purpose |
|----------|---------|
| `MISSION_BUS_ENABLED` | Publish audit/sample envelopes to Redis |
| `MISSION_BUS_SUBSCRIBE` | Peer ingest of `uci.mission.*` |
| `REDIS_URL` | Bus transport (`memory://` supported via uci_common) |
| `MISSION_AUTH_MODE` | `header` (default) or `jwt` |
| `MISSION_JWT_SECRET` / `MISSION_JWT_JWKS_URL` / `MISSION_JWT_ISSUER` | Token validation |
| `MISSION_JWT_ACTOR_CLAIM` / `MISSION_JWT_ROLE_CLAIM` | Claim mapping (default `sub` / `role`) |
| `MISSION_AUTH_ALLOW_HEADER_FALLBACK` | Allow `X-Actor-*` when JWT mode has no Bearer |
| `MISSION_SAMPLER_ENABLED` | Background utilization sampler |
| `MISSION_SAMPLER_INTERVAL_SECONDS` | Sample period (default 900) |

## Tests

- `test_mission_deferred.py` (7)
- Harness `mm_bus_topics`, `mm_sso_jwt`, `mm_sampler`
