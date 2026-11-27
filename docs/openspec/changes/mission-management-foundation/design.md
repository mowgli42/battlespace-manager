# Design: Mission Management Foundation

## Context

battlespace-display already streams a COP picture (entities, platforms, task_rows) via snapshot + SSE. Mission management must not become the picture owner; it is a durable organizational layer that joins picture telemetry for readiness/freshness.

## Goals / Non-Goals

**Goals**

- Durable authoritative records for missions, teams, operators, ownership, tasks, assignments, audit.
- Supervisor fleet overview answering awareness / resource / progress questions.
- Explicit primary vs support assignments with acknowledgement and history.
- Backend role checks on state-changing APIs.

**Non-Goals**

- Replacing CAOC `task_rows` or harness assign.
- Autonomic task assignment from workload scores.
- Production identity provider integration.
- Phase 3 analytics.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Service home | Module under `battlespace-display/api/app/mission/` | Same FastAPI process; no new port; ADR 002 display ownership |
| Persistence | SQLite | Stdlib, durable, testable temp DBs; Redis not sole authority |
| Picture coupling | Join on `platform_id` at read time | Avoid required picture key changes |
| Auth | `X-Actor-Id` + `X-Actor-Role` | Minimal Phase 1 enforcement; UI never sole boundary |
| Idempotency | `Idempotency-Key` / client `request_id` on writes | Safe retries |
| Time | UTC ISO-8601 internally; store event + received timestamps | Data-quality requirement |

## API sketch

| Method | Path | Role |
|--------|------|------|
| GET | `/api/mission/fleet` | supervisor+, analyst read |
| GET | `/api/mission/platforms/{id}` | scoped read |
| GET/POST | `/api/mission/teams` | admin write; supervisor+ read |
| GET/POST | `/api/mission/operators` | admin write; supervisor+ read |
| GET/POST | `/api/mission/missions` | supervisor+ |
| GET/POST | `/api/mission/tasks` | role-scoped |
| POST | `/api/mission/tasks/{id}/acknowledge` | accountable owner / override |
| POST | `/api/mission/tasks/{id}/reassign` | supervisor+ |
| POST | `/api/mission/tasks/{id}/complete` | owner + evidence when required |
| GET | `/api/mission/alerts` | supervisor+ |
| GET | `/api/mission/audit` | supervisor+, admin |

## Ownership state machine (assignment)

```
proposed → pending_ack → active
                      ↘ superseded (history retained)
admin_override → active (audited)
```

## Task lifecycle

```
CREATED → REVIEWED → ASSIGNED → ACCEPTED → IN_PROGRESS → COMPLETED
Alternates: DEFERRED | BLOCKED | UNABLE_TO_COMPLETE | CANCELLED
```

## Risks / Trade-offs

- Dual task concepts (CAOC vs mission) until cross-repo integration.
- Header auth is forgeable without TLS/gateway — documented incomplete.
- SQLite single-writer adequate for Phase 1 single-API process.

## Migration

Seed from `fixtures/mission-management-seed-v1.json` mapped to harness platform IDs. Empty store auto-seeds on first start in harness mode.
