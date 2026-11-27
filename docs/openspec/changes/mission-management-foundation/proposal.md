# Change: Mission Management Foundation (Phase 1)

## Why

Battlespace Manager provides a strong COP and F2T2EA tasking UI, but supervisors cannot answer fleet utilization, organizational ownership, or accountable mission progress questions without overloading tactical displays.

## What changes

- Add durable organizational domain (Mission, Team, Operator, Platform ownership overlay, Task, Assignment, Audit, Alerts).
- Enforce ownership rules (one primary team per platform, one accountable owner per active task, acknowledgement before ownership transfer).
- Add Mission Supervisor Console (fleet overview) and extend platform detail with ownership/history.
- Add backend RBAC headers for supervisor / team supervisor / operator / analyst / admin.
- Add OpenSpec capability specs, Gherkin scenarios, and automated tests.

## Capabilities

| Capability | Phase 1 |
|------------|---------|
| fleet-visibility | Supervisor fleet overview + readiness/freshness |
| organizational-ownership | Teams, operators, primary/support platform ownership |
| task-management | Accountable lifecycle, acknowledgement, reassignment history |
| operator-workload | Primary vs support lists + pending acknowledgements (no 0–100 score) |
| mission-progress | Objectives/milestones/task status counts (criteria-based) |
| alerts-and-audit | Severity levels + durable audit events |
| data-quality | Stale/unknown telemetry handling |

## Out of scope (Phase 1)

- Operating Team Console full UX (Phase 2)
- Historical utilization analytics (Phase 3)
- Autonomous assignment
- o-my / o-my-sim code changes
- Production SSO

## Impact

- Additive APIs under `/api/mission/*`
- New Supervisor tab in battlespace-display web
- New SQLite store; existing harness/COP paths unchanged
