# OpenSpec — battlespace-manager

Living capability spec for operator displays in this repo. Prefer linking ADRs and contracts over duplicating them.

| Related | Location |
|---------|----------|
| Stack choices (Svelte, Leaflet, SSE) | [ADR 001](adr/001-tactical-cop-stack.md) |
| Repo boundaries (o-my / o-my-sim / BM) | [ADR 002](adr/002-repo-boundaries.md) |
| Operator F2T2EA flow | [COP-OPERATOR-WORKFLOW.md](COP-OPERATOR-WORKFLOW.md) |
| MissionPlan / EOB / retask ingest | [UCI-COP-CONTRACT.md](UCI-COP-CONTRACT.md) |
| RF / EMSO design | [RF-DISPLAY-DESIGN.md](RF-DISPLAY-DESIGN.md) |

## Surfaces

| Surface | UI | API | Role |
|---------|----|-----|------|
| **entity-display** | `:8080` | `:8003` | Production C2 map — tracks, feeds, commlinks, tags |
| **battlespace-display** | `:8081` | `:8004` | Gulf War F2T2EA COP — kill chain, tasking, advisor, routes |
| **rf-display** | `:8082` | `:8005` | RF spectrum / EMSO deconfliction |
| **display-portal** | `:8888` | (same) | Cross-display status landing (`/landing`, `/api/portal/status`) |

Simulation engines and scenario authoring stay in **o-my-sim**. C2 fusion / Redis processors stay in **o-my**. This repo owns HTTP picture/SSE contracts and display UIs only.

## Transport modes

| Mode | When | Picture source |
|------|------|----------------|
| **Harness** | Local demo / Vercel preview | Embedded fixtures or `GulfWarEngine` (`ENTITY_HARNESS`, `BATTLESPACE_HARNESS`, `RF_HARNESS`) |
| **Bus picture** | Cross-stack with Redis | Subscribe to UCI topics; battlespace uses `BUS_PICTURE_MODE=1` (no embedded engine truth) |

Battlespace bus topics (typical): `uci.correlated.entity`, `uci.route.threat`, `uci.threat.notification`, `uci.task`, `uci.agent.suggestion`, **plus** `uci.route.plan`, `uci.mission.plan.execution`, `uci.oob` / pre-briefed `uci.entity`, `uci.task.command` (out). See [UCI-COP-CONTRACT.md](UCI-COP-CONTRACT.md).

## Key API contracts

Shared pattern across displays:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness |
| `GET /api/picture` | Full operator picture snapshot (JSON) |
| `GET /api/stream` | SSE stream of picture updates |
| `GET /api/harness/verify` | Harness mode self-check (when enabled) |

**battlespace-display** picture shape is validated by `services/battlespace-display/api/app/picture_contract.py` (required keys include `entities`, `threat_picture`, `mission_thread`, `attention_queue`, `fkcm_targets`, `timeline_view`, `task_rows`). Frontend `Track` types map from `entities[]`.

**rf-display** picture shape is validated by `services/rf-display/api/app/rf_picture_contract.py` (commlinks, emitters, EW, EMCON, spectrum columns, conflicts).

**entity-display** exposes REST snapshots (`/api/tracks`, `/api/feeds`, `/api/commlinks`, `/api/stats`) plus SSE `/api/stream`, and operator mutations (tags / promote).

Battlespace also exposes sim harness controls (`/api/sim/*`), advisor actions (`/api/advisor/*`), timeline, and OMS-AI service probes — harness/demo oriented; production tasking path is bus + o-my processors.

## Capability phases

| Status | Scope |
|--------|--------|
| **Implemented (COP 0–1)** | Typed track model, picture JSON contracts, MIL-STD-2525D markers (battlespace), SSE + snapshot transport, unified timeline, attention rail + F2T2EA phase filter, route threats / popup cues, RF spectrum deconfliction view |
| **Specified (MissionPlan / EOB)** | Dashed planned vs solid actual; Attention `PLAN_DEVIATION` / `RETASK`; TaskCommand on bus (G4); static EOB overlay — [UCI-COP-CONTRACT.md](UCI-COP-CONTRACT.md) |
| **Planned** | IndexedDB last-picture cache (Phase 5), clearance/RBAC mock (Phase 6), MapLibre spike for 500+ tracks (Phase 9) |
| **Out of scope (current stack)** | WebSocket telemetry, full Dexie offline sync, embedding sim engines or fusion processors in this repo |

Details and rationale: [ADR 001](adr/001-tactical-cop-stack.md). Compat pin: `compat/tested-against.json` (tested against o-my `0.2.0`).

## Maintenance

Update this file when ports, transport modes, required picture keys, or phase status change. Deep design stays in ADRs and display-specific docs; this OpenSpec is the index of what is implemented vs planned.
