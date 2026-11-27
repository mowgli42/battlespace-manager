# ADR 003: Mission management ownership within battlespace-display

**Status:** Accepted  
**Date:** 2026-11-27  
**Related:** [ADR 002](002-repo-boundaries.md), [MISSION-MANAGEMENT-ASSESSMENT.md](../MISSION-MANAGEMENT-ASSESSMENT.md)

## Context

Supervisors need fleet-wide organizational ownership, task accountability, and assignment history. The COP picture already shows platforms and CAOC `task_rows`, but:

- There is no Team / Operator model.
- Assignment is a single `assigned_platform_id` without primary/support or acknowledgement.
- State is in-memory; Redis is not durable.
- ADR 002 forbids embedding C2 processors or sim engines in this repo.

## Decision

1. **Authoritative owner:** battlespace-manager (`battlespace-display` mission module) owns Mission, Team, Operator, organizational Platform overlay, accountable Task, Assignment, and Audit records for Phase 1.
2. **Persistence:** SQLite file store (`MISSION_STORE_PATH`). Redis may fan out later; it is never the sole authority for ownership transitions.
3. **API surface:** `/api/mission/*` separate from `/api/picture` / `/api/stream`. Picture remains the COP contract.
4. **UI surface:** Supervisor Console tab complementary to COP tabs; do not overload map/kill-chain with org CRUD.
5. **Auth:** Backend-enforced roles. Phase 1 used forgeable headers (`X-Actor-Id`, `X-Actor-Role`). Production uses `MISSION_AUTH_MODE=jwt` (Bearer HS256 or JWKS/OIDC) with optional header fallback for harness.
6. **CAOC tasks:** Remain tactical/platform-centric. Mission tasks may reference platforms and optional external task IDs but use their own lifecycle (`CREATED` → … → `COMPLETED`).
7. **Cross-repo:** No o-my / o-my-sim changes required. BM publishes optional `uci.mission.*` fan-out (non-colliding with o-my `uci.mission.plan*`); SQLite remains authoritative.

## Consequences

- **Positive:** Clear accountability and audit without breaking picture contracts or repo boundaries.
- **Negative:** Temporary dual concept of “CAOC task” vs “mission task” until a later integration phase reconciles them.
- **Action:** Implement Phase 1 per OpenSpec change `mission-management-foundation`; defer Phase 2/3 consoles and analytics until ownership workflows are stable.
