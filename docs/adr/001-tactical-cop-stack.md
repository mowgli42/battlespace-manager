# ADR 001: Tactical COP stack (Grok → battlespace-manager)

**Status:** Accepted  
**Date:** 2026-06-28  
**Epic:** `battlespace-manager-9zb`  
**Grok source:** https://grok.com/share/c2hhcmQtMg_28836953-c53c-4879-865f-ef40890a1a41

## Context

Grok reviewed a greenfield tactical COP architecture (Vue 3, MapLibre, Pinia, Dexie, WebSocket, milsymbol). battlespace-manager already ships operator displays on a different stack. This ADR maps Grok's constraints to our codebase without a rewrite.

## Decision

| Grok pattern | battlespace-manager choice |
|--------------|----------------------------|
| Vue 3 + Pinia | **Svelte 5** — `battlespace-display` + `entity-display` |
| `shallowRef` + `Map` for tracks | **Manual Leaflet marker `Map`** in `App.svelte` `updateMap()` — upsert by `entity_id`, avoid reassigning full `picture` on hot path (Phase 2) |
| WebSocket telemetry | **SSE** `GET /api/stream` + snapshot `GET /api/picture` (FastAPI + `GulfWarEngine`) |
| MapLibre GL JS | **Leaflet** for Phases 1–8; **MapLibre spike** deferred to Phase 9 (500+ track benchmark) |
| Dexie full offline sync | **IndexedDB last-picture cache** first (Phase 5); action queue sync later |
| milsymbol MIL-STD-2525D | **Phase 1** — `milsymbol` npm, affiliation/domain → SIDC mapping (see `docs/grok-questions.md`) |
| RBAC `v-can` | **Phase 6** — clearance mock + tab DOM removal in Svelte |
| Typed `Track` model | **`src/types/track.ts`** + Zod; map from `picture.entities[]` |

## Dual-display COP

| Display | Port | Data source | COP role |
|---------|------|-------------|----------|
| entity-display | 8080 | o-my Redis (`uci.entity`, commlinks) | Production C2 / ADS-B + comms |
| battlespace-display | 8081 | Embedded or Redis `GulfWarEngine` | F2T2EA scenario operator picture |

Shared: tactical symbology conventions, compat banner (`compat/tested-against.json`), export/filter patterns.

## Contract

Operator picture JSON is validated by `app.picture_contract.validate_picture()` and tested at `services/battlespace-display/api/tests/test_picture_contract.py`. Frontend `Track` types must round-trip from `entities[]` without loss of id, position, affiliation, or confidence.

## Consequences

- **Positive:** Incremental TDD on existing UI; Grok performance and symbology guidance without framework migration.
- **Negative:** Leaflet may need Phase 9 Canvas/WebGL layer for 2000+ tracks; offline basemap tiles explicitly out of scope until Phase 9.
- **Open:** SIDC selection rules — queued for Grok in `docs/grok-questions.md`.
