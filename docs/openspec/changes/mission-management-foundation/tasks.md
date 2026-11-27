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

## 6. Phase 2/3 deferred

- [ ] Operating Team Console
- [ ] Full operator workload comparison UI
- [ ] Historical utilization metrics
- [ ] Redis `uci.mission.*` integration
