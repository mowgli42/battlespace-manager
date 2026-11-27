# Phase 3 — Performance intelligence

## Scope

1. **Historical utilization** — durable utilization samples; platform utilization and uncommitted operational time with explicit metric definitions.
2. **Mission milestone analytics** — criteria-based milestone completion over mission scope / reporting period.
3. **Aircraft and sensor health integration** — join COP picture readiness/subsystems; never invent health.
4. **Post-flight performance review** — completed-task outcomes, delays, evidence, ownership trail.
5. **Workload and resource bottleneck analysis** — aggregate conflict/history factors into ranked bottlenecks (recommendations only).

## Metric definitions (required)

| Metric | Numerator | Denominator | Units | Period | Exclusions |
|--------|-----------|-------------|-------|--------|------------|
| Platform utilization | Mission-assigned sample minutes while Operational | Operationally available sample minutes (excl. held_in_reserve) | ratio / minutes | selected window | Reserved platforms excluded from denominator; stale/unknown readiness excluded from both |
| Uncommitted operational time | Operational samples without active/scheduled commitment | — (absolute) | sample-minutes | selected window | Reserved counted separately as intentional_reserve_minutes |
| Task on-time completion | Eligible tasks completed by due_time | Eligible tasks with due_time in period | ratio | selected window | Cancelled / unable_to_complete excluded |
| Mission milestone completion | Completed required milestones | Total required milestones in scope | ratio | mission scope | Non-required milestones excluded |
| Task delay | actual_completion_time − planned/due_time | per completed task | minutes (signed) | selected window | Incomplete tasks excluded |

Stale/unknown samples are reported separately and never fabricated into Operational.

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/mission/analytics/sample` | Record fleet utilization sample from current picture |
| GET | `/api/mission/analytics/utilization` | Historical utilization metrics |
| GET | `/api/mission/analytics/tasks` | On-time completion + delay metrics |
| GET | `/api/mission/analytics/milestones` | Milestone completion analytics |
| GET | `/api/mission/analytics/health` | Aircraft/sensor health from picture |
| GET | `/api/mission/analytics/post-flight/{mission_id}` | Post-flight review |
| GET | `/api/mission/analytics/bottlenecks` | Ranked bottleneck analysis |

## Non-goals

- Redis `uci.mission.*` publish (still documented dependency)
- Autonomous reassignment from bottlenecks
- Treating estimated workload as validated HF capacity
