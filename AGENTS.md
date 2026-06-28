# battlespace-manager — agent notes

## Layout

```text
services/
  entity-display/       C2 map (from o-my) — API :8003, web :8080
  battlespace-display/  Gulf War F2T2EA UI (from o-my-sim) — API :8004, web :8081
scripts/
  env.sh                PYTHONPATH to sibling o-my + o-my-sim uci_common
  run-entity-display-local.sh
  run-battlespace-local.py
  run-battlespace-ui.sh
fixtures/
  commlink-directory-v1.1.xml
```

## Dependencies

- **entity-display API** → `o-my/packages/uci_common` (commlink_display, RedisBus)
- **battlespace-display API** → `o-my-sim/packages/uci_common` (GulfWarEngine, advisor_bridge)

Both sibling repos must exist at `../o-my` and `../o-my-sim` (override with `OMY_ROOT` / `OMYSIM_ROOT`).

## Conventions

- Keep UI work under `services/*/web/src/`.
- Keep API work under `services/*/api/app/`.
- Do not add simulation engines here — those stay in o-my-sim.
- Port 8080 = entity display; 8081 = battlespace display (avoids conflict when both run).
