# Mission Management (Phase 1)

Supervisor-facing organizational layer on battlespace-display. COP picture/SSE remains the tactical truth; mission APIs own durable ownership and accountable tasks.

## Quick start

1. Run battlespace API/UI as usual (`python3 scripts/run-battlespace-local.py` + UI script).
2. Open the **Supervisor** tab (keyboard `9`) or `?tab=supervisor` for fleet / teams / workload / conflicts / **Performance** / mission progress.
3. Open the **Team** tab (keyboard `0`) or `?tab=team` for the Operating Team Console.
4. Store path defaults to `services/battlespace-display/data/mission.db` (`MISSION_STORE_PATH` overrides). Seed: `fixtures/mission-management-seed-v1.json` (v1.2 includes utilization samples).

## Auth headers (local / harness)

| Header | Example |
|--------|---------|
| `X-Actor-Id` | `OP-SUPER-1` |
| `X-Actor-Role` | `mission_supervisor` |

Roles: `mission_supervisor`, `team_supervisor`, `operator`, `analyst`, `admin`. Writes require authentication; fleet reads allow anonymous harness use.

## Ownership rules (enforced)

- One primary team per platform; optional primary operator.
- Support does not transfer primary ownership.
- One accountable owner per active mission task; support operators separate.
- Reassignment stays pending until acknowledgement (unless admin override).
- Assignment history and audit events are retained.

## Cross-repo

No o-my / o-my-sim changes in Phase 1. Future Redis `uci.mission.*` topics are a documented integration dependency (ADR 003).

## Verify

```bash
python3 scripts/check-gherkin-alignment.py
python3 scripts/verify-mission-management-features.py
cd services/battlespace-display/api && PYTHONPATH=. python3 -m unittest tests.test_mission_management -v
```
