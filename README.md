# battlespace-manager

**Operational web displays** for the Open Arsenal / OMS / UCI stack — extracted from [`o-my`](https://github.com/mowgli42/o-my) and [`o-my-sim`](https://github.com/mowgli42/o-my-sim). **Tested against o-my `0.2.0`** — see [`compat/tested-against.json`](compat/tested-against.json).

| Display | Role | Default ports |
|---------|------|---------------|
| **entity-display** | Production C2 map — ADS-B tracks, commlink overlays, affiliation filters, operator tagging | UI `:8080`, API `:8003` |
| **battlespace-display** | Gulf War F2T2EA operator UI — kill chain, tasking, advisor | UI `:8081`, API `:8004` |
| **rf-display** | RF spectrum / EMSO — commlinks, threat radars, EW jamming, EMCON deconfliction | UI `:8082`, API `:8005` |

Simulation engines, sensors, and the sim-control panel remain in **o-my-sim** (sim-control → **scenario-director :8010**, not embedded GulfWarEngine). Core C2 pipeline (entity-fusion, entity-sorter, commlink-status, control plane) remains in **o-my**.

**Cross-stack displays:** with o-my processors + o-my-sim publishers running, start displays against shared Redis:

```bash
cd ../o-my && ./scripts/run-cross-stack-compose.sh -d
cd ../o-my && ./scripts/run-cross-stack-displays.sh
# or: REDIS_URL=redis://127.0.0.1:6379/0 ./scripts/run-battlespace-bus.sh
```

## Operator displays

Start the **display portal** (`:8888`) or any API `/landing` page to see live status for all displays and OMS monitoring (Prometheus `:9090`, Grafana `:3000`).

![Display portal — service status for all operator UIs and OMS monitoring](docs/images/displays/display-portal.png)

| Display | Screenshot | Harness |
|---------|------------|---------|
| Entity (C2 map + fog/route overlays) | ![Entity display](docs/images/displays/entity-display.png) | `ENTITY_HARNESS=1` |
| Battlespace (F2T2EA tasking + kill chain) | ![Battlespace display](docs/images/displays/battlespace-display.png) | `BATTLESPACE_HARNESS=1` |
| RF spectrum (EMSO deconfliction) | ![RF display](docs/images/displays/rf-display.png) | `RF_HARNESS=1` |

### Route threats & popup tasking

Bus / harness picture now includes `route_threats` and Attention Rail **POPUP** cues from `uci.route.threat` / `uci.threat.notification` (o-my `popup-tasker` + `threat-notifier`).

| View | Screenshot |
|------|------------|
| Attention rail (POPUP + TST) | ![Attention rail](docs/images/presentation/metrics/metric-attention-rail.png) |
| Impacted routes (Strike/EJ/Jam bands) | ![Impacted routes](docs/images/presentation/metrics/metric-route-threats.png) |
| Routes tab (full shell) | ![Routes tab](docs/images/walkthrough/08-routes-impacted.png) |
| Map + segment timeline | ![Route map timeline](docs/images/walkthrough/08-route-map-timeline.png) |
| CAOC tasking (popup bands) | ![Popup tasking](docs/images/walkthrough/08-tasking-popup-bands.png) |

```bash
# Harness API :8004 + UI :8081, then:
python3 scripts/capture-route-threat-screenshots.py http://127.0.0.1:8081
```

Regenerate screenshots (starts harness-mode stack, captures Playwright shots):

```bash
./scripts/capture-display-screenshots.sh
# → docs/images/displays/*.png
```

## Tech stack

Tactical COP architecture is documented in [ADR 001 — tactical COP stack](docs/adr/001-tactical-cop-stack.md) (Grok review mapped to this repo; no greenfield Vue/MapLibre rewrite).

| Layer | battlespace-display | entity-display |
|-------|---------------------|----------------|
| **UI** | Svelte 5, Vite 6 | Svelte 5, Vite 6 |
| **Map** | Leaflet + **milsymbol** (MIL-STD-2525D) | Leaflet |
| **Picture transport** | SSE `GET /api/stream` + snapshot `GET /api/picture` | SSE + REST |
| **API** | FastAPI, uvicorn | FastAPI, uvicorn, Redis |
| **Scenario / tracks** | `BUS_PICTURE_MODE` bus subscriber or embedded `GulfWarEngine` (harness) | o-my fusion path (`uci.correlated.entity`, `uci.entity.*`) |
| **Contracts** | Zod `Track` model, `picture_contract.py` | UCI XML → categorized entities |
| **Tests** | vitest (web), Python unittest (API) | vitest, Python unittest |

**Shared conventions:** UCI message contracts via `uci_common`, compat banner (`compat/tested-against.json`), CARTO dark basemap tiles.

**Implemented (COP phases 0–1):** typed track model, picture JSON contract, MIL-STD-2525D map markers, unified timeline tab, attention rail + F2T2EA phase filter.

**Planned (later phases):** IndexedDB last-picture cache (Phase 5), clearance/RBAC mock (Phase 6), MapLibre spike for 500+ tracks (Phase 9). WebSocket and full Dexie offline sync are explicitly out of scope for the current stack.

## Prerequisites

Clone all three repos as siblings:

```text
repo/
  o-my/
  o-my-sim/
  battlespace-manager/
```

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../o-my/packages/uci_common -e ../o-my-sim/packages/uci_common fastapi uvicorn redis
```

## Quick start

### Entity display (C2 map)

Self-contained memory-bus demo (no Redis):

```bash
./scripts/run-entity-display-local.sh
# → http://127.0.0.1:8080
```

With full o-my Redis pipeline, start o-my core services first, then entity-display API from this repo.

### Battlespace display (Gulf War)

**Harness / demo** (embedded engine):

```bash
python3 scripts/run-battlespace-local.py
# API :8004

./scripts/run-battlespace-ui.sh
# UI  :8081
```

**Cross-stack / bus picture mode** (no GulfWarEngine truth — recommended with o-my processors):

```bash
export REDIS_URL=redis://127.0.0.1:6379/0
export BUS_PICTURE_MODE=1
./scripts/run-battlespace-bus.sh
# UI :8081 · API :8004 · COP from uci.correlated.entity, uci.route.threat,
# uci.threat.notification, uci.task, uci.agent.suggestion
```

Sim engineers use **o-my-sim** sim-control panel (`:8090`) against **scenario-director** (`:8010`).

## Docker

Vendor sibling `uci_common` packages, then build:

```bash
./scripts/prepare-docker-vendor.sh
docker compose up --build
```

| URL | Service |
|-----|---------|
| http://localhost:8888 | **Display portal** — all displays + OMS monitoring status |
| http://localhost:8080/landing | Entity display landing (same portal, current display highlighted) |
| http://localhost:8080 | Entity display web |
| http://localhost:8003 | Entity display API (also `/landing`, `/api/portal/status`) |
| http://localhost:8081/landing | Battlespace display landing |
| http://localhost:8081 | Battlespace display web |
| http://localhost:8004 | Battlespace display API |
| http://localhost:8082/landing | RF display landing |
| http://localhost:8082 | RF display web |
| http://localhost:8005 | RF display API |
| http://localhost:9090 | Prometheus (o-my `--profile monitoring`) |
| http://localhost:3000 | Grafana dashboards (`admin` / `admin`) |

## Docs

- [ADR 001 — tactical COP stack](docs/adr/001-tactical-cop-stack.md) — Svelte + Leaflet + SSE vs Grok greenfield
- [COP operator workflow](docs/COP-OPERATOR-WORKFLOW.md) — nominal F2T2EA flow with screenshots (review deck)
- [O-MY walkthrough](docs/O-MY-WALKTHROUGH.md) — end-to-end tour with screenshots
- [Display metrics](docs/DISPLAY-METRICS.md) — header stats, F2T2EA phase rail, attention rail
- [RF display design](docs/RF-DISPLAY-DESIGN.md) — EMSO deconfliction research and rf-display architecture
- [RF display walkthrough](docs/RF-DISPLAY-WALKTHROUGH.md) — operator EMSO workflow with screenshots

Regenerate battlespace workflow screenshots:

```bash
./scripts/demo-presentation.sh
```

Regenerate walkthrough screenshots:

```bash
./scripts/capture-o-my-walkthrough.sh
```

## Testing

Run **all** display unit tests (entity-display + battlespace-display, API + vitest + build):

```bash
./scripts/run-all-tests.sh
```

Verify CAOC tasking queue at T+0 (OMS platforms + ATO tasks) and capture proof screenshot:

```bash
./scripts/capture-tasking-t0.sh
# → docs/images/tasking-queue-t0-fix.png
```

Repo ownership and decoupling rules: [ADR 002](docs/adr/002-repo-boundaries.md).

## Architecture

```mermaid
flowchart TB
  subgraph omy [o-my processors]
    FUSE[entity-fusion]
    SORT[entity-sorter]
    OMS[oms-state-tracker]
    RTM[route-threat-monitor]
    POP[popup-tasker]
    NOTE[threat-notifier]
    CP[service-control-plane]
  end
  subgraph omysim [o-my-sim publishers]
    SD[scenario-director :8010]
    SNS[sensor sims]
    PLAT[platform-status-sim]
    SimCtrl[sim-control :8090]
  end
  subgraph bus [Redis uci.*]
    REDIS[(pub/sub)]
  end
  subgraph bm [battlespace-manager subscribers]
    ED[entity-display :8080]
    BD[battlespace-display :8081]
    ROUTES[Routes tab + Attention rail]
    PORTAL[display-portal :8888]
  end
  SimCtrl -->|/api/sim/*| SD
  SD --> REDIS
  SNS --> REDIS
  PLAT -->|status / route| REDIS
  REDIS --> FUSE
  FUSE -->|correlated.entity| REDIS
  REDIS --> SORT
  REDIS --> OMS
  OMS -->|uci.oms.state| REDIS
  REDIS --> RTM
  RTM -->|uci.route.threat| REDIS
  REDIS --> POP
  POP -->|uci.task| REDIS
  REDIS --> NOTE
  NOTE -->|uci.threat.notification| REDIS
  CP -->|uci.service.status| REDIS
  REDIS --> ED
  REDIS --> BD
  BD --> ROUTES
  REDIS --> PORTAL
```

| Mode | entity-display | battlespace-display | Service health |
|------|----------------|---------------------|----------------|
| Harness | `ENTITY_HARNESS=1` | `BATTLESPACE_HARNESS=1` | HTTP `/health` probes |
| Cross-stack bus | `REDIS_URL` + fusion topics | `BUS_PICTURE_MODE=1` (+ `uci.route.threat`, `uci.threat.notification`, `uci.task`) | `uci.service.status` preferred |

Legacy embedded path (deprecated for cross-stack):

```mermaid
flowchart LR
  subgraph legacy [Legacy harness only]
    Engine[GulfWarEngine monolith]
    BD2[battlespace-display :8081]
  end
  Engine --> BD2
```
