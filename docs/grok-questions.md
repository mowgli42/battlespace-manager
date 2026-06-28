# Grok consultation queue

When implementation needs a design call or sample code, add an entry here and paste the section into the [Grok COP thread](https://grok.com/share/c2hhcmQtMg_28836953-c53c-4879-865f-ef40890a1a41). Paste Grok's answer back under **Response** and link the beads issue.

---

## Q1: milsymbol SIDC from affiliation + domain (Phase 1)

**Beads:** `battlespace-manager-ykl`  
**Status:** open  
**Context:** Gulf War `picture.entities[]` has `affiliation` (OPFOR, COALITION, …), `domain` (AIR, SURFACE, GROUND), `platform_type` (e.g. MiG-29, SA-6). We use Leaflet `L.icon` with milsymbol-generated data URLs.

**Question:** Provide a concise `affiliation + domain + platform_type → SIDC` mapping table and sample `milsymbol` + Leaflet code for updating ~300 icons without recreating the layer each tick.

**Our lean:** Hostile air unit → air track hostile; friendly coalition air → friendly aircraft generic; surface OPFOR → hostile ground equipment; unknown → `SUGP-----------` pending refinement.

**Response:** _(awaiting Grok)_

---

## Q2: shallowRef equivalent in Svelte 5 + Leaflet (Phase 2)

**Beads:** `battlespace-manager-a8h`  
**Status:** open  
**Context:** `App.svelte` already keeps `markers = new Map()` and mutates circle markers on SSE. We want Grok's batch upsert pattern formalized.

**Question:** Sample pattern for SSE JSON → `Map<entity_id, Track>` → Leaflet marker upsert at ~5 Hz without triggering Svelte reactivity on the full entity array.

**Our lean:** Keep `picture` for panels; hot path only touches `markers` Map and optional `lastPictureAt` for HUD latency.

**Response:** _(awaiting Grok)_

---

## Q3: IndexedDB picture cache shape (Phase 5)

**Beads:** `battlespace-manager-fyc`  
**Status:** open  
**Context:** Offline-first for operator data, not basemap tiles.

**Question:** Minimal Dexie/idb schema for last `/api/picture` snapshot + `synced_at` + optional action queue stub; hydrate Svelte on load when SSE disconnected.

**Response:** _(awaiting Grok)_
