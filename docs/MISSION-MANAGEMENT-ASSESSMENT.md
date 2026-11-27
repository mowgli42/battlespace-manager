# Mission Management Foundation — Repository Assessment

**Date:** 2026-11-27 (America/New_York)  
**Scope:** Phase 1 readiness for centralized mission supervision on battlespace-manager  
**Status:** Assessment complete; architecture supports additive Phase 1 without breaking repo boundaries

## Existing capabilities to reuse

| Capability | Location | Reuse plan |
|------------|----------|------------|
| COP picture + SSE | `battlespace-display` `/api/picture`, `/api/stream` | Fleet overview joins platform telemetry freshness from picture; does not replace picture |
| Platform rows | `picture.platforms[]` (harness + bus) | Overlay primary team/operator; keep technical readiness from existing `readiness` |
| Task rows | `picture.task_rows[]` + harness assign | Keep CAOC F2T2EA tasking; mission tasks are a separate accountable lifecycle |
| Platform context UI | `PlatformContextPanel.svelte` | Extend with ownership + assignment history; do not duplicate aircraft records |
| OpenSpec index | `docs/OPENSPEC.md` | Extend with mission-management surface |
| Gherkin + harness checks | `features/`, `*_FEATURE_CHECKS` | Add `features/mission-management/` + dedicated verify (do not overload F2T2EA checks) |
| Compat pin | `compat/tested-against.json` | Unchanged for Phase 1 (no o-my / o-my-sim contract change) |

## Existing data models that can be extended

- **Platform** — extend with organizational overlay (`primary_team_id`, `primary_operator_id`, operational availability, commitments). Technical readiness continues to come from picture/OMS.
- **Task (CAOC)** — `task_rows` remain kill-chain/tasking artifacts with `assigned_platform_id`. Mission-management **Task** is a distinct accountable work item that may reference platforms and CAOC task IDs.
- **Mission thread** — soft F2T2EA aggregate; keep as COP narrative. First-class **Mission** entity is new and owns objectives/milestones.

## Overlap with proposed features

| Proposed | Existing overlap | Decision |
|----------|------------------|----------|
| Task assignment | Harness `/api/harness/assign` + bus `TASK_REQUEST` | Keep as tactical platform assignment; mission Assignment is explicit primary/support with acknowledgement |
| Operator tags | entity-display track tags | Unrelated; do not conflate with Operator identity |
| Attention rail | urgency cues | Inform alerts; do not replace Exceptions panel |
| Workload score | None found | Do not invent 0–100 score in Phase 1 |

## Architectural gaps

1. **No durable store** — process memory only; Redis is pub/sub. Mission/task/assignment/audit need SQLite (or equivalent) in this repo.
2. **No human org model** — no Team / Operator / supervisor identity.
3. **No RBAC** — CORS open; Phase 6 clearance mock planned only. Phase 1 adds header-based role enforcement (documented as non-production).
4. **Ambiguous ownership** — `assigned_platform_id` is not primary/support assignment history.
5. **No mission supervisor surface** — COP tabs are tactical; management UI must be separate.
6. **No audit trail** for ownership/reassignment.

## Cross-repository coordination

| Change | Repo | Phase 1 action |
|--------|------|----------------|
| Platform telemetry / readiness | o-my / o-my-sim | **No change.** Consume existing picture fields. |
| CAOC task lifecycle on bus | o-my-sim task-allocator | **No change.** Mission tasks are BM-authoritative for Phase 1. |
| Publish mission events on Redis | o-my topics | **Deferred.** Document future `uci.mission.*` topics as integration dependency. |
| Operator identity from SSO | none | **Deferred.** Header actor context for local/harness. |

**Integration dependency (documented, not implemented):** If o-my later publishes authoritative org or mission events, BM should subscribe and reconcile rather than dual-write. Phase 1 keeps BM as owner of organizational mission state.

## Backward-compatibility risks

| Risk | Mitigation |
|------|------------|
| Picture contract breakage | Do not add required picture keys for mission state; expose `/api/mission/*` separately |
| Harness assign semantics | Leave `/api/harness/assign` unchanged |
| UI tab overload | New Supervisor tab; COP tabs untouched for management CRUD |
| Auth headers absent | Read endpoints allow anonymous read in harness; writes require actor + role |
| SQLite file path | Configurable `MISSION_STORE_PATH`; default under service data dir; tests use temp DB |

## Architecture confirmation

Existing Svelte + FastAPI + Redis/SSE stack **supports** Phase 1 as an additive management layer inside `battlespace-display` without rewriting COP or crossing into o-my / o-my-sim ownership (ADR 002). Proceed with Phase 1 per ADR 003.
