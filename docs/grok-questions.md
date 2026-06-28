# Grok consultation queue

Paste new questions into the [Grok COP thread](https://grok.com/share/c2hhcmQtMg_28836953-c53c-4879-865f-ef40890a1a41). Responses from [Grok review of grok-questions.md](https://grok.com/share/c2hhcmQtMg_e647463e-e831-4d1d-a086-6190dbe0cdd3).

---

## Q1: milsymbol SIDC from affiliation + domain (Phase 1)

**Beads:** `battlespace-manager-ykl`  
**Status:** answered → implementing  
**Grok share:** https://grok.com/share/c2hhcmQtMg_e647463e-e831-4d1d-a086-6190dbe0cdd3

**Response (summary):**

- `npm install milsymbol`
- Map `affiliation` → H/F/U, `domain` → A/G/U; base SIDC `S{aff}{dim}P-----------`
- SAM hint: `platform_type` contains `SA-` → `...E-----------`
- Cache `L.Icon` per `affiliation|domain|platform_type` key; upsert markers in existing `markers` Map (no layer recreate)
- Implement in `src/lib/sidc.ts` + `milSymbol.ts`; wire in `App.svelte` `updateMap()`

---

## Q2: shallowRef equivalent in Svelte 5 + Leaflet (Phase 2)

**Beads:** `battlespace-manager-a8h`  
**Status:** answered (partially in Phase 1)  
**Grok share:** https://grok.com/share/c2hhcmQtMg_e647463e-e831-4d1d-a086-6190dbe0cdd3

**Response (summary):**

- `markers = new Map()` outside `$state` is the hot path (already correct)
- `applyPayload(data)`: set `picture = data` for panels; loop entities → `upsertMarker`; prune removed ids
- Optional `lastPictureAt = $state(0)` for HUD latency only
- No SvelteMap needed for Leaflet path

---

## Q3: IndexedDB picture cache shape (Phase 5)

**Beads:** `battlespace-manager-fyc`  
**Status:** answered (deferred to Phase 5)  
**Grok share:** https://grok.com/share/c2hhcmQtMg_e647463e-e831-4d1d-a086-6190dbe0cdd3

**Response (summary):**

- Use Dexie: `pictures` store (`key`, `synced_at`, `data`); `actionQueue` stub for offline advisor actions
- `cachePicture()` on SSE success; `getCachedPicture()` in `onMount` when disconnected
- Wire in Phase 5 — do not add Dexie until milsymbol + hot path stable

---

## Repo review notes (Grok)

- Keep SSE for picture broadcast; prop passing fine until context store needed
- Leaflet + `L.canvas()` renderer pragmatic; markercluster only if >500 real entities
- Extend panels via `TABS` + `_picture_payload()` — match existing pattern
- Leverage `o-my` / `o-my-sim` `uci_common` — do not duplicate engine/advisor logic here
