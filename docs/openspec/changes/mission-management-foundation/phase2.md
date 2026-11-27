# Phase 2 — Resource management

## Scope

Build on Phase 1 ownership and fleet overview:

1. **Operating Team Console** — role-appropriate team view (primary vs support aircraft/operators, missions, tasks, pending acks, blocked, readiness, freshness).
2. **Operator workload overview** — multi-operator factor comparison (no 0–100 score).
3. **Platform commitments & operational availability** — scheduled/active commitments with estimated availability windows.
4. **Team workload comparisons** — side-by-side team factor aggregates and imbalance indicators.
5. **Mission progress overview** — richer criteria-based progress with resource constraints.
6. **Resource conflict indicators** — highlight conflicts/recommendations; never auto-assign.

## Non-goals

- Historical utilization analytics (Phase 3)
- Autonomous assignment
- Redis `uci.mission.*` (still deferred)

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/mission/teams/overview` | All teams with workload factors |
| GET | `/api/mission/teams/{team_id}/console` | Operating Team Console payload |
| GET | `/api/mission/operators/workload` | Operator workload comparison |
| GET | `/api/mission/conflicts` | Resource conflict indicators |
| GET | `/api/mission/platforms/{id}/commitments` | Commitment + availability detail |
| POST | `/api/mission/platforms/{id}/commitments` | Add/update commitment (supervisor+) |

## UI

- New **Team** tab (key `0`) → `TeamConsole.svelte`
- Supervisor Console gains Teams / Workload / Conflicts sections
