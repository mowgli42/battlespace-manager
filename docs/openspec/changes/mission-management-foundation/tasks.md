# Tasks: Mission Management Foundation (Phase 1)

## 1. Specs and docs

- [x] 1.1 Repository assessment
- [x] 1.2 ADR 003 ownership decision
- [x] 1.3 OpenSpec proposal / design / capability specs
- [x] 1.4 Update `docs/OPENSPEC.md` index

## 2. Domain and persistence

- [x] 2.1 Models for Mission, Team, Operator, Platform overlay, Task, Assignment, Audit, Alert
- [x] 2.2 SQLite store with history-preserving assignment updates
- [x] 2.3 Seed fixture aligned to harness platforms
- [x] 2.4 Ownership rule enforcement in service layer

## 3. API and auth

- [x] 3.1 Role helpers (supervisor, team_supervisor, operator, analyst, admin)
- [x] 3.2 `/api/mission/*` routes with write authorization
- [x] 3.3 Task acknowledge / reassign / complete with audit
- [x] 3.4 Fleet overview join with picture freshness

## 4. UI

- [x] 4.1 Supervisor Console — fleet overview
- [x] 4.2 Platform detail ownership + history
- [x] 4.3 Wire Supervisor tab without altering COP tabs

## 5. Tests and Gherkin

- [x] 5.1 Backend unit/service tests
- [x] 5.2 Gherkin scenarios (12 required cases)
- [x] 5.3 Verify script / harness checks for mission features
- [x] 5.4 Contract note: no o-my schema change required

## 6. Phase 2 — Resource management

- [x] 6.1 Operating Team Console API + UI (key `0`)
- [x] 6.2 Operator workload overview comparison
- [x] 6.3 Platform commitments + operational availability
- [x] 6.4 Team workload comparisons
- [x] 6.5 Mission progress with dependencies/constraints
- [x] 6.6 Resource conflict indicators (no auto-assign)
- [x] 6.7 Phase 2 Gherkin + harness checks + unit tests

## 7. Phase 3 — Performance intelligence

- [x] 7.1 Utilization sample persistence + historical utilization metric
- [x] 7.2 Uncommitted operational time (reserve excluded from inefficiency)
- [x] 7.3 Task on-time + delay metrics
- [x] 7.4 Mission milestone analytics
- [x] 7.5 Aircraft/sensor health from picture
- [x] 7.6 Post-flight performance review
- [x] 7.7 Bottleneck analysis (no auto-assign)
- [x] 7.8 Supervisor Performance UI + Gherkin/harness checks

## 8. Deferred stack (implemented)

- [x] 8.1 Redis `uci.mission.*` publish/subscribe (`mission/topics.py`, `mission/bus.py`)
- [x] 8.2 Production SSO / JWT-OIDC with header harness fallback (`MISSION_AUTH_MODE=jwt`)
- [x] 8.3 Continuous live sampler daemon (`mission/sampler.py`, `MISSION_SAMPLER_ENABLED`)
- [x] 8.4 Tests + harness checks `mm_bus_topics` / `mm_sso_jwt` / `mm_sampler` — see [MISSION-MANAGEMENT-DEFERRED-SUMMARY.md](../../../MISSION-MANAGEMENT-DEFERRED-SUMMARY.md)
